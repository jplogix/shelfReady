"""Curated demonstration catalog identity (separate from stress-test fixtures)."""

HOUSEHOLD_DEMO_SKUS = {
    "HC-COKE-01",
    "HC-CREST-01",
    "HC-TIDE-01",
    "HC-TOWEL-01",
    "HC-SHAM-01",
}

# Featured public shop collection for this pass.
PUBLIC_FEATURED_COLLECTION = "seiko_watches"
PUBLIC_FEATURED_SKUS = {
    "SK-SRPD55-01",
    "SK-SRPD51-01",
    "SK-SRPD63-01",
}

PUBLIC_DEMO_SKUS = PUBLIC_FEATURED_SKUS


def canonical_sku(sku: str | None) -> str:
    if not sku:
        return ""
    return sku.split("__")[0]


def is_public_demo_sku(sku: str | None) -> bool:
    return canonical_sku(sku) in PUBLIC_FEATURED_SKUS


def is_household_demo_sku(sku: str | None) -> bool:
    return canonical_sku(sku) in HOUSEHOLD_DEMO_SKUS
