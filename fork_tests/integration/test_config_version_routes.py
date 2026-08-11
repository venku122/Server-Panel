from __future__ import annotations

import json
from pathlib import Path

import pytest

from server_panel.storage import connect, run_migrations
from server_panel.storage.config_versions import ConfigVersionService


def isolated_service(tmp_path: Path, service_type=ConfigVersionService) -> ConfigVersionService:
    database_path = tmp_path / "config-route.sqlite3"
    connection = connect(database_path)
    run_migrations(connection)
    connection.close()
    return service_type(database_path)


def prepare(panel_module, managed_servers, monkeypatch, tmp_path: Path):
    service = isolated_service(tmp_path, panel_module._config_version_storage.ConfigVersionService)
    config_path = tmp_path / "DedicatedServerConfig.json"
    monkeypatch.setattr(panel_module, "CONFIG_VERSION_SERVICE", service)
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "admin"})
    monkeypatch.setattr(panel_module, "_proxy_server_op_if_remote", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(panel_module, "_config_path", lambda _server_id=None: config_path)
    monkeypatch.setattr(
        panel_module,
        "_find_server_in_unified_view",
        lambda server_id: next(server for server in managed_servers if server["id"] == server_id),
    )
    return service, config_path


def test_first_dedicated_save_captures_baseline_diff_noop_and_restore_lineage(
    client, panel_module, managed_servers, monkeypatch, tmp_path: Path
) -> None:
    service, config_path = prepare(panel_module, managed_servers, monkeypatch, tmp_path)
    config_path.write_text('{"ServerName":"Original","FPS":30}', encoding="utf-8")

    first_response = client.post(
        "/api/dedicated-config",
        json={"server_id": "alpha-operations", "config": {"ServerName": "Alpha", "FPS": 60}},
    )
    unchanged_response = client.post(
        "/api/dedicated-config",
        json={"server_id": "alpha-operations", "config": {"FPS": 60, "ServerName": "Alpha"}},
    )
    second_response = client.post(
        "/api/dedicated-config",
        json={"server_id": "alpha-operations", "config": {"ServerName": "Bravo", "FPS": 90}},
    )
    first = first_response.get_json()["config_version"]
    second = second_response.get_json()["config_version"]
    assert first["baseline"]["version_number"] == 1
    assert first["version"]["version_number"] == 2
    assert unchanged_response.get_json()["config_version"]["created"] is False
    assert second["version"]["version_number"] == 3
    diff = client.get(f"/api/config-versions/{second['version']['id']}/diff?server_id=alpha-operations").get_json()[
        "diff"
    ]
    assert {change["path"] for change in diff["changes"]} == {"$.FPS", "$.ServerName"}

    restored = client.post(
        f"/api/config-versions/{first['version']['id']}/restore",
        json={"server_id": "alpha-operations"},
    ).get_json()
    assert restored["success"] is True
    assert restored["version"]["version_number"] == 4
    assert restored["version"]["restored_from_version_id"] == first["version"]["id"]
    assert json.loads(config_path.read_text(encoding="utf-8"))["ServerName"] == "Alpha"
    assert [version["version_number"] for version in service.list(server_id="alpha-operations")] == [4, 3, 2, 1]


def test_metadata_failure_after_replace_restores_previous_file(
    client, panel_module, managed_servers, monkeypatch, tmp_path: Path
) -> None:
    service, config_path = prepare(panel_module, managed_servers, monkeypatch, tmp_path)
    config_path.write_text('{"ServerName":"Before"}\n', encoding="utf-8")

    def fail_save_change(**_values):
        raise RuntimeError("injected SQLite insert failure")

    monkeypatch.setattr(service, "save_change", fail_save_change)
    response = client.post(
        "/api/dedicated-config",
        json={"server_id": "alpha-operations", "config": {"ServerName": "After"}},
    )
    assert response.status_code == 500
    assert "injected SQLite" in response.get_json()["error"]
    assert json.loads(config_path.read_text(encoding="utf-8"))["ServerName"] == "Before"


def test_startup_restore_removes_historically_absent_values_and_preserves_unrelated_args(
    panel_module, monkeypatch, tmp_path: Path
) -> None:
    service = isolated_service(tmp_path, panel_module._config_version_storage.ConfigVersionService)
    monkeypatch.setattr(panel_module, "CONFIG_VERSION_SERVICE", service)
    bat_path = tmp_path / "start-server.bat"
    config_path = tmp_path / "DedicatedServerConfig.json"
    servers_path = tmp_path / "servers.json"
    bat_path.write_text(
        "NuclearOptionServer.exe -log -limitframerate 120 -ServerRemoteCommands 7777\n",
        encoding="utf-8",
    )
    config_path.write_text('{"ServerName":"Alpha","MaxPlayers":64}\n', encoding="utf-8")
    servers = [{"id": "alpha", "name": "Alpha", "remote_commands_port": 7777}]
    servers_path.write_text(json.dumps({"servers": servers}), encoding="utf-8")
    monkeypatch.setattr(panel_module, "_bat_path", lambda _sid: bat_path)
    monkeypatch.setattr(panel_module, "_config_path", lambda _sid=None: config_path)
    monkeypatch.setattr(panel_module, "_servers_file_path", lambda: servers_path)
    monkeypatch.setattr(panel_module, "load_servers", lambda: json.loads(json.dumps(servers)))
    monkeypatch.setattr(panel_module.AUDIT_SERVICE, "record", lambda **_values: None)
    baseline, _created = service.save(
        resource_type="startup_settings",
        resource_id="alpha",
        server_id="alpha",
        content={
            "fps": None,
            "max_players": None,
            "remote_commands_port": None,
            "bat_exists": True,
            "bat_text": "NuclearOptionServer.exe -log\n",
            "max_players_present": False,
            "metadata_remote_commands_port_present": False,
        },
        created_by="review-admin",
        change_summary="Baseline",
    )

    result = panel_module._restore_config_version_local(
        baseline.id,
        expected_server_id="alpha",
        actor="review-admin",
        correlation_id="restore-test",
    )
    assert result["success"] is True
    restored_bat = bat_path.read_text(encoding="utf-8")
    assert "-log" in restored_bat
    assert "limitframerate" not in restored_bat.lower()
    assert "serverremotecommands" not in restored_bat.lower()
    assert "MaxPlayers" not in json.loads(config_path.read_text(encoding="utf-8"))
    stored_server = json.loads(servers_path.read_text(encoding="utf-8"))["servers"][0]
    assert "remote_commands_port" not in stored_server
    startup_versions = service.list(server_id="alpha", resource_type="startup_settings")
    assert startup_versions[0]["restored_from_version_id"] == baseline.id


def test_multifile_startup_restore_rolls_back_every_file_when_version_save_fails(
    panel_module, monkeypatch, tmp_path: Path
) -> None:
    service = isolated_service(tmp_path, panel_module._config_version_storage.ConfigVersionService)
    monkeypatch.setattr(panel_module, "CONFIG_VERSION_SERVICE", service)
    bat_path = tmp_path / "start.bat"
    config_path = tmp_path / "config.json"
    servers_path = tmp_path / "servers.json"
    before_bat = "NuclearOptionServer.exe -limitframerate 120 -ServerRemoteCommands 7777\n"
    before_config = '{"MaxPlayers":64}\n'
    before_servers = '{"servers":[{"id":"alpha","remote_commands_port":7777}]}\n'
    bat_path.write_text(before_bat, encoding="utf-8")
    config_path.write_text(before_config, encoding="utf-8")
    servers_path.write_text(before_servers, encoding="utf-8")
    monkeypatch.setattr(panel_module, "_bat_path", lambda _sid: bat_path)
    monkeypatch.setattr(panel_module, "_config_path", lambda _sid=None: config_path)
    monkeypatch.setattr(panel_module, "_servers_file_path", lambda: servers_path)
    monkeypatch.setattr(
        panel_module,
        "load_servers",
        lambda: [{"id": "alpha", "remote_commands_port": 7777}],
    )
    baseline, _created = service.save(
        resource_type="startup_settings",
        resource_id="alpha",
        server_id="alpha",
        content={
            "fps": None,
            "max_players": None,
            "remote_commands_port": None,
            "max_players_present": False,
            "metadata_remote_commands_port_present": False,
        },
        created_by="review-admin",
        change_summary="Baseline",
    )

    def fail_save(**_values):
        raise RuntimeError("injected restore metadata failure")

    monkeypatch.setattr(service, "save", fail_save)
    with pytest.raises(RuntimeError, match="injected restore"):
        panel_module._restore_config_version_local(
            baseline.id,
            expected_server_id="alpha",
            actor="review-admin",
        )
    assert bat_path.read_text(encoding="utf-8") == before_bat
    assert config_path.read_text(encoding="utf-8") == before_config
    assert servers_path.read_text(encoding="utf-8") == before_servers


def test_remote_history_failure_is_visible_not_an_empty_history(
    client, panel_module, managed_servers, monkeypatch, tmp_path: Path
) -> None:
    prepare(panel_module, managed_servers, monkeypatch, tmp_path)
    monkeypatch.setattr(
        panel_module,
        "_proxy_server_op_if_remote",
        lambda *_args, **_kwargs: ({"success": False, "error": "Remote member unavailable"}, 502),
    )
    response = client.get("/servers/bravo-training/settings/history")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "History unavailable" in html
    assert "Remote member unavailable" in html
    assert "No configuration versions yet" not in html
