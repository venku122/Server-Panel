from __future__ import annotations

import threading
from typing import Any

from server_panel.moderation import (
    InstallRequest,
    ModerationSettingsUpdate,
    ModerationInstaller,
    ModerationPoller,
    ModerationRepository,
    ModerationService,
    TicketAction,
    sanitize_dll_url,
)


def _repository(calls: list[tuple[str, Any]]) -> ModerationRepository:
    def write_settings(server_id: str, values: dict[str, Any]) -> tuple[bool, str | None]:
        calls.append(("settings", (server_id, values)))
        return True, None

    def ticket_action(
        server_id: str, steam_id: str, action: str, text: str | None, actor: str | None
    ) -> tuple[bool, str]:
        calls.append(("ticket", (server_id, steam_id, action, text, actor)))
        return True, "ok"

    def monitor(server_id: str, steam_id: str, actor: str) -> tuple[bool, str]:
        calls.append(("monitor", (server_id, steam_id, actor)))
        return True, "armed"

    return ModerationRepository(
        get_server=lambda server_id: {"id": server_id},
        status_for=lambda server: {"success": True, "installed": server["id"] == "alpha"},
        snapshot_for=lambda server: {"settings": {"server": server["id"]}, "tickets": []},
        write_settings=write_settings,
        apply_ticket_action=ticket_action,
        set_monitor_once=monitor,
    )


def test_repository_keeps_file_and_ticket_callbacks_behind_one_boundary() -> None:
    calls: list[tuple[str, Any]] = []
    repository = _repository(calls)

    assert repository.status("alpha")["installed"] is True
    assert repository.snapshot("bravo")["settings"] == {"server": "bravo"}
    assert repository.save_settings(ModerationSettingsUpdate(server_id="alpha", enable_auto_kick=True)) == (True, None)
    assert repository.apply(
        TicketAction(server_id="alpha", steam_id="7656", action="comment", actor="admin", text="review")
    ) == (True, "ok")
    assert repository.apply(TicketAction(server_id="alpha", steam_id="7656", action="monitor_once", actor="admin")) == (
        True,
        "armed",
    )
    assert [name for name, _value in calls] == ["settings", "ticket", "monitor"]


def test_service_coordinates_installer_durable_job_and_audit() -> None:
    calls: list[tuple[str, Any]] = []
    repository = _repository(calls)
    installer = ModerationInstaller(
        lambda server_id: {"id": server_id},
        lambda server, dll_url: {"success": True, "server": server["id"], "dll_url": dll_url},
    )
    service = ModerationService(
        repository,
        installer,
        enqueue_install=lambda request: {"id": "job-1", "server_id": request.server_id},
        install_job=lambda server_id: {"success": True, "server_id": server_id, "done": False},
        audit=lambda action, server_id, summary, payload, job_id: calls.append(
            ("audit", (action, server_id, summary, payload, job_id))
        ),
    )

    request = InstallRequest(server_id="alpha", dll_url="https://example.invalid/mod.dll")
    queued = service.start_install(request)
    installed = service.install_now(request)
    ticket = service.ticket_action(TicketAction(server_id="alpha", steam_id="7656", action="claim", actor="admin"))

    assert queued.status == 200
    assert queued.payload["job"]["id"] == "job-1"
    assert installed == {"success": True, "server": "alpha", "dll_url": "https://example.invalid/mod.dll"}
    assert ticket.payload["message"] == "ok"
    assert any(name == "audit" for name, _value in calls)


def test_install_url_credentials_query_and_fragment_are_never_persisted() -> None:
    calls: list[tuple[str, Any]] = []
    queued: list[InstallRequest] = []
    repository = _repository(calls)
    installer = ModerationInstaller(
        lambda server_id: {"id": server_id},
        lambda server, dll_url: {"success": True, "server": server["id"], "dll_url": dll_url},
    )

    def enqueue(request: InstallRequest) -> dict[str, str]:
        queued.append(request)
        return {"id": "job-safe"}

    service = ModerationService(
        repository,
        installer,
        enqueue_install=enqueue,
        install_job=lambda server_id: {"server_id": server_id},
        audit=lambda action, server_id, summary, payload, job_id: calls.append(
            ("audit", (action, server_id, summary, payload, job_id))
        ),
    )

    service.start_install(
        InstallRequest(
            server_id="alpha",
            dll_url="https://user:pass@example.invalid/mod.dll?token=secret#fragment",
        )
    )

    assert sanitize_dll_url("https://user:pass@example.invalid/mod.dll?token=secret#fragment") == (
        "https://example.invalid/mod.dll"
    )
    assert queued[0].dll_url == "https://example.invalid/mod.dll"
    audit_payload = next(value for name, value in calls if name == "audit")
    assert audit_payload[3] == {"dll_url": "https://example.invalid/mod.dll"}
    assert "durable" in audit_payload[2]


def test_background_poller_has_explicit_idempotent_thread_owner() -> None:
    entered = threading.Event()
    release = threading.Event()

    def poll_forever() -> None:
        entered.set()
        release.wait(2)

    poller = ModerationPoller(poll_forever)
    poller.start()
    first_thread = poller._thread
    assert entered.wait(1)
    poller.start()
    assert poller._thread is first_thread
    release.set()
