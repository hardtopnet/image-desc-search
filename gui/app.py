from __future__ import annotations

import subprocess
import threading
import tkinter as tk
import tkinter.font as tkfont

from pathlib import Path
from tkinter import messagebox, ttk
from collections import OrderedDict
import queue
import io
import time
from typing import Any

from PIL import Image, ImageTk

from common import constants
from common.db import connect, migrate
from common.searcher import Searcher
from common.searcher import SearchMatch
from gui.dir_browser import DirBrowser
from gui.disk_cache import DiskCache
from gui.gui_state import GuiStateManager
from gui.components.tooltip import Tooltip
from gui.components.scroll_activity_tracker import ScrollActivityTracker
from gui.thumb_cache import ThumbCache

class App:
    def __init__(self) -> None:
        self._root = tk.Tk()
        self._root.title("Image Desc Search")
        self._root.geometry("1100x750")

        self._measure_font = None
        try:
            # Canvas has no default font; use the same font as `create_text`.
            self._measure_font = tkfont.Font(family=constants.FONT_FAMILY, size=constants.FONT_SIZE)
        except Exception:
            self._measure_font = None
        
        self._gui_state_manager = GuiStateManager(self._root)
        self._dir_browser = DirBrowser(gui_state_manager=self._gui_state_manager)
        self._disk_cache = DiskCache()
        self._scroll_activity_tracker = ScrollActivityTracker(app=self)
        self._thumb_cache = ThumbCache(self._root, self._disk_cache)

        self._matches: list[SearchMatch] = []
        self._is_searching = False

        self._tooltip = Tooltip(root=self._root)

        self._render_after_id: str | None = None
        self._render_scheduled_at: float = 0.0
        self._render_min_interval_s: float = 1.0 / 30.0
        self._last_render_key: tuple[int, int, int, int, int, bool] | None = None
        self._scroll_after_id: str | None = None
        self._pending_scroll_units: int = 0

        self._hover_after_id: str | None = None
        self._hover_idx: int = -1
        self._hover_x_root: int = 0
        self._hover_y_root: int = 0
        self._tooltip_hover_delay_ms = 1000

        self._card_w = 230
        self._card_h = 270
        self._pad = 8
        self._path_bottom_margin = 8
        self._cols = 1
        self._visible_rows = 1
        self._virtual_total_h = 0

        self._canvas_cards: list[dict[str, Any]] = []

        self._ellipsis_cache: OrderedDict[tuple[str, int], str] = OrderedDict()
        self._ellipsis_cache_max = 4000
        self._last_path_text_by_slot: dict[int, str] = {}
        self._last_path_label_px: int = 0

        self._show_loading_placeholder = True
        self._visible_path_by_slot: dict[int, str] = {}
        self._visible_hash_by_slot: dict[int, str] = {}
        self._hash_by_path: dict[str, str] = {}

        self._input_dir_var = tk.StringVar(value=self._dir_browser.load_last_input_dir() or str(Path.cwd()))
        self._query_var = tk.StringVar(value="")
        self._status_var = tk.StringVar(value="Ready")

        self._build_ui()

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self) -> None:
        self._root.mainloop()

    def _build_ui(self) -> None:
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(1, weight=1)

        top = ttk.Frame(self._root, padding=10)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Input").grid(row=0, column=0, sticky="w")
        input_entry = ttk.Entry(top, textvariable=self._input_dir_var)
        input_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(top, text="Browse", command=self._dir_browser.browse_input).grid(row=0, column=2, sticky="e")

        ttk.Label(top, text="Query").grid(row=1, column=0, sticky="w", pady=(8, 0))
        query_entry = ttk.Entry(top, textvariable=self._query_var)
        query_entry.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        query_entry.bind("<Return>", lambda _e: self._start_search())

        self._search_btn = ttk.Button(top, text="Search", command=self._start_search)
        self._search_btn.grid(row=1, column=2, sticky="e", pady=(8, 0))

        mid = ttk.Frame(self._root, padding=(10, 0, 10, 10))
        mid.grid(row=1, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(mid, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(mid, orient="vertical")
        vsb.grid(row=0, column=1, sticky="ns")

        def _on_scrollbar(*args: str) -> None:
            self._canvas.yview(*args)
            self._schedule_render(delay_ms=1)

        def _on_canvas_scroll(first: float, last: float) -> None:
            vsb.set(first, last)
            self._schedule_render(delay_ms=1)

        vsb.configure(command=_on_scrollbar)
        self._canvas.configure(yscrollcommand=_on_canvas_scroll)

        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<ButtonRelease-1>", lambda _e: self._schedule_render(delay_ms=1))
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Enter>", lambda _e: self._canvas.focus_set())
        self._canvas.bind("<KeyPress-Down>", lambda _e: self._canvas.yview_scroll(3, "units"))
        self._canvas.bind("<KeyPress-Up>", lambda _e: self._canvas.yview_scroll(-3, "units"))
        self._canvas.bind("<Expose>", lambda _e: self._schedule_render(delay_ms=1))

        self._canvas.configure(scrollregion=(0, 0, 1, 1))

        # Kick an initial render so the pool is visible.
        self._schedule_render(delay_ms=1)

        # Keep default yscrollcommand wiring to scrollbar; rendering is driven by scroll/resize events.

        bottom = ttk.Frame(self._root, padding=(10, 0, 10, 10))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        ttk.Separator(bottom).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(bottom, textvariable=self._status_var).grid(row=1, column=0, sticky="w")

    def _on_close(self) -> None:
        try:
            self._gui_state_manager.save_window_state()
        except Exception:
            pass
        try:
            self._root.destroy()
        except Exception:
            pass

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self._last_render_key = None
        self._schedule_render(delay_ms=60)

    def _schedule_render(self, *, delay_ms: int) -> None:
        now = time.perf_counter()
        if delay_ms <= 1:
            delay_s = 0.0
        else:
            delay_s = delay_ms / 1000.0

        earliest = self._render_scheduled_at + self._render_min_interval_s
        target = max(now + delay_s, earliest)
        wait_ms = max(0, int((target - now) * 1000))

        if self._render_after_id is not None:
            try:
                self._root.after_cancel(self._render_after_id)
            except Exception:
                pass
            self._render_after_id = None

        self._render_scheduled_at = target
        self._render_after_id = self._root.after(wait_ms, self._render_results)

    def _on_mousewheel(self, event: tk.Event) -> None:
        try:
            if self._canvas.winfo_containing(event.x_root, event.y_root) is None:
                return
        except Exception:
            return

        delta = int(getattr(event, "delta", 0))
        if delta == 0:
            return

        units = int(-1 * (delta / 120))
        self._pending_scroll_units += units
        self._scroll_activity_tracker.mark_scroll_active()
        if self._scroll_after_id is None:
            self._scroll_after_id = self._root.after(16, self._flush_scroll)

    def _flush_scroll(self) -> None:
        self._scroll_after_id = None
        units = self._pending_scroll_units
        self._pending_scroll_units = 0
        if units:
            self._canvas.yview_scroll(units, "units")
        self._schedule_render(delay_ms=16)

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)

    def _set_searching(self, searching: bool) -> None:
        self._is_searching = searching
        state = "disabled" if searching else "normal"
        self._search_btn.configure(state=state)

    def _start_search(self) -> None:
        if self._is_searching:
            return

        input_dir = Path(self._input_dir_var.get()).expanduser()
        query = self._query_var.get().strip()

        if not query:
            messagebox.showerror("Invalid query", "Query must not be empty.")
            return
        if not input_dir.exists() or not input_dir.is_dir():
            messagebox.showerror("Invalid input", "Input directory does not exist or is not a directory.")
            return

        self._dir_browser.save_last_input_dir(str(input_dir))

        self._set_searching(True)
        self._set_status("Searching...")

        thread = threading.Thread(target=self._run_search_worker, args=(input_dir, query), daemon=True)
        thread.start()

    def _run_search_worker(self, input_dir: Path, query: str) -> None:
        try:
            conn = connect(constants.DB_PATH)
            try:
                migrate(conn)
                searcher = Searcher()
                result = searcher.search(conn, input_dir=input_dir, query=query)
            finally:
                conn.close()

            self._root.after(0, lambda: self._on_search_complete(result.matches))
        except Exception as ex:
            self._root.after(0, lambda: self._on_search_error(str(ex)))

    def _on_search_error(self, message: str) -> None:
        self._set_searching(False)
        self._set_status("Error")
        messagebox.showerror("Search error", message)

    def _on_search_complete(self, matches: list[SearchMatch]) -> None:
        self._matches = matches
        self._ensure_pool()
        self._recompute_virtual_geometry()
        self._canvas.yview_moveto(0.0)
        self._last_render_key = None
        self._schedule_render(delay_ms=1)

        self._set_searching(False)
        self._set_status(f"Matches: {len(matches)}")

    def _render_results(self) -> None:
        self._render_after_id = None

        if not self._canvas.winfo_exists():
            return

        self._ensure_pool()
        self._recompute_virtual_geometry()

        # Determine first visible row from yview
        y0 = int(self._canvas.canvasy(0))
        first_row = max(0, int(y0 // self._card_h))

        start_index = first_row * self._cols

        render_key = (first_row, self._cols, self._visible_rows, self._card_w, len(self._matches), self._scroll_activity_tracker.is_scroll_active())
        if self._last_render_key and self._last_render_key == render_key:
            self._thumb_cache.ensure_thumb_poller()
            return
        self._last_render_key = render_key
        self._visible_path_by_slot.clear()
        self._visible_hash_by_slot.clear()
        visible_paths: list[str] = []

        def render_canvas_only(*, first_row: int, start_index: int, visible_paths: list[str]) -> None:
            self._ensure_canvas_pool()

            # Label width depends on actual card width after columns/layout.
            left_margin = 10
            right_margin = 10

            for slot, card in enumerate(self._canvas_cards):
                idx = start_index + slot
                if idx >= len(self._matches):
                    self._canvas.itemconfigure(card["bg"], state="hidden")
                    self._canvas.itemconfigure(card["img"], state="hidden")
                    self._canvas.itemconfigure(card["loading"], state="hidden")
                    self._canvas.itemconfigure(card["txt"], state="hidden")
                    continue

                m = self._matches[idx]
                path_text = m.path
                hash_text = getattr(m, "hash", "")
                if hash_text:
                    self._hash_by_path[path_text] = hash_text
                self._visible_path_by_slot[slot] = path_text
                if hash_text:
                    self._visible_hash_by_slot[slot] = hash_text
                visible_paths.append(path_text)

                row = slot // self._cols
                col = slot % self._cols
                x0 = col * self._card_w + self._pad
                y0 = (first_row + row) * self._card_h + self._pad
                w = self._card_w - (self._pad * 2)
                h = self._card_h - (self._pad * 2)
                x1 = x0 + w
                y1 = y0 + h

                self._canvas.coords(card["bg"], x0, y0, x1, y1)
                self._canvas.itemconfigure(card["bg"], state="normal")

                # Image placement
                img_w, img_h = self._thumb_size
                img_x = x0 + (w // 2)
                img_y = y0 + 10 + (img_h // 2)
                self._canvas.coords(card["img"], img_x, img_y)
                self._canvas.itemconfigure(card["img"], state="normal")
                self._canvas.coords(card["loading"], img_x, img_y)

                # Path text (ellipsed + cached)
                txt_x = x0 + left_margin
                label_px = max(60, int(w - (left_margin + right_margin)))
                if label_px != self._last_path_label_px:
                    self._last_path_label_px = label_px
                    # Invalidate per-slot text cache because width changed.
                    self._last_path_text_by_slot.clear()
                cache_key = (path_text, label_px)
                ell = self._ellipsis_cache.get(cache_key)
                if ell is None:
                    ell = self._left_ellipsis_px(text=path_text, max_px=label_px)
                    self._ellipsis_cache[cache_key] = ell
                    self._ellipsis_cache.move_to_end(cache_key)
                    while len(self._ellipsis_cache) > self._ellipsis_cache_max:
                        self._ellipsis_cache.popitem(last=False)
                else:
                    self._ellipsis_cache.move_to_end(cache_key)

                prev_txt = self._last_path_text_by_slot.get(slot)
                if prev_txt != ell:
                    self._last_path_text_by_slot[slot] = ell
                    self._canvas.itemconfigure(card["txt"], text=ell)
                txt_y = y0 + 10 + img_h + 12
                self._canvas.coords(card["txt"], txt_x, txt_y)
                self._canvas.itemconfigure(card["txt"], state="normal")

                # Thumbnail
                if self._scroll_activity_tracker.is_scroll_active():
                    # During active scroll, don't swap images (avoid tearing).
                    self._canvas.itemconfigure(card["img"], image="")
                    if self._show_loading_placeholder:
                        self._canvas.itemconfigure(card["loading"], state="normal")
                else:
                    cache_id = hash_text or path_text
                    tkey = self._thumb_cache.get_key(cache_id)
                    photo = self._thumb_cache.get(tkey)
                    if photo is not None:
                        self._canvas.itemconfigure(card["img"], image=photo)
                        self._canvas.itemconfigure(card["loading"], state="hidden")
                    else:
                        self._canvas.itemconfigure(card["img"], image="")
                        if self._show_loading_placeholder:
                            self._canvas.itemconfigure(card["loading"], state="normal")
                        self._thumb_cache.check_inflight(index=idx, cache_id=cache_id, path_text=path_text)

        render_canvas_only(first_row=first_row, start_index=start_index, visible_paths=visible_paths)

        self._prefetch_thumbs(first_row=first_row, visible_paths=visible_paths)
        self._thumb_cache.ensure_thumb_poller()

    def _ensure_canvas_pool(self) -> None:
        desired = self._cols * self._visible_rows
        if len(self._canvas_cards) == desired:
            return

        # Destroy previous pool
        for c in self._canvas_cards:
            try:
                self._canvas.delete(c["bg"])
                self._canvas.delete(c["img"])
                self._canvas.delete(c["txt"])
            except Exception:
                pass
        self._canvas_cards.clear()

        for slot in range(desired):
            tag = f"card_{slot}"

            bg = self._canvas.create_rectangle(0, 0, 1, 1, fill="#ffffff", outline="#d0d0d0", width=1, tags=(tag, "card"))
            img = self._canvas.create_image(0, 0, anchor="center", tags=(tag, "card"))
            loading = self._canvas.create_text(0, 0, anchor="center", text="Loading", fill="#666666", font=(constants.FONT_FAMILY, constants.FONT_SIZE), tags=(tag, "card"))
            self._canvas.itemconfigure(loading, state="hidden")
            txt = self._canvas.create_text(0, 0, anchor="nw", text="", fill="#000000", font=(constants.FONT_FAMILY, constants.FONT_SIZE), tags=(tag, "card"))
            self._canvas_cards.append({"bg": bg, "img": img, "loading": loading, "txt": txt})

        # Bind once for all cards
        self._canvas.tag_bind("card", "<Enter>", self._on_canvas_card_enter)
        self._canvas.tag_bind("card", "<Leave>", self._on_canvas_card_leave)
        self._canvas.tag_bind("card", "<Motion>", self._on_canvas_card_motion)
        self._canvas.tag_bind("card", "<Double-Button-1>", self._on_canvas_card_double_click)

    def _on_canvas_card_enter(self, event: tk.Event) -> None:
        self._tooltip.hide()
        self._update_hover(event)

    def _on_canvas_card_leave(self, _event: tk.Event) -> None:
        self._cancel_hover()
        self._tooltip.hide()

    def _on_canvas_card_motion(self, event: tk.Event) -> None:
        self._update_hover(event)

    def _on_canvas_card_double_click(self, event: tk.Event) -> None:
        idx = self._index_from_canvas_event(event)
        if idx < 0 or idx >= len(self._matches):
            return
        self._open_file(Path(self._matches[idx].path))

    def _cancel_hover(self) -> None:
        if self._hover_after_id is not None:
            try:
                self._root.after_cancel(self._hover_after_id)
            except Exception:
                pass
            self._hover_after_id = None
        self._hover_tag = None
        self._hover_idx = -1

    def _update_hover(self, event: tk.Event) -> None:
        try:
            xr = int(getattr(event, "x_root", 0))
            yr = int(getattr(event, "y_root", 0))
        except Exception:
            return
        idx = self._index_from_canvas_event(event)
        if idx < 0:
            self._cancel_hover()
            return

        # If we moved to another result, restart timer.
        changed = (idx != self._hover_idx)
        self._hover_idx = idx
        self._hover_x_root = xr
        self._hover_y_root = yr
        if changed:
            self._tooltip.hide()

        self._cancel_hover()
        self._hover_idx = idx
        self._hover_after_id = self._root.after(self._tooltip_hover_delay_ms, self._show_hover_tooltip)

    def _show_hover_tooltip(self) -> None:
        self._hover_after_id = None
        idx = self._hover_idx
        if idx < 0 or idx >= len(self._matches):
            return
        m = self._matches[idx]
        text = f"{m.path}\n\n{m.description}".strip()
        if not text:
            return
        self._tooltip.schedule(text=text, x=self._hover_x_root + 14, y=self._hover_y_root + 14, delay_ms=1)

    def _index_from_canvas_event(self, event: tk.Event) -> int:
        try:
            x = int(getattr(event, "x", 0))
            y = int(getattr(event, "y", 0))
        except Exception:
            return -1
        return self._index_from_canvas_xy(x=x, y=y)

    def _index_from_canvas_xy(self, *, x: int, y: int) -> int:
        if not self._matches:
            return -1
        try:
            cy = float(self._canvas.canvasy(y))
        except Exception:
            cy = float(y)
        row = int(max(0, cy // self._card_h))
        col = int(max(0, x // self._card_w))
        if col >= self._cols:
            return -1
        idx = (row * self._cols) + col
        if idx < 0 or idx >= len(self._matches):
            return -1
        return idx

    def _prefetch_thumbs(self, *, first_row: int, visible_paths: list[str]) -> None:
        # Prefetch a small buffer around the visible area to keep scrolling smooth.
        if not self._matches:
            return

        buffer_rows = 3
        start_row = max(0, first_row - buffer_rows)
        end_row = min(((len(self._matches) + self._cols - 1) // self._cols) - 1, first_row + self._visible_rows + buffer_rows)
        start = start_row * self._cols
        end = min(len(self._matches), (end_row + 1) * self._cols)

        budget = 80
        seen: set[str] = set(visible_paths)

        for i in range(start, end):
            if budget <= 0:
                break
            m = self._matches[i]
            p = m.path
            h = getattr(m, "hash", "")
            if p in seen:
                continue
            seen.add(p)

            cache_id = h or p
            if not self._thumb_cache.check_incache(index=i, cache_id=cache_id, path_text=p):
                continue

            budget -= 1

    def _ensure_pool(self) -> None:
        self._update_card_geometry()

        width = max(1, int(self._canvas.winfo_width()))
        height = max(1, int(self._canvas.winfo_height()))

        cols = max(1, width // self._card_w)
        visible_rows = max(1, (height // self._card_h) + 2)

        if cols == self._cols and visible_rows == self._visible_rows and self._canvas_cards:
            return

        self._cols = cols
        self._visible_rows = visible_rows

        self._ensure_canvas_pool()

        self._last_render_key = None
        self._last_path_text_by_slot.clear()

    def _update_card_geometry(self) -> None:
        # Target: 16/9 preview area + one line of text below.
        # Keep card width fixed, adjust height accordingly.
        # Inner padding is handled by ttk.Frame padding.
        preview_w = self._card_w - (self._pad * 2) - 16
        preview_h = int(preview_w * 9 / 16)
        text_h = 30 + int(self._path_bottom_margin)
        chrome_h = 24
        self._card_h = preview_h + text_h + chrome_h
        self._thumb_size = (max(1, preview_w), max(1, preview_h))

    def _recompute_virtual_geometry(self) -> None:
        if not self._matches:
            self._virtual_total_h = 1
        else:
            rows = (len(self._matches) + self._cols - 1) // self._cols
            self._virtual_total_h = rows * self._card_h
        self._canvas.configure(scrollregion=(0, 0, max(1, self._cols * self._card_w), max(1, self._virtual_total_h)))

    def _left_ellipsis_px(self, text: str, *, max_px: int) -> str:
        def _measure(s: str) -> int:
            if self._measure_font is None:
                return len(s) * 7
            return int(self._measure_font.measure(s))

        if _measure(text) <= max_px:
            return text

        ell = "..."
        if _measure(ell) >= max_px:
            return ell

        keep = text
        while keep and _measure(ell + keep) > max_px:
            keep = keep[1:]
        return ell + keep

    def _open_file(self, path: Path) -> None:
        try:
            if not path.exists():
                messagebox.showerror("File not found", "The selected file does not exist.")
                return
            try:
                self._root.clipboard_clear()
                self._root.clipboard_append(str(path))
            except Exception:
                pass

            try:
                import os

                os.startfile(str(path))
            except Exception:
                subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=False)
        except Exception as ex:
            messagebox.showerror("Open error", str(ex))

def run_gui() -> None:
    App().run()
