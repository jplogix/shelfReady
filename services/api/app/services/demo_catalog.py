"""Curated demonstration catalog identity (separate from stress-test fixtures)."""

PUBLIC_DEMO_SKUS = {
    "HC-COKE-01",
    "HC-CREST-01",
    "HC-TIDE-01",
    "HC-TOWEL-01",
    "HC-SHAM-01",
}


def canonical_sku(sku: str | None) -> str:
    if not sku:
        return ""
    return sku.split("__")[0]


def is_public_demo_sku(sku: str | None) -> bool:
    return canonical_sku(sku) in PUBLIC_DEMO_SKUS
