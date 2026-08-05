"""Small typed values at moderation service boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def sanitize_dll_url(value: str) -> str:
    """Return an auditable download URL without credentials or request secrets."""
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("dll_url must be an HTTP or HTTPS URL with a host")
    host = parsed.hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path or "/", "", ""))


@dataclass(frozen=True)
class InstallRequest:
    server_id: str
    dll_url: str

    def sanitized(self) -> "InstallRequest":
        server_id = str(self.server_id or "").strip()
        if not server_id:
            raise ValueError("server_id is required")
        return InstallRequest(server_id=server_id, dll_url=sanitize_dll_url(self.dll_url))


@dataclass(frozen=True)
class TicketAction:
    server_id: str
    steam_id: str
    action: str
    actor: str
    text: str | None = None


@dataclass(frozen=True)
class ServiceResult:
    payload: dict[str, Any]
    status: int = 200
