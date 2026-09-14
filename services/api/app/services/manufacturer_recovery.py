"""Runtime manufacturer-record retrieval for missing images and supported specs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import (
    Decision,
    DecisionKind,
    DecisionStatus,
    EvidenceAcceptance,
    FieldEvidence,
    ImageClass,
    MatchOutcome,
    Product,
    ProductImage,
    ProductStatus,
    ProductVersion,
)
from app.enrichment.seiko import parse_seiko_product_page, registry_entry
from app.policy.images import MANUFACTURER_DEMO_CAPTION
from app.policy.readiness import refresh_product_readiness
from app.policy.safe_fetch import (
    MAX_HTML_BYTES,
    MAX_IMAGE_BYTES,
    FetchError,
    fetch_bytes,
)
from app.policy.validate import compute_diffs, validate_product_fields
from app.policy.watch_specs import (
    WATCH_SPEC_FIELDS,
    model_token_in_asset,
    normalize_model_reference,
    normalize_water_resistance,
)
from app.storage.local import LocalStorage, StorageError

USAGE_DEMO_ONLY = "demo_storefront_only"
USAGE_UNRESOLVED = "republication_not_established"
SOURCE_KIND = "manufacturer_product_page"
PROVIDER = "seiko_manufacturer"

RECOVERY_STEP_ORDER = (
    "image_not_supplied",
    "looking_up_manufacturer",
    "matching_model",
    "downloading_image",
    "image_ready_for_review",
    "image_accepted",
)


def _fixtures_root() -> Path:
    settings = get_settings()
    fixtures = Path(settings.fixtures_root)
    if not fixtures.is_absolute():
        alt = Path(__file__).resolve().parents[4] / "fixtures"
        fixtures = alt if alt.exists() else Path.cwd() / fixtures
    return fixtures


def _retrieval_mode_default() -> str:
    return "replay" if get_settings().lookup_provider == "replay" else "network"


def _step(step_id: str, **extra: Any) -> dict[str, Any]:
    return {"id": step_id, "occurred": True, "at": datetime.now(timezone.utc).isoformat(), **extra}


def retrieve_manufacturer_record(db: Session, product: Product, *, force_mode: str | None = None) -> dict[str, Any]:
    """Look up the manufacturer page for the exact model, persist evidence and optional asset."""
    if not product.current_version_id:
        return {"ok": False, "error": "missing_revision"}
    version = db.get(ProductVersion, product.current_version_id)
    if not version:
        return {"ok": False, "error": "missing_revision"}

    original = dict(version.original or {})
    proposed = dict(version.proposed or {})
    steps: list[dict[str, Any]] = []
    mode = force_mode or _retrieval_mode_default()

    has_image = bool(product.images) or bool(original.get("image_filename"))
    if not has_image:
        steps.append(_step("image_not_supplied"))

    brand = (original.get("brand") or proposed.get("brand") or "").strip()
    model = normalize_model_reference(original.get("model") or proposed.get("model") or original.get("mpn"))
    if not model:
        _persist_identity_gap(db, product, version, original)
        steps.append(_step("matching_model", status="ambiguous_reference"))
        _store_recovery_provenance(version, steps, mode, error="ambiguous_reference")
        refresh_product_readiness(db, product)
        db.flush()
        return {
            "ok": False,
            "error": "ambiguous_reference",
            "steps": steps,
            "retrieval_mode": mode,
            "source_provider": PROVIDER,
        }

    fixtures = _fixtures_root()
    entry = registry_entry(fixtures, model)
    steps.append(_step("looking_up_manufacturer", model=model, retrieval_mode=mode))
    if entry is None:
        _persist_no_match(db, product, version, original, model)
        steps.append(_step("matching_model", status="no_exact_match"))
        _store_recovery_provenance(version, steps, mode, error="no_exact_match")
        refresh_product_readiness(db, product)
        db.flush()
        return {
            "ok": False,
            "error": "no_exact_match",
            "model": model,
            "steps": steps,
            "retrieval_mode": mode,
            "source_provider": PROVIDER,
        }

    page_url = entry["source_page"]
    try:
        html, page_mode = _load_html(entry, fixtures, mode)
    except FetchError as exc:
        _persist_fetch_failure(db, product, version, original, model, page_url, str(exc.code), mode)
        _store_recovery_provenance(version, steps, mode, error=str(exc.code))
        db.flush()
        return {
            "ok": False,
            "error": str(exc.code),
            "detail": exc.detail,
            "steps": steps,
            "retrieval_mode": mode,
            "source_provider": PROVIDER,
        }

    try:
        record = parse_seiko_product_page(html, page_url, expected_model=model)
    except ValueError as exc:
        _store_recovery_provenance(version, steps, page_mode, error=str(exc))
        db.flush()
        return {"ok": False, "error": str(exc), "steps": steps, "retrieval_mode": page_mode}

    if record.model != model:
        steps.append(_step("matching_model", status="page_model_mismatch"))
        _store_recovery_provenance(version, steps, page_mode, error="page_model_mismatch")
        db.flush()
        return {"ok": False, "error": "page_model_mismatch", "steps": steps, "retrieval_mode": page_mode}

    steps.append(
        _step(
            "matching_model",
            status="exact_model_match",
            manufacturer_reference=record.model,
            catalog_asset_code=record.catalog_asset_code,
        )
    )

    evidence_ids = _persist_spec_evidence(db, product, version, original, record, page_mode)
    proposed.update({k: v for k, v in record.specifications.items() if v})
    proposed["manufacturer_reference"] = record.model
    if not proposed.get("title"):
        proposed["title"] = f"Seiko 5 Sports {record.model}"
    if record.specifications.get("water_resistance"):
        proposed["water_resistance"] = normalize_water_resistance(record.specifications["water_resistance"])
        proposed["water_resistance_note"] = (
            "Manufacturer water-resistance wording only. Not a diving or swimming claim."
        )

    image_result: dict[str, Any] = {"skipped": True}
    if not has_image:
        image_result = _retrieve_image(
            db,
            product,
            version,
            original,
            record,
            entry,
            fixtures,
            page_mode,
            steps,
        )
        if image_result.get("asset_id"):
            evidence_ids.append(image_result["evidence_id"])
    elif product.images:
        mismatch = _flag_wrong_variant_images(db, product, version, original, model)
        if mismatch:
            image_result = mismatch

    version.proposed = proposed
    version.diffs = compute_diffs(original, proposed)
    seo = dict(version.seo or {})
    if proposed.get("title") and not seo.get("product_title"):
        from app.policy.seo import build_seo_draft

        rebuilt = build_seo_draft(proposed)
        if product.store_slug:
            rebuilt["url_slug"] = product.store_slug
        version.seo = rebuilt
    provenance = dict(version.provenance or {})
    provenance["manufacturer_source"] = {
        "provider": PROVIDER,
        "retrieval_mode": page_mode,
        "source_page": page_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "agent_mode": get_settings().agent_mode,
        "lookup_mode": get_settings().lookup_provider,
    }
    version.provenance = provenance
    _store_recovery_provenance(version, steps, page_mode)
    _refresh_publishability(db, product, version)
    refresh_product_readiness(db, product)
    db.flush()
    return {
        "ok": True,
        "product_id": str(product.id),
        "revision_id": str(version.id),
        "manufacturer_reference": record.model,
        "source_page": page_url,
        "evidence_ids": evidence_ids,
        "asset_id": image_result.get("asset_id"),
        "image_error": image_result.get("error"),
        "steps": steps,
        "retrieval_mode": page_mode,
        "source_provider": PROVIDER,
        "specifications": record.specifications,
        "identity_match": "exact_model_match",
    }


def accept_retrieved_image(db: Session, product: Product, image_id: str | uuid.UUID) -> dict[str, Any]:
    image = db.get(ProductImage, uuid.UUID(str(image_id)))
    if image is None or image.product_id != product.id:
        return {"ok": False, "error": "unknown_asset"}
    if image.usage_permission not in {USAGE_DEMO_ONLY, "demonstration_only"}:
        return {"ok": False, "error": "usage_not_permitted"}
    if image.suitability == "model_mismatch":
        return {"ok": False, "error": "model_mismatch"}
    for other in product.images:
        other.is_primary = False
    image.is_primary = True
    image.product_version_id = product.current_version_id
    version = db.get(ProductVersion, product.current_version_id) if product.current_version_id else None
    if version:
        proposed = dict(version.proposed)
        proposed["primary_image_id"] = str(image.id)
        version.proposed = proposed
        provenance = dict(version.provenance or {})
        recovery = dict(provenance.get("manufacturer_recovery") or {})
        steps = list(recovery.get("steps") or [])
        if not any(s.get("id") == "image_accepted" for s in steps):
            steps.append(_step("image_accepted", asset_id=str(image.id)))
        recovery["steps"] = steps
        provenance["manufacturer_recovery"] = recovery
        version.provenance = provenance
        _refresh_publishability(db, product, version)
    for ev in db.scalars(select(FieldEvidence).where(FieldEvidence.product_id == product.id, FieldEvidence.field_name == "primary_image")):
        ev.acceptance_status = EvidenceAcceptance.accepted
    for decision in db.scalars(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.status == DecisionStatus.pending,
            Decision.field_name == "primary_image",
        )
    ):
        if str(decision.proposed_value) == str(image.id) or decision.kind == DecisionKind.no_primary_image:
            decision.status = DecisionStatus.approved
            decision.proposed_value = str(image.id)
    refresh_product_readiness(db, product)
    db.flush()
    return {"ok": True, "asset_id": str(image.id)}


def _load_html(entry: dict[str, Any], fixtures: Path, mode: str) -> tuple[str, str]:
    if mode == "replay":
        html_path = fixtures / entry["replay_html"]
        if not html_path.exists():
            raise FetchError("replay_html_missing", str(html_path))
        return html_path.read_text(encoding="utf-8", errors="replace"), "replay"
    body, _final, ctype = fetch_bytes(
        entry["source_page"],
        max_bytes=MAX_HTML_BYTES,
        allowed_types=frozenset({"text/html", "application/xhtml+xml", ""}),
    )
    if ctype and ctype not in {"text/html", "application/xhtml+xml"}:
        raise FetchError("unsupported_content_type", ctype)
    return body.decode("utf-8", errors="replace"), "network"


def _retrieve_image(
    db: Session,
    product: Product,
    version: ProductVersion,
    original: dict[str, Any],
    record,
    entry: dict[str, Any],
    fixtures: Path,
    mode: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    if not record.image_candidates and mode != "replay":
        steps.append(_step("downloading_image", status="missing_on_source_page"))
        return {"error": "missing_image_on_source_page"}

    existing = db.scalars(
        select(ProductImage).where(ProductImage.product_id == product.id, ProductImage.source_kind == SOURCE_KIND)
    ).all()

    steps.append(_step("downloading_image", candidate_count=len(record.image_candidates)))
    data, source_url, retrieval_mode = _load_image_bytes(record, entry, fixtures, mode)
    sha256 = __import__("hashlib").sha256(data).hexdigest()
    for img in existing:
        if img.checksum_sha256 == sha256:
            _ensure_image_decision(db, product, version, img, record, retrieval_mode)
            steps.append(_step("image_ready_for_review", asset_id=str(img.id), deduplicated=True))
            return {"asset_id": str(img.id), "evidence_id": _image_evidence_id(db, product, img), "deduplicated": True}

    storage = LocalStorage()
    try:
        saved = storage.save_image(data, filename=Path(urlparse(source_url).path).name or "seiko.png", subdirectory=f"products/{product.id}")
    except StorageError as exc:
        return {"error": str(exc)}

    associated = model_token_in_asset(record.model, source_url) or model_token_in_asset(
        record.model, saved["original_path"]
    )
    suitability = "source_model_match" if associated else "model_mismatch"
    img = ProductImage(
        id=uuid.uuid4(),
        product_id=product.id,
        product_version_id=version.id,
        original_path=saved["original_path"],
        derivative_path=saved["derivative_path"],
        mime_type=saved["mime_type"],
        width=saved["width"],
        height=saved["height"],
        size_bytes=saved["size_bytes"],
        checksum_sha256=saved.get("sha256") or sha256,
        position=0,
        image_class=ImageClass.product_only,
        is_primary=False,
        classification_source="source_association_and_manual_fixture_review",
        source_kind=SOURCE_KIND,
        usage_permission=USAGE_DEMO_ONLY,
        suitability=suitability,
        source_url=source_url,
        match_rationale=(
            f"Official {record.model} page asset {record.catalog_asset_code or ''} "
            f"(source association). Manual review of the downloaded file confirmed "
            f"dial/bezel/bracelet against that page's product photograph. "
            f"Not an independent authenticity check. Usage: {USAGE_UNRESOLVED} commercially; "
            f"{USAGE_DEMO_ONLY} for this isolated demonstration."
        ),
    )
    db.add(img)
    db.flush()
    ev = FieldEvidence(
        id=uuid.uuid4(),
        product_id=product.id,
        product_version_id=version.id,
        field_name="primary_image",
        original_supplier_value=original.get("image_filename"),
        proposed_value=str(img.id),
        source_provider=PROVIDER,
        source_url=record.source_page,
        provider_record_id=record.catalog_asset_code,
        lookup_identifier=record.model,
        lookup_query=record.model,
        match_outcome=MatchOutcome.matching_evidence if associated else MatchOutcome.conflicting_evidence,
        match_explanation=img.match_rationale or "",
        acceptance_status=EvidenceAcceptance.pending,
        is_cached=retrieval_mode == "cache",
        is_replay=retrieval_mode == "replay",
        raw_response={
            "image_url": source_url,
            "sha256": img.checksum_sha256,
            "retrieval_mode": retrieval_mode,
            "usage_permission": USAGE_DEMO_ONLY,
            "commercial_republication": USAGE_UNRESOLVED,
            "visual_review": "manual_review_of_downloaded_file",
        },
    )
    db.add(ev)
    db.flush()
    _ensure_image_decision(db, product, version, img, record, retrieval_mode, evidence_id=str(ev.id))
    if associated:
        steps.append(_step("image_ready_for_review", asset_id=str(img.id), evidence_id=str(ev.id)))
    return {"asset_id": str(img.id), "evidence_id": str(ev.id), "error": None if associated else "model_mismatch"}


def _load_image_bytes(record, entry: dict[str, Any], fixtures: Path, mode: str) -> tuple[bytes, str, str]:
    if mode == "replay":
        path = fixtures / entry["replay_image"]
        if not path.exists():
            raise FetchError("replay_image_missing", str(path))
        source = record.image_candidates[0] if record.image_candidates else entry.get("source_page", "")
        return path.read_bytes(), source, "replay"
    if not record.image_candidates:
        raise FetchError("missing_image_on_source_page")
    url = record.image_candidates[0]
    body, final, ctype = fetch_bytes(
        url,
        max_bytes=MAX_IMAGE_BYTES,
        allowed_types=frozenset({"image/png", "image/jpeg", "image/webp", "image/jpg"}),
    )
    if ctype not in {"image/png", "image/jpeg", "image/webp", "image/jpg"}:
        raise FetchError("unsupported_content_type", ctype)
    return body, final, "network"


def _persist_spec_evidence(
    db: Session,
    product: Product,
    version: ProductVersion,
    original: dict[str, Any],
    record,
    mode: str,
) -> list[str]:
    ids: list[str] = []
    for field, value in record.specifications.items():
        if field not in WATCH_SPEC_FIELDS and field != "manufacturer_reference":
            continue
        supplier_val = original.get(field)
        if field == "manufacturer_reference":
            supplier_val = original.get("model")
        if supplier_val in (None, "", value):
            outcome = MatchOutcome.matching_evidence
            explanation = (
                f"Manufacturer page for {record.model} lists {field} as {value}."
                if supplier_val in (None, "")
                else f"{field} agrees with manufacturer page ({value})."
            )
        else:
            # Compare normalized water resistance / diameter loosely
            if field == "water_resistance" and normalize_water_resistance(str(supplier_val)) == normalize_water_resistance(value):
                outcome = MatchOutcome.matching_evidence
                explanation = f"Water resistance wording normalized; manufacturer page lists {value}."
            elif str(supplier_val).replace(" ", "") == str(value).replace(" ", ""):
                outcome = MatchOutcome.matching_evidence
                explanation = f"{field} matches manufacturer page after spacing normalization."
            else:
                outcome = MatchOutcome.conflicting_evidence
                explanation = (
                    f"Supplier {field} is '{supplier_val}'; manufacturer page for {record.model} lists '{value}'."
                )
        existing = db.scalar(
            select(FieldEvidence).where(
                FieldEvidence.product_id == product.id,
                FieldEvidence.product_version_id == version.id,
                FieldEvidence.field_name == field,
                FieldEvidence.source_provider == PROVIDER,
            )
        )
        if existing:
            ids.append(str(existing.id))
            if outcome == MatchOutcome.conflicting_evidence:
                _ensure_conflict_decision(db, product, version, field, supplier_val, value, str(existing.id), explanation)
            continue
        ev = FieldEvidence(
            id=uuid.uuid4(),
            product_id=product.id,
            product_version_id=version.id,
            field_name=field,
            original_supplier_value=supplier_val,
            proposed_value=value if outcome != MatchOutcome.conflicting_evidence else value,
            source_provider=PROVIDER,
            source_url=record.source_page,
            provider_record_id=record.model,
            lookup_identifier=record.model,
            lookup_query=record.model,
            match_outcome=outcome,
            match_explanation=explanation,
            acceptance_status=EvidenceAcceptance.pending,
            is_replay=mode == "replay",
            is_cached=mode == "cache",
            raw_response={"retrieval_mode": mode, "spec_field": field},
        )
        db.add(ev)
        db.flush()
        ids.append(str(ev.id))
        if outcome == MatchOutcome.conflicting_evidence:
            _ensure_conflict_decision(db, product, version, field, supplier_val, value, str(ev.id), explanation)
        elif supplier_val in (None, "") and field in WATCH_SPEC_FIELDS:
            _ensure_enrichment_decision(db, product, version, field, value, str(ev.id), explanation)
    return ids


def _ensure_image_decision(
    db: Session,
    product: Product,
    version: ProductVersion,
    image: ProductImage,
    record,
    mode: str,
    evidence_id: str | None = None,
) -> None:
    pending = db.scalars(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.status == DecisionStatus.pending,
            Decision.field_name == "primary_image",
        )
    ).all()
    payload = {
        "asset_id": str(image.id),
        "source_page": record.source_page,
        "manufacturer_reference": record.model,
        "catalog_asset_code": record.catalog_asset_code,
        "retrieval_mode": mode,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "usage_permission": image.usage_permission,
        "suitability": image.suitability,
        "match_rationale": image.match_rationale,
        "preview_path": image.derivative_path or image.original_path,
        "evidence_id": evidence_id,
        "caption": MANUFACTURER_DEMO_CAPTION,
    }
    if pending:
        for decision in pending:
            decision.proposed_value = str(image.id)
            decision.evidence = {**dict(decision.evidence or {}), **payload}
            decision.reason = (
                f"Retrieved official {record.model} product photograph. Review and accept to use it."
            )
            decision.consequence = "Accept attaches this asset to the current revision. Reject leaves the listing without a photo."
        return
    db.add(
        Decision(
            id=uuid.uuid4(),
            workspace_id=product.workspace_id,
            batch_id=product.batch_id,
            product_id=product.id,
            product_version_id=version.id,
            kind=DecisionKind.accept_enrichment,
            status=DecisionStatus.pending,
            field_name="primary_image",
            original_value=None,
            proposed_value=str(image.id),
            evidence=payload,
            reason=f"Use this manufacturer photograph for {record.model}.",
            consequence="Accept attaches the stored asset. Publication stays blocked until accepted.",
            risk_tier="review",
        )
    )


def _ensure_conflict_decision(
    db: Session,
    product: Product,
    version: ProductVersion,
    field: str,
    supplier_val: Any,
    evidence_val: Any,
    evidence_id: str,
    explanation: str,
) -> None:
    existing = db.scalar(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.kind == DecisionKind.conflicting_variant,
            Decision.field_name == field,
            Decision.status == DecisionStatus.pending,
        )
    )
    if existing:
        return
    db.add(
        Decision(
            id=uuid.uuid4(),
            workspace_id=product.workspace_id,
            batch_id=product.batch_id,
            product_id=product.id,
            product_version_id=version.id,
            kind=DecisionKind.conflicting_variant,
            status=DecisionStatus.pending,
            field_name=field,
            original_value=supplier_val,
            proposed_value=evidence_val,
            evidence={"evidence_id": evidence_id, "source_provider": PROVIDER},
            reason=explanation,
            consequence="Choose the manufacturer value or keep the supplier value. Original supplier data is preserved.",
            risk_tier="approval",
        )
    )


def _ensure_enrichment_decision(
    db: Session,
    product: Product,
    version: ProductVersion,
    field: str,
    value: Any,
    evidence_id: str,
    explanation: str,
) -> None:
    existing = db.scalar(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.kind == DecisionKind.accept_enrichment,
            Decision.field_name == field,
            Decision.status == DecisionStatus.pending,
        )
    )
    if existing:
        return
    db.add(
        Decision(
            id=uuid.uuid4(),
            workspace_id=product.workspace_id,
            batch_id=product.batch_id,
            product_id=product.id,
            product_version_id=version.id,
            kind=DecisionKind.accept_enrichment,
            status=DecisionStatus.pending,
            field_name=field,
            original_value=None,
            proposed_value=value,
            evidence={"evidence_id": evidence_id, "source_provider": PROVIDER},
            reason=explanation,
            consequence="Accept to apply this manufacturer specification to the proposed listing.",
            risk_tier="review",
        )
    )


def _flag_wrong_variant_images(
    db: Session, product: Product, version: ProductVersion, original: dict[str, Any], model: str
) -> dict[str, Any] | None:
    flagged = False
    for img in product.images:
        name = (img.original_path or "") + " " + str(original.get("image_filename") or "")
        if model_token_in_asset(model, name):
            img.suitability = "source_model_match"
            continue
        img.suitability = "model_mismatch"
        img.is_primary = False
        flagged = True
        existing = db.scalar(
            select(Decision).where(
                Decision.product_id == product.id,
                Decision.kind == DecisionKind.conflicting_variant,
                Decision.field_name == "primary_image",
                Decision.status == DecisionStatus.pending,
            )
        )
        if existing:
            continue
        db.add(
            Decision(
                id=uuid.uuid4(),
                workspace_id=product.workspace_id,
                batch_id=product.batch_id,
                product_id=product.id,
                product_version_id=version.id,
                kind=DecisionKind.conflicting_variant,
                status=DecisionStatus.pending,
                field_name="primary_image",
                original_value=original.get("image_filename"),
                proposed_value=None,
                evidence={
                    "constructed_demo_error": True,
                    "product_model": model,
                    "image_name": original.get("image_filename"),
                    "detection": "source_model_association",
                    "vision_used": False,
                },
                reason=(
                    f"Supplier image does not associate with model {model} "
                    f"(filename/source indicates a different reference). Constructed demo error."
                ),
                consequence="Do not publish with a mismatched model photo. Supply the matching asset or reject the image.",
                risk_tier="approval",
            )
        )
        db.add(
            FieldEvidence(
                id=uuid.uuid4(),
                product_id=product.id,
                product_version_id=version.id,
                field_name="primary_image",
                original_supplier_value=original.get("image_filename"),
                proposed_value=None,
                source_provider=PROVIDER,
                match_outcome=MatchOutcome.conflicting_evidence,
                match_explanation=(
                    f"Image filename does not contain model token {model}. "
                    "Mismatch detected by source/model association, not a vision model."
                ),
                acceptance_status=EvidenceAcceptance.rejected,
                is_replay=True,
                raw_response={"detection": "source_model_association"},
            )
        )
    return {"error": "model_mismatch"} if flagged else None


def _persist_identity_gap(db: Session, product: Product, version: ProductVersion, original: dict[str, Any]) -> None:
    existing = db.scalar(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.kind == DecisionKind.confirm_product_match,
            Decision.status == DecisionStatus.pending,
        )
    )
    if existing:
        return
    db.add(
        Decision(
            id=uuid.uuid4(),
            workspace_id=product.workspace_id,
            batch_id=product.batch_id,
            product_id=product.id,
            product_version_id=version.id,
            kind=DecisionKind.confirm_product_match,
            status=DecisionStatus.pending,
            field_name="model",
            original_value=original.get("model"),
            proposed_value=None,
            evidence={"reason": "ambiguous_reference"},
            reason="Supplier record does not identify an exact model. A photograph will not be guessed.",
            consequence="Provide the manufacturer reference before this product can enter the featured catalog.",
            risk_tier="approval",
        )
    )
    db.add(
        FieldEvidence(
            id=uuid.uuid4(),
            product_id=product.id,
            product_version_id=version.id,
            field_name="model",
            original_supplier_value=original.get("model"),
            proposed_value=None,
            source_provider=PROVIDER,
            match_outcome=MatchOutcome.no_match,
            match_explanation="Ambiguous reference: no exact model. No image was assigned.",
            acceptance_status=EvidenceAcceptance.rejected,
            is_replay=_retrieval_mode_default() == "replay",
        )
    )
    product.status = ProductStatus.needs_review
    version.is_publishable = False


def _persist_no_match(db: Session, product: Product, version: ProductVersion, original: dict[str, Any], model: str) -> None:
    db.add(
        FieldEvidence(
            id=uuid.uuid4(),
            product_id=product.id,
            product_version_id=version.id,
            field_name="model",
            original_supplier_value=original.get("model"),
            proposed_value=None,
            source_provider=PROVIDER,
            lookup_identifier=model,
            match_outcome=MatchOutcome.no_match,
            match_explanation=f"No manufacturer registry entry for {model}. No image guessed.",
            acceptance_status=EvidenceAcceptance.rejected,
        )
    )


def _persist_fetch_failure(
    db: Session,
    product: Product,
    version: ProductVersion,
    original: dict[str, Any],
    model: str,
    page_url: str,
    code: str,
    mode: str,
) -> None:
    db.add(
        FieldEvidence(
            id=uuid.uuid4(),
            product_id=product.id,
            product_version_id=version.id,
            field_name="primary_image",
            original_supplier_value=original.get("image_filename"),
            source_provider=PROVIDER,
            source_url=page_url,
            lookup_identifier=model,
            match_outcome=MatchOutcome.lookup_unavailable,
            match_explanation=f"Manufacturer retrieval failed: {code}.",
            is_replay=mode == "replay",
            raw_response={"error": code, "retrieval_mode": mode},
        )
    )


def _store_recovery_provenance(
    version: ProductVersion, steps: list[dict[str, Any]], mode: str, error: str | None = None
) -> None:
    provenance = dict(version.provenance or {})
    provenance["manufacturer_recovery"] = {
        "steps": steps,
        "retrieval_mode": mode,
        "source_provider": PROVIDER,
        "error": error,
    }
    version.provenance = provenance


def _refresh_publishability(db: Session, product: Product, version: ProductVersion) -> None:
    has_primary = any(i.is_primary and i.suitability != "model_mismatch" for i in product.images)
    result = validate_product_fields(dict(version.proposed), has_primary_image=has_primary)
    version.proposed = result["proposed"]
    version.blockers = result["blockers"] + [{"kind": "review", **r} for r in result["reviews"]]
    pending = db.scalars(
        select(Decision).where(Decision.product_id == product.id, Decision.status == DecisionStatus.pending)
    ).all()
    filled_title = bool(version.proposed.get("title"))
    filled_brand = bool(version.proposed.get("brand"))
    for decision in pending:
        if decision.kind == DecisionKind.other and decision.field_name == "title" and filled_title:
            decision.status = DecisionStatus.approved
            decision.proposed_value = version.proposed.get("title")
        if decision.kind == DecisionKind.other and decision.field_name == "brand" and filled_brand:
            decision.status = DecisionStatus.approved
            decision.proposed_value = version.proposed.get("brand")
    pending = [
        d
        for d in db.scalars(
            select(Decision).where(Decision.product_id == product.id, Decision.status == DecisionStatus.pending)
        ).all()
    ]
    version.is_publishable = bool(result["is_publishable"] and not pending)
    if version.is_publishable:
        product.status = ProductStatus.ready
    else:
        product.status = ProductStatus.needs_review


def _image_evidence_id(db: Session, product: Product, image: ProductImage) -> str | None:
    row = db.scalar(
        select(FieldEvidence).where(
            FieldEvidence.product_id == product.id,
            FieldEvidence.field_name == "primary_image",
            FieldEvidence.proposed_value == str(image.id),
        )
    )
    return str(row.id) if row else None
