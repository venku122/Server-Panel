from __future__ import annotations

from pathlib import Path

import pytest


def test_delete_helper_returns_only_safe_identity(panel_module, monkeypatch: pytest.MonkeyPatch) -> None:
    target = {
        "id": "alpha-operations",
        "name": "Alpha Operations",
        "install_dir": "/sensitive/server/path",
        "password": "must-not-leak",
        "remote_commands_port": 7779,
    }
    monkeypatch.setattr(panel_module, "load_servers", lambda: [target])
    monkeypatch.setattr(panel_module, "save_servers", lambda _servers: None)
    monkeypatch.setattr(panel_module, "_fw_remove_server_rules", lambda _server_id: None)
    monkeypatch.setattr(panel_module, "load_ports", lambda: [])
    monkeypatch.setattr(panel_module, "save_ports", lambda _ports: None)

    payload, status = panel_module._delete_server_local("alpha-operations", False)

    assert status == 200
    assert payload == {
        "success": True,
        "removed": {"id": "alpha-operations", "name": "Alpha Operations"},
        "deleted_files": False,
    }


def test_startup_settings_response_omits_paths_and_server_record(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    startup = tmp_path / "RunServer.bat"
    startup.write_text(
        "NuclearOptionServer.exe -batchmode -limitframerate 60 -ServerRemoteCommands 7779\n",
        encoding="utf-8",
    )
    dedicated = tmp_path / "DedicatedServerConfig.json"
    dedicated.write_text('{"MaxPlayers": 16}\n', encoding="utf-8")
    server = {
        "id": "alpha-operations",
        "name": "Alpha Operations",
        "install_dir": str(tmp_path),
        "password": "must-not-leak",
        "remote_commands_port": 7779,
    }
    monkeypatch.setattr(panel_module, "get_server_by_id", lambda _server_id: server)
    monkeypatch.setattr(panel_module, "_bat_path", lambda _server_id: startup)
    monkeypatch.setattr(panel_module, "_config_path", lambda _server_id: dedicated)
    monkeypatch.setattr(panel_module, "_proxy_server_op_if_remote", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"username": "reviewadmin", "role": "admin"})

    response = client.get("/api/startup-settings?server_id=alpha-operations")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["settings"]["max_players"] == 16
    assert "bat_path" not in payload
    assert "server" not in payload
    assert str(tmp_path) not in response.get_data(as_text=True)
    assert "must-not-leak" not in response.get_data(as_text=True)


def test_remote_delete_response_is_sanitized(client, panel_module, monkeypatch: pytest.MonkeyPatch) -> None:
    remote_payload = {
        "success": True,
        "removed": {
            "id": "alpha-operations",
            "name": "Alpha Operations",
            "install_dir": "/sensitive/server/path",
            "password": "must-not-leak",
        },
        "servers": [{"password": "must-not-leak"}],
    }
    monkeypatch.setattr(
        panel_module,
        "_proxy_server_op_if_remote",
        lambda *_args, **_kwargs: (remote_payload, 200),
    )
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"username": "reviewadmin", "role": "admin"})

    response = client.delete("/api/servers/alpha-operations", json={"delete_files": True})

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "removed": {"id": "alpha-operations", "name": "Alpha Operations"},
        "deleted_files": True,
    }
