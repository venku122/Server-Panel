"""Typed values at moderation service boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from server_panel.contracts.moderation import (
    InstallRequest,
    ModerationSettingsUpdate,
    TicketAction,
    sanitize_dll_url,
)


@dataclass(frozen=True)
class ServiceResult:
    payload: dict[str, Any]
    status: int = 200


__all__ = [
    "InstallRequest",
    "ModerationSettingsUpdate",
    "ServiceResult",
    "TicketAction",
    "sanitize_dll_url",
]
