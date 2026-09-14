"""Seiko manufacturer-page adapter. Parses retrieved HTML; registry is not a live result."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from app.policy.watch_specs import normalize_model_reference

REGISTRY_REL = Path("manufacturer/seiko_registry.json")


@dataclass
class SeikoPageRecord:
    model: str
    source_page: str
    collection: str | None = None
    specifications: dict[str, str] = field(default_factory=dict)
    image_candidates: list[str] = field(default_factory=list)
    catalog_asset_code: str | None = None
    raw_excerpt: dict[str, Any] = field(default_factory=dict)


def load_seiko_registry(fixtures_root: Path) -> dict[str, Any]:
    path = fixtures_root / REGISTRY_REL
    return json.loads(path.read_text())


def registry_entry(fixtures_root: Path, model: str) -> dict[str, Any] | None:
    token = normalize_model_reference(model)
    if not token:
        return None
    data = load_seiko_registry(fixtures_root)
    return (data.get("models") or {}).get(token)


def _strip_tags(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text))


def _meta_content(html: str, prop: str) -> str | None:
    pat = re.compile(
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
        re.I,
    )
    match = pat.search(html)
    if match:
        return unescape(match.group(1))
    pat2 = re.compile(
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(prop)}["\']',
        re.I,
    )
    match = pat2.search(html)
    return unescape(match.group(1)) if match else None


KNOWN_LABELS = [
    "Caliber Number",
    "Movement Type",
    "Power reserve",
    "Jewels",
    "Functions",
    "Case Material",
    "Case Size",
    "Crystal",
    "LumiBrite",
    "Clasp",
    "Distance between lugs",
    "Other Details",
    "Water Resistance",
    "Magnetic Resistance",
    "Weight",
    "Features",
]


def _label_value(plain: str, label: str) -> str | None:
    others = [re.escape(item) for item in KNOWN_LABELS if item != label]
    boundary = "|".join(others) if others else r"$"
    match = re.search(rf"{re.escape(label)}\s+(.+?)(?=\s+(?:{boundary})|$)", plain)
    if not match:
        return None
    value = unescape(match.group(1)).strip(" |")
    value = re.split(r"\s{2,}|\s\|\s", value)[0].strip()
    return value or None


def parse_seiko_product_page(html: str, page_url: str, *, expected_model: str) -> SeikoPageRecord:
    expected = normalize_model_reference(expected_model) or ""
    title = _meta_content(html, "og:title") or ""
    page_model = normalize_model_reference(title.split("|")[0]) or expected
    if page_model and expected and page_model != expected:
        raise ValueError(f"page_model_mismatch:{page_model}:{expected}")

    og_image = _meta_content(html, "og:image")
    collection = None
    if "5 Sports" in html and "SKX" in html:
        collection = "5 Sports SKX series"

    # Prefer labeled extraction from stripped markup
    labeled_html = re.sub(r"</(dt|th|h\d|p|li|td)>", " | ", html, flags=re.I)
    labeled_html = re.sub(r"<br\s*/?>", " ", labeled_html, flags=re.I)
    plain = _strip_tags(labeled_html)

    specs: dict[str, str] = {}
    caliber = _label_value(plain, "Caliber Number")
    if caliber:
        specs["caliber"] = caliber.split()[0]
    movement = _label_value(plain, "Movement Type")
    if movement:
        specs["movement_type"] = movement.split("|")[0].strip()
    reserve = _label_value(plain, "Power reserve")
    if reserve:
        specs["power_reserve"] = reserve.split("|")[0].strip()
    material = _label_value(plain, "Case Material")
    if material:
        specs["case_material"] = material.split("|")[0].strip()
    crystal = _label_value(plain, "Crystal")
    if crystal:
        specs["crystal"] = crystal.split("|")[0].strip()
    water = _label_value(plain, "Water Resistance")
    if water:
        specs["water_resistance"] = water.split("|")[0].strip()
    weight = _label_value(plain, "Weight")
    if weight:
        specs["weight"] = weight.split("|")[0].strip()
    lugs = _label_value(plain, "Distance between lugs")
    if lugs:
        token = re.match(r"\d+", lugs)
        if token:
            specs["lug_width"] = f"{token.group(0)} mm"

    size_chunk = ""
    size_match = re.search(r"Case Size(.*?)(?:Crystal|LumiBrite)", plain, re.I)
    if size_match:
        size_chunk = size_match.group(1)
    thick = re.search(r"Thickness:\s*([0-9.]+)\s*mm", html + " " + size_chunk, re.I)
    diam = re.search(r"Diameter:\s*([0-9.]+)\s*mm", html + " " + size_chunk, re.I)
    l2l = re.search(r"Lug-to-lug:\s*([0-9.]+)\s*mm", html + " " + size_chunk, re.I)
    if thick:
        specs["case_thickness"] = f"{thick.group(1)} mm"
    if diam:
        specs["case_diameter"] = f"{diam.group(1)} mm"
    if l2l:
        specs["lug_to_lug"] = f"{l2l.group(1)} mm"

    if collection:
        specs["collection"] = collection
    specs["manufacturer_reference"] = page_model or expected
    # Bracelet material is not a labeled field on these pages — do not invent it.

    candidates: list[str] = []
    if og_image:
        candidates.append(og_image)
    for rel in re.findall(r'(?:src|content)=["\']([^"\']*Product--Image[^"\']+)', html, re.I):
        abs_url = urljoin(page_url, unescape(rel).split("?")[0])
        if expected and expected.lower() in abs_url.lower() and abs_url not in candidates:
            # Skip recommendation thumbs (other model codes) and logos
            path = urlparse(abs_url).path.lower()
            if any(skip in path for skip in ("megamenu", "logo", "sns-", "category_")):
                continue
            if expected.lower() in path:
                candidates.append(abs_url)

    # Keep product-frame PNG first; drop unrelated models
    filtered = []
    for url in candidates:
        path = urlparse(url).path
        if expected and expected not in path.upper().replace("-", ""):
            continue
        if "/product--image/" not in path.lower() and "og:image" not in url:
            if "Product--Image" not in path and "Product--Image" not in url:
                continue
        filtered.append(url.split("?")[0])
    # de-dupe
    seen: set[str] = set()
    unique: list[str] = []
    for url in filtered or [c.split("?")[0] for c in candidates[:1]]:
        if url in seen:
            continue
        seen.add(url)
        unique.append(url)

    pngs = [u for u in unique if u.lower().endswith(".png")]
    unique = pngs or unique[:1]
    catalog_code = None
    for url in unique:
        m = re.search(rf"({expected}K1)", urlparse(url).path, re.I)
        if m:
            catalog_code = m.group(1).upper()
            break

    return SeikoPageRecord(
        model=page_model or expected,
        source_page=page_url,
        collection=collection,
        specifications=specs,
        image_candidates=unique,
        catalog_asset_code=catalog_code,
        raw_excerpt={
            "og_title": title,
            "og_image": og_image,
            "spec_keys": list(specs.keys()),
        },
    )
