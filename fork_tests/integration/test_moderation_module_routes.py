from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _admin_user(panel_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "admin"})


def _local_server(tmp_path: Path) -> tuple[dict, Path, Path]:
    install_dir = tmp_path / "server"
    config_path = install_dir / "BepInEx" / "config" / "com.nicho.no.killfeedconsole.cfg"
    state_path = install_dir / "BepInEx" / "config" / "NO_KillFeedConsoleAdmin" / "moderation-state.json"
    config_path.parent.mkdir(parents=True)
    state_path.parent.mkdir(parents=True)
    config_path.write_text(
        "[Kick]\nEnableAutoKick = false\nAircraftFriendlyFireTolerance = 0\n"
        "VehicleFriendlyFireTolerance = 1\nShipFriendlyFireTolerance = 0\n"
        "[Discord]\nEnableWebhook = true\n",
        encoding="utf-8",
    )
    state_path.write_text(
        json.dumps(
            {
                "Tickets": [
                    {
                        "OffenderSteamId": "7656",
                        "OffenderName": "Test Pilot",
                        "Status": "open",
                        "UpdatedUtc": "2026-08-03T00:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return {"id": "alpha-operations", "install_dir": str(install_dir)}, config_path, state_path


def test_live_moderation_routes_are_owned_by_blueprint(panel_module) -> None:
    moderation_rules = {
        rule.rule: rule.endpoint for rule in panel_module.app.url_map.iter_rules() if "/moderation/" in rule.rule
    }

    assert moderation_rules == {
        "/api/moderation/status": "moderation.status",
        "/api/moderation/job": "moderation.install_job",
        "/api/moderation/install": "moderation.install",
        "/api/moderation/state": "moderation.state",
        "/api/moderation/settings": "moderation.settings",
        "/api/moderation/ticket_action": "moderation.ticket_action",
        "/api/cluster/servers/moderation/status": "moderation.cluster_status",
        "/api/cluster/servers/moderation/job": "moderation.cluster_job",
        "/api/cluster/servers/moderation/install": "moderation.cluster_install",
        "/api/cluster/servers/moderation/get_state": "moderation.cluster_state",
        "/api/cluster/servers/moderation/set_settings": "moderation.cluster_settings",
        "/api/cluster/servers/moderation/ticket_action": "moderation.cluster_ticket_action",
    }


def test_settings_load_save_and_template_render_compatibility(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server, config_path, _state_path = _local_server(tmp_path)
    updated: dict = {}
    monkeypatch.setattr(panel_module.MODERATION_REPOSITORY, "_get_server", lambda _server_id: server)
    monkeypatch.setattr(panel_module, "get_server_by_id", lambda _server_id: server)
    monkeypatch.setattr(panel_module, "_server_install_dir_for", lambda _server: server["install_dir"])
    monkeypatch.setattr(panel_module, "_update_server_fields", lambda _server_id, values: updated.update(values))
    monkeypatch.setattr(panel_module.MODERATION_SERVICE, "_audit", lambda *_args: None)

    page = client.get("/servers/alpha-operations/moderation")
    before = client.get("/api/moderation/state?server_id=alpha-operations")
    saved = client.post(
        "/api/moderation/settings",
        json={
            "server_id": "alpha-operations",
            "enable_auto_kick": True,
            "aircraft_tolerance": 2,
            "vehicle_tolerance": 3,
            "ship_tolerance": 4,
            "panel_discord_notifications": True,
        },
    )

    assert page.status_code == 200
    assert b"Moderation settings" in page.data
    assert before.status_code == 200
    assert before.get_json()["tickets"][0]["OffenderSteamId"] == "7656"
    assert saved.status_code == 200
    text = config_path.read_text(encoding="utf-8")
    assert "EnableAutoKick = true" in text
    assert "AircraftFriendlyFireTolerance = 2" in text
    assert "EnableWebhook = false" in text
    assert updated["moderation_bot_notifications"] is True


def test_install_route_uses_durable_job_and_legacy_poll_shape(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        panel_module.MODERATION_REPOSITORY,
        "_get_server",
        lambda server_id: {"id": server_id, "install_dir": "/unused"},
    )
    monkeypatch.setitem(
        panel_module.JOB_HANDLERS,
        "moderation_install",
        lambda context, _parameters: context.event("Synthetic moderation install complete.") or {"success": True},
    )
    monkeypatch.setattr(panel_module.MODERATION_SERVICE, "_audit", lambda *_args: None)

    started = client.post("/api/moderation/install", json={"server_id": "alpha-operations"})
    assert started.status_code == 200
    job_id = started.get_json()["job"]["id"]

    detail = None
    for _attempt in range(40):
        detail = panel_module.JOB_SERVICE.get(job_id, include_events=True)
        if detail and detail["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    polled = client.get("/api/moderation/job?server_id=alpha-operations")

    assert detail is not None
    assert detail["job_type"] == "moderation_install"
    assert detail["status"] == "succeeded"
    assert polled.status_code == 200
    assert polled.get_json()["done"] is True
    assert polled.get_json()["ok"] is True
    assert "Synthetic moderation install complete." in polled.get_json()["lines"]


def test_browser_ticket_actor_comes_only_from_authenticated_session(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def apply_ticket(server_id, steam_id, action, text, actor):
        captured.update(server_id=server_id, steam_id=steam_id, action=action, text=text, actor=actor)
        return True, "ok"

    monkeypatch.setattr(panel_module.MODERATION_REPOSITORY, "_apply_ticket_action", apply_ticket)
    monkeypatch.setattr(
        panel_module.MODERATION_REPOSITORY,
        "_get_server",
        lambda server_id: {"id": server_id, "install_dir": "/unused"},
    )
    monkeypatch.setattr(panel_module.MODERATION_REPOSITORY, "_snapshot_for", lambda _server: {"tickets": []})
    monkeypatch.setattr(panel_module.MODERATION_SERVICE, "_audit", lambda *_args: None)

    response = client.post(
        "/api/moderation/ticket_action",
        json={
            "server_id": "alpha-operations",
            "steam_id": "7656",
            "action": "claim",
            "actor": "spoofed-admin",
        },
    )

    assert response.status_code == 200
    assert captured["actor"] == "reviewadmin"


def test_signed_cluster_actor_is_accepted_only_after_verification(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actors: list[str | None] = []

    def apply_signed_actor(_server_id, _steam_id, _action, _text, actor):
        actors.append(actor)
        return True, "ok"

    monkeypatch.setattr(
        panel_module.cluster_state,
        "verify_signed_request",
        lambda *_args, **_kwargs: (True, "verified"),
    )
    monkeypatch.setattr(
        panel_module.MODERATION_REPOSITORY,
        "_apply_ticket_action",
        apply_signed_actor,
    )
    monkeypatch.setattr(
        panel_module.MODERATION_REPOSITORY,
        "_get_server",
        lambda server_id: {"id": server_id, "install_dir": "/unused"},
    )
    monkeypatch.setattr(panel_module.MODERATION_REPOSITORY, "_snapshot_for", lambda _server: {"tickets": []})
    monkeypatch.setattr(panel_module.MODERATION_SERVICE, "_audit", lambda *_args: None)

    verified = client.post(
        "/api/cluster/servers/moderation/ticket_action",
        json={"server_id": "alpha-operations", "steam_id": "7656", "action": "claim", "actor": "node-alpha"},
    )
    monkeypatch.setattr(
        panel_module.cluster_state,
        "verify_signed_request",
        lambda *_args, **_kwargs: (False, "invalid signature"),
    )
    rejected = client.post(
        "/api/cluster/servers/moderation/ticket_action",
        json={"server_id": "alpha-operations", "steam_id": "7656", "action": "claim", "actor": "evil"},
    )

    assert verified.status_code == 200
    assert actors == ["node-alpha"]
    assert rejected.status_code == 401
    assert rejected.get_json()["error"] == "invalid signature"


@pytest.mark.parametrize(
    "path",
    [
        "/api/cluster/servers/moderation/status",
        "/api/cluster/servers/moderation/job",
        "/api/cluster/servers/moderation/install",
        "/api/cluster/servers/moderation/get_state",
        "/api/cluster/servers/moderation/set_settings",
    ],
)
def test_missing_or_invalid_cluster_signature_is_401(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setattr(
        panel_module.cluster_state,
        "verify_signed_request",
        lambda *_args, **_kwargs: (False, "missing signature"),
    )

    response = client.post(path, json={"server_id": "alpha-operations"})

    assert response.status_code == 401
    assert response.get_json() == {"success": False, "error": "missing signature"}


def test_invalid_missing_and_insufficient_permissions_have_stable_statuses(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "mod"})
    forbidden = client.post("/api/moderation/install", json={"server_id": "alpha-operations"})
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "admin"})
    monkeypatch.setattr(
        panel_module.MODERATION_REPOSITORY,
        "_get_server",
        lambda server_id: (_ for _ in ()).throw(KeyError(f"Unknown server_id: {server_id}")),
    )
    missing = client.get("/api/moderation/status?server_id=missing")
    invalid = client.post(
        "/api/moderation/install",
        json={"server_id": "alpha-operations", "dll_url": "file:///tmp/mod.dll"},
    )

    assert forbidden.status_code == 403
    assert missing.status_code == 404
    assert invalid.status_code == 400


def test_install_job_and_audit_persist_only_sanitized_dll_url(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audits: list[tuple] = []
    monkeypatch.setattr(
        panel_module.MODERATION_REPOSITORY,
        "_get_server",
        lambda server_id: {"id": server_id, "install_dir": "/unused"},
    )
    monkeypatch.setattr(
        panel_module.MODERATION_SERVICE,
        "_audit",
        lambda *values: audits.append(values),
    )
    monkeypatch.setitem(
        panel_module.JOB_HANDLERS,
        "moderation_install",
        lambda _context, _parameters: {"success": True},
    )

    response = client.post(
        "/api/moderation/install",
        json={
            "server_id": "alpha-operations",
            "dll_url": "https://user:pass@example.invalid/mod.dll?token=secret#fragment",
        },
    )

    assert response.status_code == 200
    job = panel_module.JOB_SERVICE.get(response.get_json()["job"]["id"])
    assert job["parameters"]["dll_url"] == "https://example.invalid/mod.dll"
    assert audits[0][3] == {"dll_url": "https://example.invalid/mod.dll"}
    serialized = json.dumps({"job": job, "audits": audits})
    assert "user:pass" not in serialized
    assert "token=secret" not in serialized
