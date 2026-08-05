"""Moderation use cases shared by browser and signed cluster routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .installer import ModerationInstaller
from .models import InstallRequest, ServiceResult, TicketAction
from .repository import ModerationRepository

EnqueueInstall = Callable[[InstallRequest], dict[str, Any]]
InstallJob = Callable[[str], dict[str, Any]]
AuditCallback = Callable[[str, str, str, dict[str, Any], str | None], None]


class ModerationService:
    """Coordinate moderation persistence, installation, jobs, and audit."""

    def __init__(
        self,
        repository: ModerationRepository,
        installer: ModerationInstaller,
        *,
        enqueue_install: EnqueueInstall,
        install_job: InstallJob,
        audit: AuditCallback,
    ) -> None:
        self.repository = repository
        self.installer = installer
        self._enqueue_install = enqueue_install
        self._install_job = install_job
        self._audit = audit

    def status(self, server_id: str) -> ServiceResult:
        return ServiceResult(self.repository.status(server_id))

    def install_job(self, server_id: str) -> ServiceResult:
        self.repository.status(server_id)
        return ServiceResult(self._install_job(server_id))

    def start_install(self, request: InstallRequest) -> ServiceResult:
        normalized = request.sanitized()
        self.repository.status(normalized.server_id)
        job = self._enqueue_install(normalized)
        self._audit(
            "moderation.install.queued",
            normalized.server_id,
            "Queued durable moderation module install/repair job",
            {"dll_url": normalized.dll_url},
            str(job.get("id") or "") or None,
        )
        return ServiceResult({"success": True, "started": True, "job": job})

    def install_now(self, request: InstallRequest) -> dict[str, Any]:
        normalized = request.sanitized()
        return self.installer.install(normalized.server_id, normalized.dll_url)

    def state(self, server_id: str) -> ServiceResult:
        snapshot = self.repository.snapshot(server_id)
        return ServiceResult({"success": True, "server_id": server_id, **snapshot})

    def save_settings(self, server_id: str, values: dict[str, Any]) -> ServiceResult:
        saved, error = self.repository.save_settings(server_id, values)
        if not saved:
            return ServiceResult({"success": False, "error": error or "Failed to save moderation settings."}, 400)
        self._audit("moderation.settings.saved", server_id, "Saved moderation settings", values, None)
        return ServiceResult({"success": True, **self.repository.snapshot(server_id)})

    def ticket_action(self, action: TicketAction) -> ServiceResult:
        applied, message = self.repository.apply(action)
        if not applied:
            return ServiceResult({"success": False, "error": message}, 400)
        self._audit(
            f"moderation.ticket.{action.action}",
            action.server_id,
            f"Applied moderation ticket action: {action.action}",
            {"steam_id": action.steam_id, "text": action.text},
            None,
        )
        return ServiceResult({"success": True, "message": message, **self.repository.snapshot(action.server_id)})
