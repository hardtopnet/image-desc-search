
from collections import OrderedDict
import io
import queue
import threading
from typing import Any
from PIL import ImageTk, Image
import tkinter as tk
from common import constants
from common.db import connect, migrate
from gui.disk_cache import DiskCache

class ThumbCache():
    def __init__(self, root: tk.Tk, disk_cache: DiskCache) -> None:
        self._root = root
        self._disk_cache = disk_cache

        self._thumb_cache: OrderedDict[tuple[str, int], ImageTk.PhotoImage] = OrderedDict()
        self._thumb_cache_max = 350
        self._thumb_max = 200
        self._thumb_req_q: queue.Queue[tuple[int, str, str]] = queue.Queue()
        self._thumb_done_q: queue.Queue[tuple[int, str, str, bytes | None]] = queue.Queue()
        self._thumb_inflight: set[tuple[str, int]] = set()

        self._thumb_worker = threading.Thread(target=self._thumb_worker_main, daemon=True)
        self._thumb_worker.start()
        self._thumb_poller_id: str | None = None
    
    def get(self, key: tuple[str, int]) -> ImageTk.PhotoImage | None:
        v = self._thumb_cache.get(key)
        if v is None:
            return None
        self._thumb_cache.move_to_end(key)
        return v

    def put(self, key: tuple[str, int], img: ImageTk.PhotoImage) -> None:
        self._thumb_cache[key] = img
        self._thumb_cache.move_to_end(key)
        while len(self._thumb_cache) > self._thumb_cache_max:
            self._thumb_cache.popitem(last=False)

    def get_key(self, cache_id: str) -> tuple[str, int]:
        return (cache_id, self._thumb_max)
    
    def check_inflight(self, index: int, cache_id: str, path_text: str) -> bool:
        key = (cache_id, self._thumb_max)
        if key not in self._thumb_inflight:
            self._thumb_inflight.add(key)
            self._thumb_req_q.put_nowait((index, path_text, cache_id))
            return True
        return False

    def check_incache(self, index: int, cache_id: str, path_text: str) -> bool:
        key = (cache_id, self._thumb_max)
        if self._thumb_cache.get(key) is not None:
            return False # Already in cache, no need to enqueue.
        
        return self.check_inflight(index=index, cache_id=cache_id, path_text=path_text)

    def ensure_thumb_poller(self) -> None:
        if self._thumb_poller_id is not None:
            return
        self._thumb_poller_id = self._root.after(30, self._poll_thumbs)


    def _thumb_worker_main(self) -> None:
        conn = None

        def _ensure_conn() -> Any:
            nonlocal conn
            if conn is not None:
                return conn
            conn = connect(constants.DB_PATH)
            try:
                migrate(conn)
            except Exception:
                pass
            return conn

        def _reset_conn() -> None:
            nonlocal conn
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            conn = None

        def _load_thumbnail_bytes(*, conn: Any, cache_id: str, path_text: str) -> bytes | None:
            try:
                # Fast-path: cache_id is already the image hash.
                row2 = conn.execute("SELECT thumbnail FROM IMAGE_METADATA WHERE hash = ?", [cache_id]).fetchone()
                if row2 is not None:
                    blob = row2["thumbnail"]
                    if blob is None:
                        return None
                    if isinstance(blob, memoryview):
                        return blob.tobytes()
                    if isinstance(blob, (bytes, bytearray)):
                        return bytes(blob)
                    return None
                
                # First fetch hash via unique path index, then fetch thumbnail by primary key.
                row = conn.execute("SELECT hash FROM IMAGE_FILE WHERE path = ?", [path_text]).fetchone()
                if row is None:
                    return None

                h = row["hash"]
                row2 = conn.execute("SELECT thumbnail FROM IMAGE_METADATA WHERE hash = ?", [h]).fetchone()
                if row2 is None:
                    return None
                blob = row2["thumbnail"]
                if blob is None:
                    return None
                if isinstance(blob, memoryview):
                    return blob.tobytes()
                if isinstance(blob, (bytes, bytearray)):
                    return bytes(blob)
                return None
            except Exception:
                return None

        def _make_cover_thumbnail(img: Image.Image) -> Image.Image:
            # Create a 16:9 cover thumbnail (crop to fill) without distortion.
            try:
                target_w, target_h = getattr(self, "_thumb_size", (self._thumb_max, int(self._thumb_max * 9 / 16)))
            except Exception:
                target_w, target_h = self._thumb_max, int(self._thumb_max * 9 / 16)

            img = img.convert("RGB")
            src_w, src_h = img.size
            if src_w <= 0 or src_h <= 0:
                return img

            target_ratio = target_w / target_h
            src_ratio = src_w / src_h

            if src_ratio > target_ratio:
                # Source is wider: crop left/right
                new_w = int(src_h * target_ratio)
                left = max(0, (src_w - new_w) // 2)
                box = (left, 0, left + new_w, src_h)
            else:
                # Source is taller: crop top/bottom
                new_h = int(src_w / target_ratio)
                top = max(0, (src_h - new_h) // 2)
                box = (0, top, src_w, top + new_h)

            img = img.crop(box)
            return img.resize((int(target_w), int(target_h)), Image.Resampling.LANCZOS)

        while True:
            idx, path_text, cache_id = self._thumb_req_q.get()
            out_png: bytes | None = None
            try:
                c = _ensure_conn()
                out_png = self._disk_cache.disk_cache_read(cache_id=cache_id, size=self._thumb_max)
                if out_png:
                    self._thumb_done_q.put((idx, path_text, cache_id, out_png))
                    continue

                thumb_bytes = _load_thumbnail_bytes(conn=c, cache_id=cache_id, path_text=path_text)
                if thumb_bytes:
                    img = Image.open(io.BytesIO(thumb_bytes))
                    img2 = _make_cover_thumbnail(img)
                    buf = io.BytesIO()
                    img2.save(buf, format="PNG", optimize=True)
                    out_png = buf.getvalue()
                    self._disk_cache.disk_cache_write(cache_id=cache_id, size=self._thumb_max, png=out_png)                
            
            except Exception:
                _reset_conn()
                out_png = None
            self._thumb_done_q.put((idx, path_text, cache_id, out_png))

    def _poll_thumbs(self) -> None:
        self._thumb_poller_id = None
        updated = False
        for _ in range(40):
            try:
                idx, path_text, cache_id, png = self._thumb_done_q.get_nowait()
            except Exception:
                break
            key = (cache_id, self._thumb_max)
            self._thumb_inflight.discard(key)

            if png is None:
                # Force a rerender so the card can leave "Loading..." state.
                updated = True
                continue

            try:
                photo = ImageTk.PhotoImage(data=png)
            except Exception:
                updated = True
                continue

            self.put(key, photo)
            updated = True

        if updated:
            try:
                self._root.event_generate("<<ThumbsUpdated>>", when="tail")
            except Exception:
                pass
            # self._schedule_render(delay_ms=1)

        self.ensure_thumb_poller()
