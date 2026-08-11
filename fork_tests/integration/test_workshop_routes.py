from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from server_panel.workshop import WorkshopLibrary, invalidate_workshop_cache


@pytest.fixture(autouse=True)
def _admin_user(panel_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "admin"})
    invalidate_workshop_cache()


def _seed_library(tmp_path: Path, payload: dict | None = None) -> tuple[WorkshopLibrary, Path, Path]:
    item = tmp_path / "steamapps" / "workshop" / "content" / "2168680" / "111"
    item.mkdir(parents=True)
    (item / "meta.json").write_text(json.dumps({"title": "Falcon Ridge", "author": "Aviator"}), encoding="utf-8")
    (item / "FalconRidge.json").write_text(json.dumps(payload or {"mission": True}), encoding="utf-8")
    missions = tmp_path / "missions"
    return WorkshopLibrary([item.parent], missions), missions, item


def _local_server() -> dict:
    return {"id": "alpha-operations", "name": "Alpha", "location": "local"}


def _wire_local_mutation(panel_module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, library: WorkshopLibrary):
    config_path = tmp_path / "server" / "DedicatedServerConfig.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}\n", encoding="utf-8")
    servers_path = tmp_path / "servers.json"
    servers_path.write_text(json.dumps({"servers": [_local_server()]}, indent=2), encoding="utf-8")
    monkeypatch.setattr(panel_module, "_find_server_in_unified_view", lambda _server_id: _local_server())
    monkeypatch.setattr(panel_module, "_workshop_library", lambda _server_id: library)
    monkeypatch.setattr(panel_module, "_config_path", lambda _server_id: config_path)
    monkeypatch.setattr(panel_module, "_servers_file_path", lambda: servers_path)
    monkeypatch.setattr(panel_module, "load_servers", lambda: [_local_server()])
    monkeypatch.setattr(panel_module, "_record_config_change", lambda *_args, **_kwargs: {"created": True})
    return config_path, servers_path


