"""Persistence boundary for the public-source moderation feature."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .models import TicketAction

ServerLookup = Callable[[str], dict[str, Any]]
ServerView = Callable[[dict[str, Any]], dict[str, Any]]
SettingsWriter = Callable[[str, dict[str, Any]], tuple[bool, str | None]]
TicketWriter = Callable[[str, str, str, str | None, str | None], tuple[bool, str]]
MonitorWriter = Callable[[str, str, str], tuple[bool, str]]


class ModerationRepository:
    """Keep route/service code independent from moderation file formats."""

    def __init__(
        self,
        *,
        get_server: ServerLookup,
        status_for: ServerView,
        snapshot_for: ServerView,
        write_settings: SettingsWriter,
        apply_ticket_action: TicketWriter,
        set_monitor_once: MonitorWriter,
    ) -> None:
        self._get_server = get_server
        self._status_for = status_for
        self._snapshot_for = snapshot_for
        self._write_settings = write_settings
        self._apply_ticket_action = apply_ticket_action
        self._set_monitor_once = set_monitor_once

    def status(self, server_id: str) -> dict[str, Any]:
        return self._status_for(self._get_server(server_id))

    def snapshot(self, server_id: str) -> dict[str, Any]:
        return self._snapshot_for(self._get_server(server_id))

    def save_settings(self, server_id: str, values: dict[str, Any]) -> tuple[bool, str | None]:
        return self._write_settings(server_id, values)

    def apply(self, action: TicketAction) -> tuple[bool, str]:
        if action.action == "monitor_once":
            return self._set_monitor_once(action.server_id, action.steam_id, action.actor)
        return self._apply_ticket_action(
            action.server_id,
            action.steam_id,
            action.action,
            action.text,
            action.actor,
        )
