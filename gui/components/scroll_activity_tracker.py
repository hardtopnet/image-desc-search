from typing import Any

class ScrollActivityTracker:
    def __init__(self, app: Any, idle_ms: int = 540) -> None:
        self._scroll_active = False
        self._scroll_idle_after_id: str | None = None
        self._scroll_idle_ms = idle_ms
        self._app = app

    def mark_scroll_active(self) -> None:
        self._scroll_active = True
        if self._scroll_idle_after_id is not None:
            try:
                self._app._root.after_cancel(self._scroll_idle_after_id)
            except Exception:
                pass
        self._scroll_idle_after_id = self._app._root.after(self._scroll_idle_ms, lambda: self._mark_scroll_idle())

    def is_scroll_active(self) -> bool:
        return self._scroll_active
    
    def _mark_scroll_idle(self) -> None:
        self._scroll_idle_after_id = None
        self._scroll_active = False
        self._app._schedule_render(delay_ms=1)