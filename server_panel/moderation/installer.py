"""Install/repair boundary for the public moderation DLL."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

InstallCallback = Callable[[dict[str, Any], str | None], dict[str, Any]]
ServerLookup = Callable[[str], dict[str, Any]]


class ModerationInstaller:
    """Resolve a server and run the existing public-source installer."""

    def __init__(self, get_server: ServerLookup, install_callback: InstallCallback) -> None:
        self._get_server = get_server
        self._install_callback = install_callback

    def install(self, server_id: str, dll_url: str) -> dict[str, Any]:
        return self._install_callback(self._get_server(server_id), dll_url)
