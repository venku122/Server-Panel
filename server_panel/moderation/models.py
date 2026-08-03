"""Small typed values at moderation service boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InstallRequest:
    server_id: str
    dll_url: str


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
