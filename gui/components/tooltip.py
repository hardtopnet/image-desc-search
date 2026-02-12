import tkinter as tk

class Tooltip:
    def __init__(self, *, root: tk.Tk) -> None:
        self._root = root
        self._top: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self._after_id: str | None = None
        self._max_width_px = self._compute_max_width_px()
        self._last_text: str | None = None
        self._last_xy: tuple[int, int] | None = None

    def _compute_max_width_px(self) -> int:
        try:
            half_screen = int(self._root.winfo_screenwidth() / 2)
            return max(800, half_screen)
        except Exception:
            return 800

    def schedule(self, *, text: str, x: int, y: int, delay_ms: int = 350) -> None:
        self.cancel_scheduled()
        self._after_id = self._root.after(delay_ms, lambda: self.show(text=text, x=x, y=y))

    def cancel_scheduled(self) -> None:
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def show(self, *, text: str, x: int, y: int) -> None:
        self._max_width_px = self._compute_max_width_px()

        if self._top is None or self._label is None:
            top = tk.Toplevel(self._root)
            top.wm_overrideredirect(True)
            top.attributes("-topmost", True)

            frame = tk.Frame(top, borderwidth=1, relief="solid", background="#ffffe0")
            frame.pack(fill="both", expand=True)

            label = tk.Label(
                frame,
                justify="left",
                anchor="w",
                background="#ffffe0",
                foreground="#000000",
                padx=8,
                pady=6,
            )
            label.pack(fill="both", expand=True)

            self._top = top
            self._label = label
            self._last_text = None
            self._last_xy = None

        if self._last_text != text:
            # Update text only when it changes to avoid reflow cost.
            self._label.configure(text=text, wraplength=self._max_width_px)
            self._last_text = text

        if self._last_xy != (x, y):
            self._last_xy = (x, y)

        self._top.update_idletasks()

        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        w = self._top.winfo_reqwidth()
        h = self._top.winfo_reqheight()
        pad = 8

        # Prefer showing below the pointer; if there's not enough room,
        # flip above the pointer. Always keep a safe padding on screen.
        x2 = max(pad, min(int(x), int(sw - w - pad)))

        y_int = int(y)
        if (y_int + h + pad) <= sh:
            y2 = y_int
        else:
            y2 = y_int - h - 18
        y2 = max(pad, min(int(y2), int(sh - h - pad)))
        self._top.geometry(f"+{x2}+{y2}")
        try:
            self._top.deiconify()
        except Exception:
            pass

    def hide(self) -> None:
        self.cancel_scheduled()
        if self._top is not None:
            try:
                self._top.withdraw()
            except Exception:
                try:
                    self._top.destroy()
                except Exception:
                    pass
        self._last_text = None
        self._last_xy = None

