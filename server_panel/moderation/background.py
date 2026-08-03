"""Explicit ownership for the legacy-compatible notification polling hook."""

from __future__ import annotations

import threading
from collections.abc import Callable


class ModerationPoller:
    def __init__(self, poll_forever: Callable[[], None]) -> None:
        self._poll_forever = poll_forever
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._poll_forever, daemon=True, name="moderation-notifications")
        self._thread.start()
