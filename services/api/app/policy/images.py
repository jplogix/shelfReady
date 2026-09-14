"""Fixture image source, usage, and category suitability — not authenticity claims."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.models import ImageClass

DEMONSTRATION_CAPTION = "Demonstration illustration · not authentic product photography"
MANUFACTURER_DEMO_CAPTION = (
    "Manufacturer product photograph retrieved for this isolated ShelfReady demonstration. "
    "Not Seiko-sponsored. Commercial republication rights are not established."
)


@dataclass(frozen=True)
class ImageAssetMeta:
    filename: str
    image_class: ImageClass
    prefer_as_primary: bool
    source_kind: str
    usage_permission: str
    suitable_types: frozenset[str]
    caption: str
    associated_model: str | None = None


def _seiko(filename: str, model: str) -> ImageAssetMeta:
    return ImageAssetMeta(
        filename=filename,
        image_class=ImageClass.product_only,
        prefer_as_primary=True,
        source_kind="manufacturer_product_page",
        usage_permission="demo_storefront_only",
        suitable_types=frozenset({"watch", "watches", "wristwatch"}),
        caption=MANUFACTURER_DEMO_CAPTION,
        associated_model=model,
    )


def _demo(filename: str, types: set[str]) -> ImageAssetMeta:
    return ImageAssetMeta(
        filename=filename,
        image_class=ImageClass.product_only,
        prefer_as_primary=True,
        source_kind="fixture_illustration",
        usage_permission="demonstration_only",
        suitable_types=frozenset(t.lower() for t in types),
        caption=DEMONSTRATION_CAPTION,
    )


def _stress(
    filename: str,
    image_class: ImageClass,
    prefer: bool,
    types: set[str],
) -> ImageAssetMeta:
    return ImageAssetMeta(
        filename=filename,
        image_class=image_class,
        prefer_as_primary=prefer,
        source_kind="fixture_stress",
        usage_permission="demonstration_only",
        suitable_types=frozenset(t.lower() for t in types),
        caption=DEMONSTRATION_CAPTION,
    )


IMAGE_ASSETS: dict[str, ImageAssetMeta] = {
    "SRPD55K1.png": _seiko("SRPD55K1.png", "SRPD55"),
    "SRPD51K1.png": _seiko("SRPD51K1.png", "SRPD51"),
    "SRPD63K1.png": _seiko("SRPD63K1.png", "SRPD63"),
    "SRPD53K1.png": _seiko("SRPD53K1.png", "SRPD53"),
    "demo-soda-can.png": _demo("demo-soda-can.png", {"soda", "soft drink", "beverage"}),
    "demo-toothpaste.png": _demo("demo-toothpaste.png", {"toothpaste"}),
    "demo-laundry-pods.png": _demo("demo-laundry-pods.png", {"detergent", "laundry"}),
    "demo-paper-towels.png": _demo("demo-paper-towels.png", {"paper towels", "paper towel"}),
    "demo-shampoo.png": _demo("demo-shampoo.png", {"shampoo"}),
    "demo-deodorant.png": _demo("demo-deodorant.png", {"deodorant"}),
    "demo-cleaner.png": _demo("demo-cleaner.png", {"cleaner", "spray"}),
    "aurora-mug.png": _stress("aurora-mug.png", ImageClass.product_only, True, {"mug", "drinkware"}),
    "aurora-hoodie.png": _stress(
        "aurora-hoodie.png", ImageClass.product_only, True, {"hoodie", "apparel", "jacket", "throw"}
    ),
    "nw-tote-black.png": _stress("nw-tote-black.png", ImageClass.product_only, True, {"tote", "bag"}),
    "nw-tote-model.png": _stress("nw-tote-model.png", ImageClass.model_worn, False, {"tote", "bag"}),
    "gucci-sunglass.png": _stress(
        "gucci-sunglass.png", ImageClass.product_only, True, {"sunglasses", "sun glasses"}
    ),
    "packaging-only.png": _stress(
        "packaging-only.png", ImageClass.packaging, False, {"lamp", "case"}
    ),
    "detail-stitch.png": _stress("detail-stitch.png", ImageClass.detail, False, {"cap", "belt", "socks"}),
}


def lookup_image_meta(filename: str | None) -> ImageAssetMeta | None:
    if not filename:
        return None
    name = filename.split("/")[-1]
    if name in IMAGE_ASSETS:
        return IMAGE_ASSETS[name]
    for key, meta in IMAGE_ASSETS.items():
        if key in name:
            return meta
    return None


def suitability_for(
    meta: ImageAssetMeta | None,
    product_type: str | None,
    category: str | None,
    *,
    model: str | None = None,
) -> str:
    if meta is None:
        return "unclassified"
    if meta.associated_model:
        from app.policy.watch_specs import normalize_model_reference

        expected = normalize_model_reference(meta.associated_model)
        actual = normalize_model_reference(model)
        if actual and expected and actual != expected:
            return "model_mismatch"
        if actual and expected and actual == expected:
            return "source_model_match"
    haystack = f"{product_type or ''} {category or ''}".strip().lower()
    if not haystack:
        return "unclassified"
    if any(token in haystack for token in meta.suitable_types):
        return "category_match"
    return "category_mismatch"


def image_payload(meta: ImageAssetMeta | None, product_type: str | None, category: str | None) -> dict[str, str]:
    if meta is None:
        return {
            "source_kind": "unknown",
            "usage_permission": "unknown",
            "suitability": "unclassified",
            "caption": "",
        }
    return {
        "source_kind": meta.source_kind,
        "usage_permission": meta.usage_permission,
        "suitability": suitability_for(meta, product_type, category),
        "caption": meta.caption,
    }
