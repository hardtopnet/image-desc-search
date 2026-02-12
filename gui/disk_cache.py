from genericpath import exists
import hashlib
from pathlib import Path
import re

from common import constants

class DiskCache():
    def __init__(self) -> None:
        self._disk_cache_dir = constants.CACHE_PATH
        try:
            self._disk_cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self._disk_cache_enabled = True

    def _disk_cache_path(self, *, cache_id: str, size: int) -> Path:
        # Cache file: <id>_<size>.png
        # Use hash if available; fallback: stable sha1 of the identifier.
        if not cache_id:
            cache_id = "unknown"

        safe = cache_id.strip()
        if not re.fullmatch(r"[0-9a-fA-F]{16,128}", safe):
            safe = hashlib.sha1(safe.encode("utf-8"), usedforsecurity=False).hexdigest()
        safe = safe.lower()
        sub = safe[:2]
        if not exists(self._disk_cache_dir / sub):
            try:
                (self._disk_cache_dir / sub).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        return self._disk_cache_dir / sub / f"{safe}_{int(size)}.png"

    def disk_cache_read(self, *, cache_id: str, size: int) -> bytes | None:
        if not self._disk_cache_enabled:
            return None
        try:
            p = self._disk_cache_path(cache_id=cache_id, size=size)
            if not p.exists():
                return None
            data = p.read_bytes()
            if not data:
                return None
            return data
        except Exception:
            return None

    def disk_cache_write(self, *, cache_id: str, size: int, png: bytes) -> None:
        if not self._disk_cache_enabled:
            return
        try:
            p = self._disk_cache_path(cache_id=cache_id, size=size)
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_bytes(png)
            tmp.replace(p)
        except Exception:
            return
