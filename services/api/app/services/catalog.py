"""Catalog processing: normalize, validate, create decisions, SEO drafts."""

from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Decision,
    DecisionKind,
    DecisionStatus,
    ImageClass,
    NormalizationRule,
    Product,
    ProductImage,
    ProductStatus,
    ProductVersion,
)
from app.policy.images import lookup_image_meta, suitability_for
from app.policy.money import MoneyError, parse_money
from app.policy.normalize import (
    clean_whitespace,
    find_unsupported_claims,
    normalize_brand,
    normalize_category,
    normalize_colors,
    normalize_type,
)
from app.policy.readiness import refresh_product_readiness
from app.policy.seo import build_seo_draft, sanitize_supplier_text
from app.policy.validate import compute_diffs, validate_product_fields
from app.policy.watch_specs import copy_watch_fields, model_token_in_asset, normalize_water_resistance


def active_rules_map(db: Session, workspace_id: uuid.UUID, rule_type: str) -> list[tuple[str, str]]:
    rows = db.scalars(
        select(NormalizationRule).where(
            NormalizationRule.workspace_id == workspace_id,
            NormalizationRule.rule_type == rule_type,
            NormalizationRule.active.is_(True),
        )
    ).all()
    return [(r.source_value, r.target_value) for r in rows]


