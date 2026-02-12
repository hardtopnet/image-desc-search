import json
from typing import Any
from common import constants
import tkinter as tk

class GuiStateManager:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._restoring_window = False
        self._restore_window_state()
        self._root.bind("<Configure>", self._on_root_configure)
        
        self._window_save_after_id: str | None = None
        self._window_save_debounce_ms = 250

    def _load_gui_state(self) -> dict[str, Any] | None:
        try:
            if not constants.GUISTATE_PATH.exists():
                return None
            raw = json.loads(constants.GUISTATE_PATH.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            return raw
        except Exception:
            return None

    def save_gui_state(self, patch: dict[str, Any]) -> None:
        try:
            cur = self._load_gui_state() or {}
            if not isinstance(cur, dict):
                cur = {}
            cur.update(patch)
            constants.GUISTATE_PATH.write_text(json.dumps(cur, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass
    def save_window_state(self) -> None:
        self._window_save_after_id = None
        try:
            geom = self._root.winfo_geometry()
        except Exception:
            geom = None
        try:
            st = self._root.state()
        except Exception:
            st = None
        patch: dict[str, Any] = {}
        if isinstance(geom, str) and geom.strip():
            patch["window_geometry"] = geom
        if isinstance(st, str) and st.strip():
            patch["window_state"] = st
        if patch:
            self.save_gui_state(patch)

    def _restore_window_state(self) -> None:
        state = self._load_gui_state() or {}
        if not isinstance(state, dict):
            return

        geom = state.get("window_geometry")
        wstate = state.get("window_state")

        self._restoring_window = True
        try:
            if isinstance(geom, str) and geom.strip():
                try:
                    self._root.geometry(geom)
                except Exception:
                    pass

            # On Windows, "zoomed" maps to maximized.
            if isinstance(wstate, str) and wstate in {"normal", "zoomed"}:
                try:
                    self._root.state(wstate)
                except Exception:
                    pass
        finally:
            # Allow the first Configure to settle before saving again.
            self._root.after(0, lambda: setattr(self, "_restoring_window", False))

    def _on_root_configure(self, _event: tk.Event) -> None:
        if self._restoring_window:
            return
        if self._window_save_after_id is not None:
            try:
                self._root.after_cancel(self._window_save_after_id)
            except Exception:
                pass
            self._window_save_after_id = None
        self._window_save_after_id = self._root.after(self._window_save_debounce_ms, self.save_window_state)
