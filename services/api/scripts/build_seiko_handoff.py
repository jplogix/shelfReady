"""Build artifacts/shelfready-seiko-image-handoff.zip from downloaded originals."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
ORIGINALS = ROOT / "fixtures" / "seiko_images" / "originals"
OPTIMIZED = ROOT / "fixtures" / "seiko_images" / "optimized"
ARTIFACTS = ROOT / "artifacts"
REGISTRY = ROOT / "fixtures" / "manufacturer" / "seiko_registry.json"

MANIFEST_ROWS = [
    {
        "supplier_sku": "SK-SRPD55-01",
        "model_reference": "SRPD55",
        "file": "SRPD55K1.png",
        "source_page": "https://www.seikowatches.com/us-en/products/5sports/srpd55",
        "direct_image_url": "https://www.seikowatches.com/us-en/-/media/Images/Product--Image/All/Seiko/2022/02/20/02/14/SRPD55K1/SRPD55K1.png",
        "match_rationale": "og:image and Product--Image path on the SRPD55 page use catalog code SRPD55K1. Manual review of the downloaded file: black dial, black bezel, steel bracelet.",
        "usage_status": "manufacturer_hosted; commercial_republication_not_established; demo_storefront_only",
        "integration_status": "handoff/replay bundle only for import; hero CSV has no image_filename; runtime tool must attach",
        "role": "hero_runtime_recovery",
    },
    {
        "supplier_sku": "SK-SRPD51-01",
        "model_reference": "SRPD51",
        "file": "SRPD51K1.png",
        "source_page": "https://www.seikowatches.com/us-en/products/5sports/srpd51",
        "direct_image_url": "https://www.seikowatches.com/us-en/-/media/Images/Product--Image/All/Seiko/2022/02/20/02/14/SRPD51K1/SRPD51K1.png",
        "match_rationale": "Official SRPD51 page og:image SRPD51K1.png. Manual review: blue dial, blue bezel, steel bracelet.",
        "usage_status": "manufacturer_hosted; commercial_republication_not_established; demo_storefront_only",
        "integration_status": "assigned on supplier import (matching model)",
        "role": "matching_photo_with_spec_conflict",
    },
    {
        "supplier_sku": "SK-SRPD63-01",
        "model_reference": "SRPD63",
        "file": "SRPD63K1.png",
        "source_page": "https://www.seikowatches.com/us-en/products/5sports/srpd63",
        "direct_image_url": "https://www.seikowatches.com/us-en/-/media/Images/Product--Image/All/Seiko/2022/02/20/02/16/SRPD63K1/SRPD63K1.png",
        "match_rationale": "Official SRPD63 page og:image SRPD63K1.png. Manual review: green dial, green bezel, rose-gold hands, steel bracelet.",
        "usage_status": "manufacturer_hosted; commercial_republication_not_established; demo_storefront_only",
        "integration_status": "assigned on supplier import (matching model)",
        "role": "mostly_complete",
    },
    {
        "supplier_sku": "SK-SRPD53-01",
        "model_reference": "SRPD53",
        "file": "SRPD53K1.png",
        "source_page": "https://www.seikowatches.com/us-en/products/5sports/srpd53",
        "direct_image_url": "https://www.seikowatches.com/us-en/-/media/Images/Product--Image/All/Seiko/2022/02/20/02/14/SRPD53K1/SRPD53K1.png",
        "match_rationale": "Official SRPD53 page photograph (blue dial, blue/red bezel). Not used on the constructed wrong-variant supplier row.",
        "usage_status": "manufacturer_hosted; commercial_republication_not_established; kept for review; not the supplier-assigned image",
        "integration_status": "unassigned on SK-SRPD53-01 (that row uses SRPD51K1.png as a constructed mismatch)",
        "role": "correct_srpd53_reference_not_on_wrong_variant_row",
    },
]

LIFESTYLE = [
    {
        "supplier_sku": "SK-SRPD55-01",
        "model_reference": "SRPD55",
        "file": "SRPD55K1_1.jpg",
        "source_page": "https://www.seikowatches.com/us-en/products/5sports/srpd55",
        "direct_image_url": "https://www.seikowatches.com/us-en/-/media/Images/Product--Image/America/Seiko/5sports/SRPD55K1/SRPD55K1_1.jpg",
        "note": "Official SRPD55 gallery lifestyle frame. Not used as primary (inconsistent product-only frame).",
    },
    {
        "supplier_sku": "SK-SRPD55-01",
        "model_reference": "SRPD55",
        "file": "SRPD55K1_2.jpg",
        "source_page": "https://www.seikowatches.com/us-en/products/5sports/srpd55",
        "direct_image_url": "https://www.seikowatches.com/us-en/-/media/Images/Product--Image/America/Seiko/5sports/SRPD55K1/SRPD55K1_2.jpg",
        "note": "Official SRPD55 gallery lifestyle frame. Not used as primary.",
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def optimize(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src)
    img.load()
    frame = img.convert("RGBA") if img.mode in {"RGBA", "P"} else img.convert("RGB")
    frame.thumbnail((1200, 1200))
    if src.suffix.lower() == ".png":
        frame.save(dest, format="PNG", optimize=True)
    else:
        frame.convert("RGB").save(dest, format="JPEG", quality=88, optimize=True)


def contact_sheet(paths: list[Path], dest: Path) -> None:
    thumbs: list[Image.Image] = []
    labels: list[str] = []
    for path in paths:
        im = Image.open(path)
        im.load()
        im.thumbnail((320, 320))
        canvas = Image.new("RGB", (320, 320), (245, 242, 234))
        canvas.paste(im.convert("RGB"), ((320 - im.size[0]) // 2, (320 - im.size[1]) // 2))
        thumbs.append(canvas)
        labels.append(path.name)
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 340 + 20, rows * 380 + 40), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        r, c = divmod(i, cols)
        x, y = 20 + c * 340, 20 + r * 380
        sheet.paste(thumb, (x, y))
        draw.text((x, y + 325), labels[i], fill=(32, 32, 32))
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, format="JPEG", quality=90)


def main() -> None:
    OPTIMIZED.mkdir(parents=True, exist_ok=True)
    originals = []
    for row in MANIFEST_ROWS:
        src = ORIGINALS / row["file"]
        if not src.exists():
            raise SystemExit(f"missing original {src}")
        dest = OPTIMIZED / row["file"]
        optimize(src, dest)
        im = Image.open(src)
        im.load()
        originals.append(src)
        row.update(
            {
                "retrieval_timestamp": datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).isoformat(),
                "local_original": f"originals/{row['file']}",
                "local_derivative": f"optimized/{row['file']}",
                "width": im.size[0],
                "height": im.size[1],
                "format": im.format,
                "sha256": sha256(src),
            }
        )
    lifestyle_rows = []
    for row in LIFESTYLE:
        src = ORIGINALS / row["file"]
        if not src.exists():
            continue
        dest = OPTIMIZED / row["file"]
        optimize(src, dest)
        im = Image.open(src)
        im.load()
        originals.append(src)
        lifestyle_rows.append(
            {
                **row,
                "retrieval_timestamp": datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).isoformat(),
                "local_original": f"originals/{row['file']}",
                "local_derivative": f"optimized/{row['file']}",
                "width": im.size[0],
                "height": im.size[1],
                "format": im.format,
                "sha256": sha256(src),
                "usage_status": "manufacturer_hosted; not primary; commercial_republication_not_established",
                "integration_status": "not used in featured gallery (lifestyle frame)",
            }
        )
    sheet_path = OPTIMIZED / "contact-sheet.jpg"
    contact_sheet(originals, sheet_path)

    notes = """# Seiko image handoff

