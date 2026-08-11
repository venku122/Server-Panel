from __future__ import annotations

import pytest

from server_panel.storage import connect


@pytest.fixture(autouse=True)
def _admin_user(panel_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "admin"})


def _assert_contract_error(response) -> None:
    payload = response.get_json()
    assert response.status_code == 400
    assert payload["success"] is False
    assert payload["error"].startswith("Invalid request:")
    assert payload["diagnostics"]


def test_configuration_routes_render_compatible_contract_errors(client) -> None:
    _assert_contract_error(client.post("/api/startup-settings", json={"settings": {"fps": 0}}))
    _assert_contract_error(client.post("/api/dedicated-config", json={"config": ["invalid"]}))


def test_workshop_routes_validate_query_resolve_and_rotation_boundaries(
    client,
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(panel_module, "_find_server_in_unified_view", lambda _server_id: {"id": "alpha"})

    _assert_contract_error(client.get("/api/servers/alpha/workshop?filter=remote"))
    _assert_contract_error(client.post("/api/servers/alpha/workshop/resolve", json={"reference": " "}))
    _assert_contract_error(
        client.post(
            "/api/servers/alpha/workshop/rotation",
            json={"item_id": "111", "placement": "slot3"},
        )
    )


def test_moderation_routes_validate_service_inputs_before_side_effects(client) -> None:
    _assert_contract_error(
        client.post(
            "/api/moderation/settings",
            json={"server_id": "alpha", "aircraft_tolerance": -1},
        )
    )


def test_invalid_persisted_job_row_renders_placeholder_and_warning(client, panel_module) -> None:
    job_id = "invalid-persisted-contract"
    connection = connect(panel_module.PANEL_DATABASE_PATH)
    connection.execute(
        "DELETE FROM jobs WHERE id = ?",
        (job_id,),
    )
    connection.execute(
        """
        INSERT INTO jobs (
            id, job_type, scope_type, server_id, status, parameters_json, result_json,
            progress_current, progress_total, created_by, created_at, updated_at,
            started_at, finished_at, error_summary, cancel_requested, attempt,
            lease_owner, lease_expires_at, parent_job_id, correlation_id, replay_safe
        ) VALUES (?, ?, 'server', 'alpha-operations', 'failed', ?, NULL,
            0, 1, 'mixed-version-node', '2026-08-05T00:00:00Z', '2026-08-05T00:00:00Z',
            NULL, '2026-08-05T00:00:00Z', NULL, 0, 1, NULL, NULL, NULL, 'mixed-version-job', 0)
        """,
        (job_id, "future_peer_job", "{not-json"),
    )
    connection.commit()
    connection.close()

    api_response = client.get("/api/jobs")
    page_response = client.get("/jobs")
    persisted = next(item for item in api_response.get_json()["jobs"] if item["id"] == job_id)

    assert api_response.status_code == 200
    assert persisted["invalid_record"] is True
    assert persisted["job_type"] == "invalid"
    assert persisted["parameters"] == {}
    assert b"could not be fully validated" in page_response.data


def test_job_lease_is_diagnostics_only(client, panel_module) -> None:
    job = panel_module.JOB_SERVICE.create(
        job_type="server_update",
        scope_type="server",
        server_id="alpha-operations",
        parameters={"server_id": "alpha-operations"},
        created_by="lease-test",
        correlation_id="lease-test-correlation",
        progress_total=1,
        replay_safe=False,
    )

    normal = client.get(f"/api/jobs/{job.id}").get_json()["job"]
    diagnostic = client.get(f"/api/jobs/{job.id}?diagnostics=lease").get_json()["job"]

    assert "lease" not in normal
    assert set(diagnostic["lease"]) == {"owner", "expires_at"}


def test_rendered_settings_limits_come_from_shared_backend_constants(client) -> None:
    response = client.get("/servers/alpha-operations/settings")

    assert response.status_code == 200
    assert b'id="startup-fps"' in response.data
    assert b'max="1000"' in response.data
    assert b'id="startup-max-players"' in response.data
    assert b'max="256"' in response.data
    assert b'max="65535"' in response.data
    _assert_contract_error(
        client.post(
            "/api/moderation/ticket_action",
            json={"server_id": "alpha", "steam_id": "7656", "action": "erase"},
        )
    )
    _assert_contract_error(
        client.post(
            "/api/moderation/install",
            json={"server_id": "alpha", "dll_url": "file:///tmp/mod.dll"},
        )
    )