def process_product(
    db: Session,
    product: Product,
    original: dict[str, Any],
    *,
    median_price: Decimal | None = None,
    existing_slugs: set[str] | None = None,
    sku_conflicts: dict[str, list[uuid.UUID]] | None = None,
    exact_dup_of: uuid.UUID | None = None,
) -> ProductVersion:
    product.status = ProductStatus.processing
    brand_rules = active_rules_map(db, product.workspace_id, "brand")
    color_rules = active_rules_map(db, product.workspace_id, "color")

    brand_r = normalize_brand(original.get("brand"), brand_rules)
    color_r = normalize_colors(original.get("color"), color_rules)
    cat_r = normalize_category(original.get("category"))
    type_r = normalize_type(original.get("product_type"))

    description = sanitize_supplier_text(original.get("description"))
    claims = find_unsupported_claims(original.get("description") or "")

    proposed: dict[str, Any] = {
        "sku": clean_whitespace(original.get("sku")),
        "title": clean_whitespace(original.get("title")),
        "description": description,
        "brand": brand_r.normalized if brand_r.known else clean_whitespace(original.get("brand")),
        "brand_original": brand_r.original,
        "color_label": color_r.original,
        "color_families": color_r.normalized if color_r.known else None,
        "category": cat_r.normalized if cat_r.known else clean_whitespace(original.get("category")),
        "category_original": cat_r.original,
        "product_type": type_r.normalized,
        "price": original.get("price"),
        "currency": original.get("currency") or "USD",
        "stock": original.get("stock"),
        "image_filename": original.get("image_filename"),
        "gtin": original.get("gtin"),
        "upc": original.get("upc"),
        "ean": original.get("ean"),
        "mpn": original.get("mpn"),
        "model": original.get("model"),
        "size": original.get("size"),
        "pack_quantity": original.get("pack_quantity"),
        "demo_scenario": original.get("demo_scenario"),
    }
    proposed.update(copy_watch_fields(original))
    if proposed.get("model") and not proposed.get("manufacturer_reference"):
        proposed["manufacturer_reference"] = str(proposed["model"]).strip().upper().replace(" ", "")
    if proposed.get("water_resistance"):
        proposed["water_resistance"] = normalize_water_resistance(str(proposed["water_resistance"]))

    # Safe whitespace cleanup already applied — automatic
    provenance = {
        "brand": "alias_rule" if brand_r.known else "original",
        "color": "alias_rule" if color_r.known else "original",
        "category": "alias_rule" if cat_r.known else "original",
        "description": "sanitized_untrusted",
    }

    # Image classification / primary selection. Loading success ≠ category suitability.
    has_primary = False
    images = list(product.images)
    fname = original.get("image_filename") or ""
    product_type = original.get("product_type")
    category = original.get("category")
    if images:
        for img in images:
            stem = img.original_path.split("/")[-1]
            meta = lookup_image_meta(fname) or lookup_image_meta(stem)
            img.is_primary = False
            product_model = original.get("model")
            if meta:
                img.image_class = meta.image_class
                img.classification_source = "fixture_replay"
                img.source_kind = meta.source_kind
                img.usage_permission = meta.usage_permission
                img.suitability = suitability_for(
                    meta, product_type, category, model=str(product_model) if product_model else None
                )
            else:
                img.image_class = ImageClass.unknown
                img.classification_source = "unknown"
                img.source_kind = "unknown"
                img.usage_permission = "unknown"
                img.suitability = "unclassified"

        matching_primary = [
            i
            for i in images
            if i.image_class == ImageClass.product_only
            and i.suitability in {"category_match", "source_model_match"}
        ]
        product_only = [i for i in images if i.image_class == ImageClass.product_only]
        chosen = matching_primary or product_only
        if chosen:
            if chosen[0].suitability == "model_mismatch":
                has_primary = False
            else:
                chosen[0].is_primary = True
                has_primary = True
        else:
            has_primary = False

    version_number = len(product.versions) + 1
    seo = build_seo_draft(proposed, existing_slugs=existing_slugs)
    result = validate_product_fields(
        proposed,
        currency=proposed.get("currency") or "USD",
        median_price=median_price,
        require_primary_image=True,
        has_primary_image=has_primary or not original.get("image_filename"),
    )
    # If no image filename at all, still need review for missing primary
    if not images and original.get("image_filename"):
        result["blockers"].append(
            {
                "kind": "no_primary_image",
                "field": "primary_image",
                "reason": "Referenced image file was not found or failed validation.",
                "value": original.get("image_filename"),
            }
        )
        result["is_publishable"] = False
    if not images and not original.get("image_filename"):
        result["blockers"].append(
            {
                "kind": "no_primary_image",
                "field": "primary_image",
                "reason": "No suitable primary product image.",
                "value": None,
            }
        )
        result["is_publishable"] = False

    # Override has_primary_image check when we have product_only
    if images and not has_primary:
        # already blocked above via validate if require_primary
        pass

    proposed = result["proposed"]
    diffs = compute_diffs(original, proposed)
    version = ProductVersion(
        id=uuid.uuid4(),
        product_id=product.id,
        version_number=version_number,
        original=original,
        proposed=proposed,
        seo=seo,
        diffs=diffs,
        provenance=provenance,
        is_publishable=result["is_publishable"],
        blockers=result["blockers"] + [{"kind": "review", **r} for r in result["reviews"]],
    )
    db.add(version)
    db.flush()
    product.current_version_id = version.id

    decisions: list[Decision] = []

    def add_decision(
        kind: DecisionKind,
        *,
        field: str | None,
        original_value: Any,
        proposed_value: Any,
        reason: str,
        consequence: str,
        risk_tier: str,
        bulk_key: str | None = None,
        evidence: dict | None = None,
    ) -> None:
        d = Decision(
            id=uuid.uuid4(),
            workspace_id=product.workspace_id,
            batch_id=product.batch_id,
            product_id=product.id,
            product_version_id=version.id,
            kind=kind,
            status=DecisionStatus.pending,
            field_name=field,
            original_value=original_value,
            proposed_value=proposed_value,
            evidence=evidence or {},
            reason=reason,
            consequence=consequence,
            risk_tier=risk_tier,
            bulk_key=bulk_key,
        )
        db.add(d)
        decisions.append(d)

    if brand_r.needs_decision:
        add_decision(
            DecisionKind.unknown_brand_alias,
            field="brand",
            original_value=brand_r.original,
            proposed_value=None,
            reason="Unknown brand alias; will not invent a canonical brand.",
            consequence="If approved with a target brand, a workspace rule can be saved. Reject keeps original.",
            risk_tier="review",
            bulk_key=f"brand:{brand_r.original.lower()}",
            evidence={"source": "normalize_brand"},
        )
    if color_r.needs_decision:
        add_decision(
            DecisionKind.unknown_color_alias,
            field="color",
            original_value=color_r.original,
            proposed_value=None,
            reason="Unknown color mapping; original label preserved.",
            consequence="Approve with color families to save a rule, or reject to keep supplier label only.",
            risk_tier="review",
            bulk_key=f"color:{color_r.original.lower()}",
        )
    if cat_r.needs_decision:
        add_decision(
            DecisionKind.ambiguous_category,
            field="category",
            original_value=cat_r.original,
            proposed_value=None,
            reason="Category could not be mapped to a known taxonomy value.",
            consequence="Product stays in needs_review until a category is chosen.",
            risk_tier="review",
        )

    for blocker in result["blockers"]:
        kind_map = {
            "missing_price": DecisionKind.missing_price,
            "no_primary_image": DecisionKind.no_primary_image,
            "invalid_stock": DecisionKind.other,
            "invalid_price": DecisionKind.other,
            "missing_field": DecisionKind.other,
        }
        kind = kind_map.get(blocker["kind"], DecisionKind.other)
        add_decision(
            kind,
            field=blocker.get("field"),
            original_value=blocker.get("value"),
            proposed_value=None,
            reason=blocker["reason"],
            consequence="Publication is blocked until resolved.",
            risk_tier="approval" if kind == DecisionKind.missing_price else "review",
        )

    for review in result["reviews"]:
        if review["kind"] == "suspicious_price":
            add_decision(
                DecisionKind.suspicious_price,
                field="price",
                original_value=review.get("value"),
                proposed_value=review.get("value"),
                reason=review["reason"],
                consequence="If approved, price is accepted for publication eligibility.",
                risk_tier="approval",
            )

    if claims:
        add_decision(
            DecisionKind.unsupported_claim,
            field="description",
            original_value=original.get("description"),
            proposed_value=description,
            reason=f"Unsupported or untrusted claim/instruction detected: {', '.join(claims)}",
            consequence="Supplier text treated as untrusted; claims will not be published as facts.",
            risk_tier="review",
            evidence={"matches": claims},
        )

    if exact_dup_of:
        add_decision(
            DecisionKind.exact_duplicate,
            field="sku",
            original_value=str(product.id),
            proposed_value=str(exact_dup_of),
            reason="Exact duplicate row detected (identical fingerprint).",
            consequence="Approve to skip this row; reject to keep both for manual handling.",
            risk_tier="review",
            evidence={"duplicate_of": str(exact_dup_of)},
        )

    if sku_conflicts and product.sku in sku_conflicts and len(sku_conflicts[product.sku]) > 1:
        others = [str(pid) for pid in sku_conflicts[product.sku] if pid != product.id]
        if others:
            add_decision(
                DecisionKind.conflicting_sku,
                field="sku",
                original_value=product.sku,
                proposed_value=None,
                reason="Repeated SKU with conflicting data across rows.",
                consequence="Approve a winning row or edit SKU; merges are never automatic.",
                risk_tier="approval",
                evidence={"other_product_ids": others},
            )

    if not images or not has_primary:
        # ensure decision exists
        if not any(d.kind == DecisionKind.no_primary_image for d in decisions):
            add_decision(
                DecisionKind.no_primary_image,
                field="primary_image",
                original_value=original.get("image_filename"),
                proposed_value=None,
                reason="No suitable product-only primary image.",
                consequence="Publication blocked until a primary image is approved or uploaded.",
                risk_tier="review",
            )

    if images:
        fname_model = original.get("model")
        fname_image = original.get("image_filename") or ""
        if fname_model and fname_image and not model_token_in_asset(str(fname_model), str(fname_image)):
            add_decision(
                DecisionKind.conflicting_variant,
                field="primary_image",
                original_value=fname_image,
                proposed_value=None,
                reason=(
                    f"Supplier image '{fname_image}' does not associate with model {fname_model}. "
                    "Constructed demo error: wrong-variant photograph."
                ),
                consequence="Publication blocked until a matching photograph is approved.",
                risk_tier="approval",
                evidence={
                    "constructed_demo_error": True,
                    "detection": "source_model_association",
                    "vision_used": False,
                },
            )

    # Publication is handled via batch review-and-publish, not per-product inbox cards.

    if decisions:
        product.status = ProductStatus.needs_review
        version.is_publishable = False
    else:
        product.status = ProductStatus.ready

    refresh_product_readiness(db, product)
    db.flush()
    return version


def median_prices(products_originals: list[dict[str, Any]]) -> Decimal | None:
    amounts: list[Decimal] = []
    for o in products_originals:
        try:
            amt, _ = parse_money(o.get("price"), o.get("currency") or "USD")
            amounts.append(amt)
        except MoneyError:
            continue
    if not amounts:
        return None
    amounts.sort()
    mid = len(amounts) // 2
    if len(amounts) % 2:
        return amounts[mid]
    return (amounts[mid - 1] + amounts[mid]) / 2
