"""Contracts for public-main moderation settings and actions."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator

from .base import ContractModel, ServerId


class ServerTarget(ContractModel):
    server_id: ServerId


def sanitize_dll_url(value: str) -> str:
    """Remove credentials and request-only secrets before persistence."""
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("dll_url must be an HTTP or HTTPS URL")
    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    host = f"{hostname}:{parsed.port}" if parsed.port is not None else hostname
    return urlunsplit((parsed.scheme, host, parsed.path or "/", "", ""))


class InstallRequest(ServerTarget):
    dll_url: str = Field(min_length=1, max_length=2048)

    @field_validator("dll_url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        return sanitize_dll_url(value)

    def sanitized(self) -> "InstallRequest":
        return self


class ModerationSettingsUpdate(ServerTarget):
    enable_auto_kick: bool = False
    aircraft_tolerance: int = Field(default=0, ge=0, le=1000)
    vehicle_tolerance: int = Field(default=1, ge=0, le=1000)
    ship_tolerance: int = Field(default=0, ge=0, le=1000)
    panel_discord_notifications: bool = False
    export_moderation_state: bool | None = None
    require_real_player_involved: bool | None = None


class TicketAction(ServerTarget):
    steam_id: str = Field(min_length=1, max_length=32)
    action: Literal[
        "claim",
        "unclaim",
        "close",
        "reopen",
        "comment",
        "kick",
        "ban",
        "unkick",
        "monitor_once",
    ]
    actor: str = Field(default="panel", min_length=1, max_length=200)
    text: str | None = Field(default=None, max_length=4000)
