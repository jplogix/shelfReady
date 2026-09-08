from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.api.schemas import (
    AddToCartRequest,
    AgentActionOut,
    BatchCreate,
    BatchOut,
    BulkDecisionResolve,
    CartItemOut,
    CartOut,
    ColumnMapping,
    DecisionOut,
    DecisionResolve,
    JobOut,
    ModeResponse,
    ProductDetail,
    ProductOut,
    StartProcessRequest,
    StoreProductOut,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.config import get_settings
from app.db.models import (
    AgentAction,
    Batch,
    BatchStatus,
    Cart,
    CartItem,
    Decision,
    DecisionKind,
    DecisionStatus,
    ImportRow,
    Job,
    JobStatus,
    NormalizationRule,
    Product,
    ProductImage,
    ProductStatus,
    ProductVersion,
    RuleScope,
    StoreProduct,
    Workspace,
)
from app.db.session import get_db
from app.services.csv_import import (
    apply_mapping,
    parse_csv_bytes,
    suggest_column_mapping,
    validate_mapped_row,
)
from app.storage.local import LocalStorage, StorageError

router = APIRouter(dependencies=[Depends(require_auth)])


def get_workspace(db: Session) -> Workspace:
    ws = db.scalar(select(Workspace).limit(1))
    if not ws:
        raise HTTPException(500, "Workspace not seeded")
    return ws


def recompute_batch_counts(db: Session, batch: Batch) -> dict[str, Any]:
    products = db.scalars(select(Product).where(Product.batch_id == batch.id)).all()
    counts = {
        "imported": len(products),
        "corrected": 0,
        "awaiting_decisions": 0,
        "published": 0,
        "verified": 0,
        "failed": 0,
    }
    for p in products:
        if p.status == ProductStatus.published:
            counts["published"] += 1
            if p.verification_passed:
                counts["verified"] += 1
        elif p.status in {ProductStatus.failed, ProductStatus.verification_failed}:
            counts["failed"] += 1
        elif p.status == ProductStatus.needs_review:
            counts["awaiting_decisions"] += 1
        if p.current_version_id:
            v = db.get(ProductVersion, p.current_version_id)
            if v and v.diffs:
                counts["corrected"] += 1
    pending = db.scalar(
        select(func.count()).select_from(Decision).where(
            Decision.batch_id == batch.id, Decision.status == DecisionStatus.pending
        )
    )
    counts["pending_decisions"] = int(pending or 0)
    batch.counts = counts
    return counts


@router.get("/mode", response_model=ModeResponse)
def get_mode() -> ModeResponse:
    settings = get_settings()
    mode = settings.agent_mode
    return ModeResponse(
        agent_mode=mode,
        label="Fixture replay mode" if mode == "replay" else "Live agent mode",
        is_replay=mode == "replay",
        is_live=mode == "live",
    )


@router.get("/workspace", response_model=WorkspaceOut)
def read_workspace(db: Session = Depends(get_db)) -> Workspace:
    return get_workspace(db)


@router.patch("/workspace", response_model=WorkspaceOut)
def update_workspace(body: WorkspaceUpdate, db: Session = Depends(get_db)) -> Workspace:
    ws = get_workspace(db)
    if body.auto_publish_demo is not None:
        ws.auto_publish_demo = body.auto_publish_demo
    if body.name is not None:
        ws.name = body.name
    db.commit()
    db.refresh(ws)
    return ws


@router.get("/batches", response_model=list[BatchOut])
def list_batches(db: Session = Depends(get_db)) -> list[Batch]:
    return list(db.scalars(select(Batch).order_by(Batch.created_at.desc())).all())


@router.post("/batches", response_model=BatchOut)
def create_batch(body: BatchCreate, db: Session = Depends(get_db)) -> Batch:
    ws = get_workspace(db)
    batch = Batch(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name=body.name,
        supplier_name=body.supplier_name,
        status=BatchStatus.draft,
        counts={},
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: uuid.UUID, db: Session = Depends(get_db)) -> Batch:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    recompute_batch_counts(db, batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/batches/{batch_id}/upload", response_model=ColumnMapping)
async def upload_csv(
    batch_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ColumnMapping:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    data = await file.read()
    try:
        headers, rows = parse_csv_bytes(data)
    except Exception as exc:
        raise HTTPException(400, f"Invalid CSV: {exc}") from exc
    mapping = suggest_column_mapping(headers)
    batch.source_filename = file.filename
    batch.column_mapping = mapping
    batch.status = BatchStatus.importing
    # Clear prior rows
    for old in list(batch.import_rows):
        db.delete(old)
    db.flush()
    for i, raw in enumerate(rows, start=1):
        db.add(
            ImportRow(
                id=uuid.uuid4(),
                batch_id=batch.id,
                row_number=i,
                raw=raw,
                is_malformed=False,
            )
        )
    # Persist uploaded file
    storage = LocalStorage()
    dest = storage.root / "uploads" / f"{batch.id}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    db.commit()
    return ColumnMapping(mapping=mapping, headers=headers, preview_rows=rows[:5])


@router.post("/batches/{batch_id}/import", response_model=BatchOut)
def commit_import(
    batch_id: uuid.UUID,
    body: StartProcessRequest,
    db: Session = Depends(get_db),
) -> Batch:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    batch.column_mapping = body.column_mapping
    ws = get_workspace(db)
    storage = LocalStorage()
    fixtures_root = get_settings().fixtures_root
    if not fixtures_root.is_absolute():
        # resolve relative to repo root (two levels up from services/api)
        fixtures_root = (Path.cwd() / fixtures_root).resolve()
        alt = Path(__file__).resolve().parents[4] / "fixtures"
        if alt.exists():
            fixtures_root = alt

    # Remove prior products for re-import
    for p in list(batch.products):
        db.delete(p)
    db.flush()

    seen_skus: dict[str, Product] = {}
    for row in batch.import_rows:
        mapped = apply_mapping(row.raw, body.column_mapping)
        ok, reason = validate_mapped_row(mapped, row.row_number)
        if not ok:
            row.is_malformed = True
            row.malformed_reason = reason
            continue
        sku = mapped["sku"]
        if sku in seen_skus:
            # Conflicting/repeated SKU: create separate product with suffix for tracking
            # Actual conflict decision happens in processing
            product = Product(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                batch_id=batch.id,
                sku=f"{sku}__row{row.row_number}",
                status=ProductStatus.imported,
            )
        else:
            product = Product(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                batch_id=batch.id,
                sku=sku,
                status=ProductStatus.imported,
            )
            seen_skus[sku] = product
        db.add(product)
        db.flush()
        row.product_id = product.id

        # Attach fixture/local image if present
        fname = mapped.get("image_filename")
        if fname:
            src = fixtures_root / "images" / fname
            if src.exists():
                try:
                    saved = storage.copy_fixture(src, subdirectory=f"products/{product.id}")
                    img = ProductImage(
                        id=uuid.uuid4(),
                        product_id=product.id,
                        original_path=saved["original_path"],
                        derivative_path=saved["derivative_path"],
                        mime_type=saved["mime_type"],
                        width=saved["width"],
                        height=saved["height"],
                        size_bytes=saved["size_bytes"],
                        position=0,
                    )
                    db.add(img)
                except StorageError:
                    pass

    batch.status = BatchStatus.ready
    recompute_batch_counts(db, batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/batches/{batch_id}/process", response_model=JobOut)
def start_process(batch_id: uuid.UUID, db: Session = Depends(get_db)) -> Job:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    running = db.scalar(
        select(Job).where(Job.status.in_([JobStatus.pending, JobStatus.running])).limit(1)
    )
    if running:
        raise HTTPException(409, "Another job is already queued or running")
    settings = get_settings()
    job = Job(
        id=uuid.uuid4(),
        batch_id=batch.id,
        job_type="process",
        status=JobStatus.pending,
        agent_mode=settings.agent_mode,
        checkpoint={},
    )
    db.add(job)
    batch.status = BatchStatus.processing
    db.commit()
    db.refresh(job)
    return job


@router.post("/batches/{batch_id}/publish", response_model=JobOut)
def start_publish(batch_id: uuid.UUID, db: Session = Depends(get_db)) -> Job:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    settings = get_settings()
    job = Job(
        id=uuid.uuid4(),
        batch_id=batch.id,
        job_type="publish",
        status=JobStatus.pending,
        agent_mode=settings.agent_mode,
        checkpoint={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/batches/{batch_id}/products", response_model=list[ProductOut])
def list_products(batch_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Product]:
    return list(
        db.scalars(select(Product).where(Product.batch_id == batch_id).order_by(Product.sku)).all()
    )


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> ProductDetail:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    version = db.get(ProductVersion, product.current_version_id) if product.current_version_id else None
    return ProductDetail(
        id=product.id,
        sku=product.sku,
        status=product.status.value,
        verification_passed=product.verification_passed,
        current_version_id=product.current_version_id,
        approved_version_id=product.approved_version_id,
        store_product_id=product.store_product_id,
        original=version.original if version else None,
        proposed=version.proposed if version else None,
        seo=version.seo if version else None,
        diffs=version.diffs if version else [],
        blockers=version.blockers if version else [],
        provenance=version.provenance if version else {},
        is_publishable=version.is_publishable if version else False,
        images=[
            {
                "id": str(i.id),
                "path": i.derivative_path or i.original_path,
                "class": i.image_class.value,
                "is_primary": i.is_primary,
                "classification_source": i.classification_source,
            }
            for i in product.images
        ],
    )


@router.get("/batches/{batch_id}/decisions", response_model=list[DecisionOut])
def list_decisions(
    batch_id: uuid.UUID,
    status: str | None = "pending",
    db: Session = Depends(get_db),
) -> list[Decision]:
    q = select(Decision).where(Decision.batch_id == batch_id).order_by(Decision.created_at.asc())
    if status:
        q = q.where(Decision.status == DecisionStatus(status))
    return list(db.scalars(q).all())


@router.post("/decisions/{decision_id}/resolve", response_model=DecisionOut)
def resolve_decision(
    decision_id: uuid.UUID,
    body: DecisionResolve,
    db: Session = Depends(get_db),
) -> Decision:
    decision = db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(404, "Decision not found")
    if decision.status != DecisionStatus.pending:
        raise HTTPException(400, "Decision already resolved")

    # Stale version check for consequential approvals
    if decision.product_id and decision.product_version_id:
        product = db.get(Product, decision.product_id)
        if product and product.current_version_id != decision.product_version_id:
            raise HTTPException(409, "Stale decision: product was edited after this request")

    if body.action == "approve":
        decision.status = DecisionStatus.approved
        if decision.product_id and decision.product_version_id:
            product = db.get(Product, decision.product_id)
            if product and decision.kind == DecisionKind.publication:
                product.approved_version_id = decision.product_version_id
            if product and decision.kind == DecisionKind.suspicious_price:
                # accept price
                version = db.get(ProductVersion, decision.product_version_id)
                if version:
                    version.is_publishable = True
            if product and decision.field_name and decision.proposed_value is not None:
                version = db.get(ProductVersion, product.current_version_id)
                if version and decision.kind in {
                    DecisionKind.unknown_brand_alias,
                    DecisionKind.ambiguous_category,
                    DecisionKind.unknown_color_alias,
                }:
                    # keep proposed if provided
                    pass
    elif body.action == "edit":
        decision.status = DecisionStatus.edited
        decision.edited_value = body.edited_value
        if decision.product_id:
            product = db.get(Product, decision.product_id)
            if product and product.current_version_id:
                version = db.get(ProductVersion, product.current_version_id)
                if version and decision.field_name:
                    proposed = dict(version.proposed)
                    field = decision.field_name
                    if field == "brand":
                        proposed["brand"] = body.edited_value
                    elif field == "category":
                        proposed["category"] = body.edited_value
                    elif field == "color":
                        proposed["color_families"] = (
                            body.edited_value
                            if isinstance(body.edited_value, list)
                            else [p.strip() for p in str(body.edited_value).split(",")]
                        )
                    elif field == "price":
                        proposed["price"] = str(body.edited_value)
                    elif field == "stock":
                        proposed["stock"] = int(body.edited_value)
                    version.proposed = proposed
                    # invalidate prior approval
                    product.approved_version_id = None
    elif body.action == "reject":
        decision.status = DecisionStatus.rejected
    else:
        raise HTTPException(400, "action must be approve, edit, or reject")

    decision.resolved_at = datetime.now(timezone.utc)

    if body.save_as_rule and body.rule_type and body.rule_target and decision.original_value:
        db.add(
            NormalizationRule(
                id=uuid.uuid4(),
                workspace_id=decision.workspace_id,
                rule_type=body.rule_type,
                source_value=str(decision.original_value),
                target_value=str(body.rule_target),
                scope=RuleScope.workspace,
                active=True,
            )
        )

    # Update product status if no pending decisions left
    if decision.product_id:
        product = db.get(Product, decision.product_id)
        if product:
            pending = db.scalars(
                select(Decision).where(
                    Decision.product_id == product.id,
                    Decision.status == DecisionStatus.pending,
                    Decision.id != decision.id,
                )
            ).all()
            if not pending and product.status == ProductStatus.needs_review:
                # publication decision may still be pending — handled above
                still_pub = [
                    d
                    for d in db.scalars(
                        select(Decision).where(
                            Decision.product_id == product.id,
                            Decision.status == DecisionStatus.pending,
                        )
                    ).all()
                    if d.id != decision.id
                ]
                if not still_pub:
                    version = (
                        db.get(ProductVersion, product.current_version_id)
                        if product.current_version_id
                        else None
                    )
                    if version:
                        from app.policy.validate import validate_product_fields

                        has_primary = any(i.is_primary for i in product.images)
                        result = validate_product_fields(
                            dict(version.proposed), has_primary_image=has_primary
                        )
                        version.proposed = result["proposed"]
                        version.blockers = result["blockers"]
                        # publication still needed unless approved
                        pub_ok = product.approved_version_id == product.current_version_id
                        version.is_publishable = result["is_publishable"] and (
                            pub_ok
                            or any(
                                d.kind == DecisionKind.publication
                                and d.status in {DecisionStatus.approved, DecisionStatus.edited}
                                for d in db.scalars(
                                    select(Decision).where(Decision.product_id == product.id)
                                ).all()
                            )
                        )
                        product.status = (
                            ProductStatus.ready if result["is_publishable"] else ProductStatus.needs_review
                        )

    batch = db.get(Batch, decision.batch_id)
    if batch:
        recompute_batch_counts(db, batch)
    db.commit()
    db.refresh(decision)
    return decision


@router.post("/decisions/bulk-resolve", response_model=list[DecisionOut])
def bulk_resolve(body: BulkDecisionResolve, db: Session = Depends(get_db)) -> list[Decision]:
    if body.action != "approve":
        raise HTTPException(400, "Bulk only supports approve for equivalent low-risk decisions")
    decisions = [db.get(Decision, did) for did in body.decision_ids]
    decisions = [d for d in decisions if d and d.status == DecisionStatus.pending]
    if not decisions:
        return []
    kinds = {d.kind for d in decisions}
    keys = {d.bulk_key for d in decisions}
    tiers = {d.risk_tier for d in decisions}
    if len(kinds) != 1 or len(keys) != 1 or "approval" in tiers:
        raise HTTPException(400, "Bulk approve only for equivalent low-risk decisions")
    results: list[Decision] = []
    for d in decisions:
        results.append(resolve_decision(d.id, DecisionResolve(action="approve"), db))
    return results


@router.get("/batches/{batch_id}/jobs", response_model=list[JobOut])
def list_jobs(batch_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Job]:
    return list(
        db.scalars(select(Job).where(Job.batch_id == batch_id).order_by(Job.created_at.desc())).all()
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/jobs/{job_id}/actions", response_model=list[AgentActionOut])
def list_actions(job_id: uuid.UUID, db: Session = Depends(get_db)) -> list[AgentAction]:
    return list(
        db.scalars(
            select(AgentAction).where(AgentAction.job_id == job_id).order_by(AgentAction.created_at.asc())
        ).all()
    )


@router.get("/store/products", response_model=list[StoreProductOut])
def store_list(db: Session = Depends(get_db)) -> list[StoreProduct]:
    return list(db.scalars(select(StoreProduct).order_by(StoreProduct.title)).all())


@router.get("/store/products/{slug}", response_model=StoreProductOut)
def store_get(slug: str, db: Session = Depends(get_db)) -> StoreProduct:
    sp = db.scalar(select(StoreProduct).where(StoreProduct.slug == slug))
    if not sp:
        raise HTTPException(404, "Not found")
    return sp


@router.post("/store/cart/items", response_model=CartOut)
def add_to_cart(body: AddToCartRequest, db: Session = Depends(get_db)) -> CartOut:
    ws = get_workspace(db)
    sp = db.get(StoreProduct, body.store_product_id)
    if not sp:
        raise HTTPException(404, "Product not found")
    if not sp.available or sp.stock <= 0:
        raise HTTPException(400, "Out of stock — cannot add to cart")
    cart = db.scalar(
        select(Cart).where(Cart.workspace_id == ws.id, Cart.purpose == body.purpose).limit(1)
    )
    if not cart:
        cart = Cart(id=uuid.uuid4(), workspace_id=ws.id, purpose=body.purpose)
        db.add(cart)
        db.flush()
    existing = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.store_product_id == sp.id
        )
    )
    if existing:
        existing.quantity += body.quantity
    else:
        db.add(
            CartItem(
                id=uuid.uuid4(),
                cart_id=cart.id,
                store_product_id=sp.id,
                quantity=body.quantity,
                unit_price=sp.price,
                currency=sp.currency,
            )
        )
    db.commit()
    return _cart_out(db, cart)


@router.get("/store/cart", response_model=CartOut)
def get_cart(purpose: str = "operator", db: Session = Depends(get_db)) -> CartOut:
    ws = get_workspace(db)
    cart = db.scalar(
        select(Cart).where(Cart.workspace_id == ws.id, Cart.purpose == purpose).limit(1)
    )
    if not cart:
        cart = Cart(id=uuid.uuid4(), workspace_id=ws.id, purpose=purpose)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return _cart_out(db, cart)


def _cart_out(db: Session, cart: Cart) -> CartOut:
    items = []
    for it in cart.items:
        sp = db.get(StoreProduct, it.store_product_id)
        items.append(
            CartItemOut(
                id=it.id,
                store_product_id=it.store_product_id,
                quantity=it.quantity,
                unit_price=it.unit_price,
                currency=it.currency,
                title=sp.title if sp else None,
            )
        )
    return CartOut(id=cart.id, purpose=cart.purpose, items=items)


@router.post("/demo/load-sample", response_model=BatchOut)
def load_sample_batch(db: Session = Depends(get_db)) -> Batch:
    """Load the bundled synthetic supplier CSV into a new batch and import products."""
    settings = get_settings()
    fixtures = Path(settings.fixtures_root)
    if not fixtures.is_absolute():
        alt = Path(__file__).resolve().parents[4] / "fixtures"
        fixtures = alt if alt.exists() else Path.cwd() / fixtures
    csv_path = fixtures / "supplier_catalog.csv"
    if not csv_path.exists():
        raise HTTPException(500, f"Fixture CSV missing at {csv_path}")
    ws = get_workspace(db)
    batch = Batch(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="Synthetic Supplier Catalog",
        supplier_name="Northwind Synthetic Supply",
        status=BatchStatus.draft,
        counts={},
    )
    db.add(batch)
    db.commit()
    data = csv_path.read_bytes()
    headers, rows = parse_csv_bytes(data)
    mapping = suggest_column_mapping(headers)
    batch.column_mapping = mapping
    batch.source_filename = "supplier_catalog.csv"
    for i, raw in enumerate(rows, start=1):
        db.add(ImportRow(id=uuid.uuid4(), batch_id=batch.id, row_number=i, raw=raw))
    db.commit()
    return commit_import(batch.id, StartProcessRequest(column_mapping=mapping), db)
