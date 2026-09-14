from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.api.schemas import (
    AddToCartRequest,
    UpdateCartItemRequest,
    AgentActionOut,
    BatchCreate,
    BatchOut,
    BulkDecisionResolve,
    CartOut,
    ColumnMapping,
    DecisionOut,
    DecisionResolve,
    FieldEvidenceOut,
    JobOut,
    ModeResponse,
    ProductDetail,
    ProductOut,
    PublishRequest,
    ListingProvenanceOut,
    StartProcessRequest,
    StoreProductOut,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.config import get_settings
from app.db.models import (
    AgentAction,
    Batch,
    BatchKind,
    BatchStatus,
    Decision,
    DecisionKind,
    DecisionStatus,
    FieldEvidence,
    ImportRow,
    Job,
    JobStatus,
    NormalizationRule,
    Product,
    ProductImage,
    ProductReadiness,
    ProductStatus,
    ProductVersion,
    RuleScope,
    StoreProduct,
    Workspace,
)
from app.db.session import get_db
from app.policy.images import lookup_image_meta
from app.policy.readiness import refresh_product_readiness
from app.services.batch_metrics import product_list_item, recompute_batch_counts
from app.services.csv_import import (
    apply_mapping,
    parse_csv_bytes,
    suggest_column_mapping,
    validate_mapped_row,
)
from app.services.public_store import list_public_store_products, listing_provenance, to_public_store_product
from app.services.shopper_cart import (
    SHOPPER_COOKIE,
    SHOPPER_PURPOSE,
    add_store_item,
    cart_out,
    get_or_create_cart,
    parse_cart_id,
    remove_item,
    set_item_quantity,
)
from app.storage.local import LocalStorage, StorageError

router = APIRouter(dependencies=[Depends(require_auth)])
public_router = APIRouter()


def get_workspace(db: Session) -> Workspace:
    ws = db.scalar(select(Workspace).limit(1))
    if not ws:
        raise HTTPException(500, "Workspace not seeded")
    return ws


def _mode_response() -> ModeResponse:
    settings = get_settings()
    agent = settings.agent_mode
    lookup = settings.lookup_provider
    if agent == "replay":
        label = "Fixture replay mode"
        if lookup == "replay":
            label = "Fixture replay · replay lookup"
    else:
        label = "Live agent mode"
        if lookup == "replay":
            label = "Live agent · replay lookup"
        else:
            label = "Live agent · live lookup"
    return ModeResponse(
        agent_mode=agent,
        lookup_mode=lookup,
        label=label,
        is_replay=agent == "replay",
        is_live=agent == "live",
        lookup_is_replay=lookup == "replay",
    )


@public_router.get("/mode", response_model=ModeResponse)
def get_mode() -> ModeResponse:
    return _mode_response()


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
def list_batches(
    batch_kind: str | None = None,
    db: Session = Depends(get_db),
) -> list[Batch]:
    q = select(Batch).order_by(Batch.created_at.desc())
    if batch_kind:
        try:
            q = q.where(Batch.batch_kind == BatchKind(batch_kind))
        except ValueError:
            pass
    return list(db.scalars(q).all())


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
                supplier_sku=sku,
                status=ProductStatus.imported,
            )
        else:
            product = Product(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                batch_id=batch.id,
                sku=sku,
                supplier_sku=sku,
                status=ProductStatus.imported,
            )
            seen_skus[sku] = product
        if product.supplier_sku is None:
            product.supplier_sku = mapped["sku"]
        db.add(product)
        db.flush()
        row.product_id = product.id

        # Attach fixture/local image if present
        fname = mapped.get("image_filename")
        if fname:
            for img_dir in (
                fixtures_root / "seiko_images" / "originals",
                fixtures_root / "demo_images",
                fixtures_root / "images",
            ):
                src = img_dir / fname
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
                            checksum_sha256=saved.get("sha256"),
                            position=0,
                        )
                        meta = lookup_image_meta(str(fname))
                        if meta:
                            img.source_kind = meta.source_kind
                            img.usage_permission = meta.usage_permission
                        db.add(img)
                        break
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
def start_publish(
    batch_id: uuid.UUID,
    body: PublishRequest | None = None,
    db: Session = Depends(get_db),
) -> Job:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    settings = get_settings()
    checkpoint: dict[str, Any] = {}
    if body and body.product_ids:
        checkpoint["product_ids"] = [str(pid) for pid in body.product_ids]
    job = Job(
        id=uuid.uuid4(),
        batch_id=batch.id,
        job_type="publish",
        status=JobStatus.pending,
        agent_mode=settings.agent_mode,
        checkpoint=checkpoint,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/batches/{batch_id}/products", response_model=list[ProductOut])
def list_products(
    batch_id: uuid.UUID,
    readiness: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> list[ProductOut]:
    products = db.scalars(
        select(Product).where(Product.batch_id == batch_id).order_by(Product.sku)
    ).all()
    items = [product_list_item(db, p) for p in products]
    if readiness:
        items = [i for i in items if i.get("readiness") == readiness]
    if search:
        q = search.lower()
        items = [
            i
            for i in items
            if q in (i.get("title") or "").lower()
            or q in (i.get("sku") or "").lower()
            or q in (i.get("supplier_sku") or "").lower()
        ]
    return [ProductOut(**i) for i in items]


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> ProductDetail:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    version = db.get(ProductVersion, product.current_version_id) if product.current_version_id else None
    row = db.scalar(select(ImportRow).where(ImportRow.product_id == product.id).limit(1))
    evidence = db.scalars(select(FieldEvidence).where(FieldEvidence.product_id == product.id)).all()
    decisions = db.scalars(
        select(Decision).where(Decision.product_id == product.id, Decision.status == DecisionStatus.pending)
    ).all()
    base = product_list_item(db, product)
    return ProductDetail(
        **base,
        original=version.original if version else None,
        proposed=version.proposed if version else None,
        seo=version.seo if version else None,
        diffs=version.diffs if version else [],
        blockers=version.blockers if version else [],
        provenance=version.provenance if version else {},
        is_publishable=version.is_publishable if version else False,
        import_row_number=row.row_number if row else None,
        images=[
            {
                "id": str(i.id),
                "path": i.derivative_path or i.original_path,
                "class": i.image_class.value,
                "is_primary": i.is_primary,
                "classification_source": i.classification_source,
                "source_kind": i.source_kind,
                "usage_permission": i.usage_permission,
                "suitability": i.suitability,
                "source_url": i.source_url,
                "match_rationale": i.match_rationale,
                "checksum_sha256": i.checksum_sha256,
            }
            for i in product.images
        ],
        field_evidence=[FieldEvidenceOut.model_validate(e) for e in evidence],
        decisions=[DecisionOut.model_validate(d) for d in decisions],
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

    # Block approve-null for decisions that require a value
    requires_value = {
        DecisionKind.missing_price,
        DecisionKind.accept_enrichment,
    }
    requires_edit = {
        DecisionKind.unknown_brand_alias,
        DecisionKind.unknown_color_alias,
        DecisionKind.ambiguous_category,
    }

    if body.action == "approve":
        if decision.kind in requires_value and decision.proposed_value is None:
            raise HTTPException(400, "Cannot approve without a proposed value; use edit to supply one.")
        if decision.kind in requires_edit:
            raise HTTPException(400, "Cannot approve alias/category without a value; use edit.")
        decision.status = DecisionStatus.approved
        if decision.product_id:
            product = db.get(Product, decision.product_id)
            if product and decision.kind == DecisionKind.suspicious_price:
                version = db.get(ProductVersion, decision.product_version_id)
                if version:
                    version.is_publishable = True
            if product and decision.kind == DecisionKind.accept_enrichment and decision.proposed_value is not None:
                version = db.get(ProductVersion, product.current_version_id)
                if version and decision.field_name == "primary_image":
                    from app.services.manufacturer_recovery import accept_retrieved_image

                    accept_retrieved_image(db, product, str(decision.proposed_value))
                elif version and decision.field_name:
                    proposed = dict(version.proposed)
                    proposed[decision.field_name] = decision.proposed_value
                    version.proposed = proposed
                    product.approved_version_id = None
            if product and decision.kind == DecisionKind.no_primary_image and decision.proposed_value:
                from app.services.manufacturer_recovery import accept_retrieved_image

                accept_retrieved_image(db, product, str(decision.proposed_value))
            if product and decision.kind == DecisionKind.conflicting_variant and decision.proposed_value is not None:
                version = db.get(ProductVersion, product.current_version_id)
                if version and decision.field_name and decision.field_name != "primary_image":
                    proposed = dict(version.proposed)
                    proposed[decision.field_name] = decision.proposed_value
                    version.proposed = proposed
                    product.approved_version_id = None
            if product and decision.kind == DecisionKind.confirm_product_match:
                product.approved_version_id = None
    elif body.action == "edit":
        if body.edited_value is None and decision.kind in {DecisionKind.missing_price, *requires_edit}:
            raise HTTPException(400, "Edited value is required for this decision.")
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
                    elif field and body.edited_value is not None:
                        proposed[field] = body.edited_value
                    version.proposed = proposed
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
                        version.is_publishable = result["is_publishable"] and not pending
                        product.status = (
                            ProductStatus.ready if result["is_publishable"] and not pending else ProductStatus.needs_review
                        )
                    refresh_product_readiness(db, product)

    batch = db.get(Batch, decision.batch_id)
    if batch:
        recompute_batch_counts(db, batch)

    if decision.product_id:
        remaining = db.scalars(
            select(Decision).where(
                Decision.product_id == decision.product_id,
                Decision.status == DecisionStatus.pending,
            )
        ).all()
        if not remaining:
            from app.agent.hooks import record_agent_event
            from app.agent.runner import enqueue_resume_job
            from app.agent.tools import ToolContext, set_tool_context

            latest = db.scalars(
                select(Job).where(Job.batch_id == decision.batch_id).order_by(Job.created_at.desc())
            ).first()
            agent_mode = latest.agent_mode if latest else get_settings().agent_mode
            # Replay already applied the edit in this request. Live needs the agent
            # to continue with updated DB context for the affected product only.
            if agent_mode == "live":
                resume = enqueue_resume_job(
                    db, batch, [str(decision.product_id)], agent_mode=agent_mode
                )
                if resume and latest:
                    ctx = ToolContext(db, latest, batch)
                    set_tool_context(ctx)
                    try:
                        record_agent_event(
                            "resumed",
                            product_id=str(decision.product_id),
                            detail=f"decision {decision.id} resolved → resume {resume.id}",
                        )
                    finally:
                        set_tool_context(None)

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


@public_router.get("/store/products", response_model=list[StoreProductOut])
@router.get("/store/products", response_model=list[StoreProductOut])
def store_list(db: Session = Depends(get_db)) -> list[StoreProductOut]:
    rows = list_public_store_products(db)
    return [to_public_store_product(sp) for sp in rows]


@public_router.get("/store/products/{slug}", response_model=StoreProductOut)
@router.get("/store/products/{slug}", response_model=StoreProductOut)
def store_get(slug: str, db: Session = Depends(get_db)) -> StoreProductOut:
    sp = db.scalar(select(StoreProduct).where(StoreProduct.slug == slug))
    if not sp:
        raise HTTPException(404, "Not found")
    return to_public_store_product(sp)


@public_router.get("/store/products/{slug}/provenance", response_model=ListingProvenanceOut)
def store_provenance(slug: str, db: Session = Depends(get_db)) -> ListingProvenanceOut:
    sp = db.scalar(select(StoreProduct).where(StoreProduct.slug == slug))
    if not sp:
        raise HTTPException(404, "Not found")
    return listing_provenance(db, sp)


def _set_shopper_cookie(response: Response, cart_id: uuid.UUID) -> None:
    response.set_cookie(
        SHOPPER_COOKIE,
        str(cart_id),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


@public_router.post("/store/cart/items", response_model=CartOut)
def add_shopper_cart_item(
    body: AddToCartRequest,
    response: Response,
    sr_shopper_cart: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> CartOut:
    if body.purpose == "verification":
        raise HTTPException(400, "Verification carts cannot be used from the storefront")
    ws = get_workspace(db)
    sp = db.get(StoreProduct, body.store_product_id)
    if not sp:
        raise HTTPException(404, "Product not found")
    cart = get_or_create_cart(
        db, ws, purpose=SHOPPER_PURPOSE, cart_id=parse_cart_id(sr_shopper_cart)
    )
    add_store_item(db, cart, sp, body.quantity)
    db.commit()
    db.refresh(cart)
    _set_shopper_cookie(response, cart.id)
    return cart_out(db, cart)


@public_router.patch("/store/cart/items/{store_product_id}", response_model=CartOut)
def update_shopper_cart_item(
    store_product_id: uuid.UUID,
    body: UpdateCartItemRequest,
    response: Response,
    sr_shopper_cart: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> CartOut:
    cart_id = parse_cart_id(sr_shopper_cart)
    if not cart_id:
        raise HTTPException(404, "Cart not found")
    ws = get_workspace(db)
    cart = get_or_create_cart(db, ws, purpose=SHOPPER_PURPOSE, cart_id=cart_id)
    set_item_quantity(db, cart, store_product_id, body.quantity)
    db.commit()
    db.refresh(cart)
    _set_shopper_cookie(response, cart.id)
    return cart_out(db, cart)


@public_router.delete("/store/cart/items/{store_product_id}", response_model=CartOut)
def delete_shopper_cart_item(
    store_product_id: uuid.UUID,
    response: Response,
    sr_shopper_cart: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> CartOut:
    cart_id = parse_cart_id(sr_shopper_cart)
    if not cart_id:
        raise HTTPException(404, "Cart not found")
    ws = get_workspace(db)
    cart = get_or_create_cart(db, ws, purpose=SHOPPER_PURPOSE, cart_id=cart_id)
    remove_item(db, cart, store_product_id)
    db.commit()
    db.refresh(cart)
    _set_shopper_cookie(response, cart.id)
    return cart_out(db, cart)


@public_router.get("/store/cart", response_model=CartOut)
def get_shopper_cart(
    response: Response,
    sr_shopper_cart: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> CartOut:
    cart_id = parse_cart_id(sr_shopper_cart)
    if not cart_id:
        return CartOut(id=uuid.uuid4(), purpose=SHOPPER_PURPOSE, items=[])
    ws = get_workspace(db)
    cart = get_or_create_cart(db, ws, purpose=SHOPPER_PURPOSE, cart_id=cart_id)
    db.commit()
    _set_shopper_cookie(response, cart.id)
    return cart_out(db, cart)


@router.post("/store/cart/items", response_model=CartOut)
def add_to_cart(body: AddToCartRequest, db: Session = Depends(get_db)) -> CartOut:
    if body.purpose == "verification":
        raise HTTPException(400, "Verification carts are created only by publication verification")
    if body.purpose == SHOPPER_PURPOSE:
        raise HTTPException(400, "Use the public storefront cart for shopper items")
    ws = get_workspace(db)
    sp = db.get(StoreProduct, body.store_product_id)
    if not sp:
        raise HTTPException(404, "Product not found")
    cart = get_or_create_cart(db, ws, purpose=body.purpose or "operator")
    add_store_item(db, cart, sp, body.quantity)
    db.commit()
    db.refresh(cart)
    return cart_out(db, cart)


@router.get("/store/cart", response_model=CartOut)
def get_cart(purpose: str = "operator", db: Session = Depends(get_db)) -> CartOut:
    if purpose in {SHOPPER_PURPOSE, "verification"}:
        raise HTTPException(400, "Shopper and verification carts are not shared with operator carts")
    ws = get_workspace(db)
    cart = get_or_create_cart(db, ws, purpose=purpose)
    db.commit()
    db.refresh(cart)
    return cart_out(db, cart)


def import_fixture_batch(
    db: Session,
    *,
    csv_name: str,
    batch_name: str,
    supplier_name: str,
    batch_kind: BatchKind,
) -> Batch:
    settings = get_settings()
    fixtures = Path(settings.fixtures_root)
    if not fixtures.is_absolute():
        alt = Path(__file__).resolve().parents[4] / "fixtures"
        fixtures = alt if alt.exists() else Path.cwd() / fixtures
    csv_path = fixtures / csv_name
    if not csv_path.exists():
        raise HTTPException(500, f"Fixture CSV missing at {csv_path}")
    ws = get_workspace(db)
    batch = Batch(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name=batch_name,
        supplier_name=supplier_name,
        status=BatchStatus.draft,
        batch_kind=batch_kind,
        counts={},
    )
    db.add(batch)
    db.commit()
    data = csv_path.read_bytes()
    headers, rows = parse_csv_bytes(data)
    mapping = suggest_column_mapping(headers)
    batch.column_mapping = mapping
    batch.source_filename = csv_name
    for i, raw in enumerate(rows, start=1):
        db.add(ImportRow(id=uuid.uuid4(), batch_id=batch.id, row_number=i, raw=raw))
    db.commit()
    return commit_import(batch.id, StartProcessRequest(column_mapping=mapping), db)


@router.post("/demo/load-sample", response_model=BatchOut)
def load_sample_batch(db: Session = Depends(get_db)) -> Batch:
    """Load the bundled synthetic supplier CSV into a new batch and import products."""
    return import_fixture_batch(
        db,
        csv_name="supplier_catalog.csv",
        batch_name=f"Stress-test catalog · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        supplier_name="Northwind Synthetic Supply",
        batch_kind=BatchKind.stress_test,
    )


@router.post("/demo/load-seiko", response_model=BatchOut)
def load_seiko_batch(db: Session = Depends(get_db)) -> Batch:
    """Load the Seiko demonstration catalog (hero starts without an image)."""
    return import_fixture_batch(
        db,
        csv_name="seiko_demo_catalog.csv",
        batch_name=f"Seiko demonstration · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        supplier_name="Pacific Watch Distributors",
        batch_kind=BatchKind.demo,
    )


@router.post("/demo/load-demo", response_model=BatchOut)
def load_demo_batch(db: Session = Depends(get_db)) -> Batch:
    """Load the household demonstration catalog with real barcodes and labeled scenarios."""
    return import_fixture_batch(
        db,
        csv_name="demo_catalog.csv",
        batch_name=f"Household demo · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        supplier_name="Household Essentials Co.",
        batch_kind=BatchKind.demo,
    )
