import json
import tkinter as tk
from tkinter import filedialog
from typing import Any

from anyio import Path

from common import constants
from gui.gui_state import GuiStateManager

class DirBrowser():
    _input_dir_var: tk.StringVar
    _gui_state_manager: GuiStateManager

    def __init__(self, gui_state_manager: GuiStateManager) -> None:
        self._input_dir_var = tk.StringVar()
        self._gui_state_manager = gui_state_manager

    def browse_input(self) -> None:
        path = filedialog.askdirectory(initialdir=self._input_dir_var.get() or str(Path.cwd()))
        if path:
            self._input_dir_var.set(path)
            self.save_last_input_dir(path)

    def load_last_input_dir(self) -> str | None:
        try:
            if not constants.GUISTATE_PATH.exists():
                return None
            raw = json.loads(constants.GUISTATE_PATH.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            val = raw.get("last_input_dir")
            if isinstance(val, str) and val.strip():
                return val
            return None
        except Exception:
            return None

    def save_last_input_dir(self, path: str) -> None:
        try:
            self._gui_state_manager.save_gui_state({"last_input_dir": path})
        except Exception:
            pass
