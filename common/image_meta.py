from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

class ImageResolution(NamedTuple):
    w: int
    h: int

@dataclass(frozen=True)
class FileMetadata:
    path: Path
    size_bytes: int
    created_at_utc: str
    modified_at_utc: str

    @staticmethod
    def dt_to_utc_iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ImageMetadata:
    sha256: str
    size_bytes: int
    res_w: int | None
    res_h: int | None
    thumbnail: bytes | None

    @staticmethod
    def _file_metadata(path: Path) -> FileMetadata:
        st = path.stat()
        created = datetime.fromtimestamp(st.st_ctime, tz=timezone.utc)
        modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        return FileMetadata(
            path=path,
            size_bytes=int(st.st_size),
            created_at_utc=FileMetadata.dt_to_utc_iso(created),
            modified_at_utc=FileMetadata.dt_to_utc_iso(modified),
        )

    @staticmethod
    def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def image_resolution(path: Path) -> ImageResolution | None:
        try:
            from PIL import Image
        except Exception:
            return None

        try:
            with Image.open(path) as img:
                w, h = img.size
                return ImageResolution(int(w), int(h))
        except Exception:
            return None

    @staticmethod
    def _image_thumbnail_jpeg(path: Path, *, max_size: int = 256, quality: int = 65) -> bytes | None:
        try:
            from PIL import Image
        except Exception:
            return None

        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                img.thumbnail((max_size, max_size))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                return buf.getvalue()
        except Exception:
            return None

    @staticmethod
    def build_image_metadata(path: Path) -> tuple[FileMetadata, ImageMetadata]:
        fm = ImageMetadata._file_metadata(path)
        sha = ImageMetadata._sha256_file(path)
        res = ImageMetadata.image_resolution(path)
        thumb = ImageMetadata._image_thumbnail_jpeg(path)
        return (
            fm,
            ImageMetadata(
                sha256=sha,
                size_bytes=fm.size_bytes,
                res_w=res.w if res else None,
                res_h=res.h if res else None,
                thumbnail=thumb,
            ),
        )
