"""Local file storage behind a simple interface."""

from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path

from PIL import Image

from app.config import get_settings


class StorageError(ValueError):
    pass


ALLOWED_MIME = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}

MAX_BYTES = 8 * 1024 * 1024
MIN_DIM = 64
MAX_DIM = 6000


class LocalStorage:
    def __init__(self, root: Path | None = None) -> None:
        settings = get_settings()
        self.root = Path(root or settings.storage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save_image(
        self,
        data: bytes,
        *,
        filename: str,
        subdirectory: str = "images",
    ) -> dict:
        if len(data) > MAX_BYTES:
            raise StorageError("file_too_large")
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception as exc:
            raise StorageError("decode_failed") from exc
        fmt = (img.format or "").upper()
        mime = None
        for m, f in ALLOWED_MIME.items():
            if f == fmt:
                mime = m
                break
        if mime is None:
            raise StorageError(f"unsupported_format:{fmt}")
        w, h = img.size
        if w < MIN_DIM or h < MIN_DIM or w > MAX_DIM or h > MAX_DIM:
            raise StorageError("invalid_dimensions")

        # Strip EXIF by re-encoding
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        if clean.mode not in ("RGB", "RGBA"):
            clean = clean.convert("RGB")

        digest = hashlib.sha256(data).hexdigest()[:16]
        stem = Path(filename).stem[:40] or "image"
        uid = uuid.uuid4().hex[:8]
        rel_dir = Path(subdirectory)
        abs_dir = self.root / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        ext = "jpg" if mime == "image/jpeg" else ("png" if mime == "image/png" else "webp")
        original_name = f"{stem}-{digest}-{uid}.{ext}"
        original_path = abs_dir / original_name
        save_fmt = ALLOWED_MIME[mime]
        clean.save(original_path, format=save_fmt, optimize=True)

        # Derivative: max 800px
        deriv = clean.copy()
        deriv.thumbnail((800, 800))
        deriv_name = f"{stem}-{digest}-{uid}-800.{ext}"
        deriv_path = abs_dir / deriv_name
        deriv.save(deriv_path, format=save_fmt, optimize=True)

        return {
            "original_path": str(original_path.relative_to(self.root)),
            "derivative_path": str(deriv_path.relative_to(self.root)),
            "mime_type": mime,
            "width": w,
            "height": h,
            "size_bytes": original_path.stat().st_size,
        }

    def absolute(self, relative: str) -> Path:
        return self.root / relative

    def copy_fixture(self, fixture_path: Path, subdirectory: str = "fixtures") -> dict:
        data = fixture_path.read_bytes()
        return self.save_image(data, filename=fixture_path.name, subdirectory=subdirectory)