Downloaded from official Seiko US product pages on 2026-09-14.

Usage: manufacturer-hosted photographs. Official hosting does not grant commercial republication rights.
Isolated ShelfReady demonstration may display them with `demo_storefront_only` captions. Not Seiko-sponsored.

The SRPD55 hero photograph is included here and in replay fixtures while remaining unassigned on the imported supplier row (empty image_filename). Runtime `retrieve_manufacturer_record` must still persist and attach it. Replay vs network retrieval is recorded on evidence.

SK-SRPD53-01 deliberately uses SRPD51K1.png in the supplier CSV as a constructed wrong-variant error.

## Local setup

```
cd services/api && .venv/bin/alembic upgrade head
.venv/bin/python scripts/reset_seiko_demo.py          # dry-run
.venv/bin/python scripts/reset_seiko_demo.py --apply  # new isolated batch
```

Hero SK-SRPD55-01 must have no ProductImage rows after import and before process.
"""
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    zip_path = ARTIFACTS / "shelfready-seiko-image-handoff.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src in ORIGINALS.iterdir():
            if src.is_file():
                zf.write(src, f"originals/{src.name}")
        for src in OPTIMIZED.iterdir():
            if src.is_file():
                zf.write(src, f"optimized/{src.name}")
        zf.write(REGISTRY, "manufacturer/seiko_registry.json")
        zf.writestr("USAGE.md", notes)
        zf.writestr("manifest.json", json.dumps({"products": MANIFEST_ROWS, "unresolved_or_non_primary": lifestyle_rows}, indent=2))
        buf = StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "supplier_sku",
                "model_reference",
                "source_page",
                "direct_image_url",
                "retrieval_timestamp",
                "local_original",
                "local_derivative",
                "width",
                "height",
                "format",
                "sha256",
                "match_rationale",
                "usage_status",
                "integration_status",
                "role",
            ],
        )
        writer.writeheader()
        for row in MANIFEST_ROWS:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})
        zf.writestr("manifest.csv", buf.getvalue())
        zf.writestr(
            "SETUP.md",
            "Import fixtures/seiko_demo_catalog.csv. Do not pre-seed SK-SRPD55-01 images. Run worker process, accept image decision, publish featured SKUs.\n",
        )

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for row in MANIFEST_ROWS:
            assert row["local_original"] in names
            assert row["local_derivative"] in names
        assert "optimized/contact-sheet.jpg" in names
        assert "manifest.json" in names
    print(f"Wrote {zip_path} files={len(names)}")


if __name__ == "__main__":
    main()