def test_workshop_page_and_local_index(client, panel_module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    library, _missions, _item = _seed_library(tmp_path)
    monkeypatch.setattr(panel_module, "_find_server_in_unified_view", lambda _server_id: _local_server())
    monkeypatch.setattr(panel_module, "_workshop_library", lambda _server_id: library)

    page = client.get("/servers/alpha-operations/workshop")
    response = client.get("/api/servers/alpha-operations/workshop?q=falcon")

    assert page.status_code == 200
    assert b"Add to Rotation" in page.data
    payload = response.get_json()
    assert [item["id"] for item in payload["items"]] == ["111"]
    assert payload["capabilities"]["rotation_mutation"] is True
    assert payload["last_refresh_at"]


def test_preview_validates_full_rotation_before_copy(client, panel_module, monkeypatch, tmp_path: Path) -> None:
    library, missions, _item = _seed_library(tmp_path)
    monkeypatch.setattr(panel_module, "_find_server_in_unified_view", lambda _server_id: _local_server())
    monkeypatch.setattr(panel_module, "_workshop_library", lambda _server_id: library)
    monkeypatch.setattr(
        panel_module,
        "_workshop_slots_for_server",
        lambda _server_id: ({}, {"name": "One"}, {"name": "Two"}),
    )

    response = client.post(
        "/api/servers/alpha-operations/workshop/rotation/preview",
        json={"item_id": "111", "placement": "first_available"},
    )

    assert response.status_code == 200
    assert response.get_json()["preview"]["can_apply"] is False
    assert "rotation is full" in response.get_json()["preview"]["apply_error"]
    assert not missions.exists()


def test_conflict_preview_does_not_overwrite(client, panel_module, monkeypatch, tmp_path: Path) -> None:
    library, missions, _item = _seed_library(tmp_path)
    existing = missions / "FalconRidge" / "FalconRidge.json"
    existing.parent.mkdir(parents=True)
    existing.write_text('{"mission": "existing"}', encoding="utf-8")
    monkeypatch.setattr(panel_module, "_find_server_in_unified_view", lambda _server_id: _local_server())
    monkeypatch.setattr(panel_module, "_workshop_library", lambda _server_id: library)
    monkeypatch.setattr(panel_module, "_workshop_slots_for_server", lambda _sid: ({}, {"name": ""}, {"name": ""}))

    response = client.post(
        "/api/servers/alpha-operations/workshop/rotation/preview",
        json={"item_id": "111", "conflict_policy": "error"},
    )

    preview = response.get_json()["preview"]
    assert preview["conflicts"][0]["state"] == "different"
    assert preview["can_apply"] is False
    assert existing.read_text(encoding="utf-8") == '{"mission": "existing"}'


def test_successful_apply_commits_files_config_metadata_and_audit(
    client, panel_module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    library, missions, _item = _seed_library(tmp_path)
    config_path, servers_path = _wire_local_mutation(panel_module, monkeypatch, tmp_path, library)
    audits: list[dict] = []
    monkeypatch.setattr(panel_module.AUDIT_SERVICE, "record", lambda **values: audits.append(values))

    response = client.post(
        "/api/servers/alpha-operations/workshop/rotation",
        json={"item_id": "111", "placement": "first_available", "conflict_policy": "error"},
    )

    assert response.status_code == 200
    assert (missions / "FalconRidge" / "FalconRidge.json").is_file()
    assert json.loads(config_path.read_text())["MissionRotation"][0]["Key"]["Name"] == "FalconRidge"
    assert json.loads(servers_path.read_text())["servers"][0]["mission1_name"] == "FalconRidge"
    assert audits[0]["request_payload"]["partial_collection_acknowledged"] is False


def test_late_audit_failure_rolls_back_every_file(client, panel_module, monkeypatch, tmp_path: Path) -> None:
    library, missions, _item = _seed_library(tmp_path)
    config_path, servers_path = _wire_local_mutation(panel_module, monkeypatch, tmp_path, library)
    config_before = config_path.read_bytes()
    servers_before = servers_path.read_bytes()

    def fail_audit(**_values):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(panel_module.AUDIT_SERVICE, "record", fail_audit)
    response = client.post(
        "/api/servers/alpha-operations/workshop/rotation",
        json={"item_id": "111", "placement": "first_available", "conflict_policy": "error"},
    )

    assert response.status_code == 500
    assert response.get_json()["files_restored"] is True
    assert config_path.read_bytes() == config_before
    assert servers_path.read_bytes() == servers_before
    assert not missions.exists()


def test_remote_library_and_rotation_are_nonmisleading(client, panel_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        panel_module,
        "_find_server_in_unified_view",
        lambda _server_id: {"id": "bravo-training", "location": "remote"},
    )

    library_response = client.get("/api/servers/bravo-training/workshop")
    mutation_response = client.post("/api/servers/bravo-training/workshop/rotation", json={"item_id": "111"})

    assert library_response.get_json()["items"] == []
    assert library_response.get_json()["capabilities"]["rotation_mutation"] is False
    assert mutation_response.status_code == 409
    assert "cannot copy files onto a remote member" in mutation_response.get_json()["error"]


def test_refresh_queues_existing_durable_workshop_job(client, panel_module, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def enqueue(job_type, **kwargs):
        captured.update(job_type=job_type, **kwargs)
        return SimpleNamespace(to_dict=lambda: {"id": "job-workshop", "job_type": job_type})

    monkeypatch.setattr(panel_module, "load_servers", lambda: [{"id": "alpha-operations"}])
    monkeypatch.setattr(panel_module, "_enqueue_job", enqueue)

    response = client.post("/api/sync-workshop-missions", json={"server_id": "alpha-operations"})

    assert response.status_code == 202
    assert response.get_json()["job"]["id"] == "job-workshop"
    assert captured["job_type"] == "workshop_sync"
    assert captured["scope_type"] == "global"
