from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from server_panel.contracts import (
    ClusterJobEnqueue,
    DedicatedConfigUpdate,
    JobResult,
    ModerationSettingsUpdate,
    StartupSettingsUpdate,
    WorkshopResolveRequest,
    WorkshopRotationUpdate,
    normalize_job_parameters,
    validation_failure,
)
from server_panel.contracts.jobs import JobView
from server_panel.limits import (
    FPS_MAX,
    FPS_MIN,
    JOB_EVENTS_MAX,
    JOB_LIST_MAX,
    MAX_PLAYERS_MAX,
    PORT_MAX,
    PORT_MIN,
    SERVER_ID_MAX_LENGTH,
)
from server_panel.storage import connect, run_migrations
from server_panel.storage.jobs import JobService, JobWorker
from server_panel.workshop import WorkshopItem


def test_configuration_contracts_normalize_route_values_without_template_types() -> None:
    startup = StartupSettingsUpdate.model_validate(
        {
            "server_id": " alpha ",
            "settings": {
                "fps": "60",
                "max_players": "32",
                "remote_commands_port": "7777",
            },
        }
    )
    dedicated = DedicatedConfigUpdate.model_validate(
        {"server_id": "alpha", "config": {"MaxPlayers": 32, "Nested": {"Enabled": True}}}
    )

    assert startup.server_id == "alpha"
    assert startup.settings.model_dump(exclude_none=True) == {
        "fps": 60,
        "max_players": 32,
        "remote_commands_port": 7777,
    }
    assert dedicated.config_view() == {"MaxPlayers": 32, "Nested": {"Enabled": True}}


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (StartupSettingsUpdate, {"settings": {"remote_commands_port": 70000}}),
        (DedicatedConfigUpdate, {"config": ["not", "an", "object"]}),
        (WorkshopResolveRequest, {"reference": "   "}),
        (WorkshopRotationUpdate, {"item_id": "123", "placement": "slot3"}),
        (ModerationSettingsUpdate, {"server_id": "alpha", "aircraft_tolerance": -1}),
        (ClusterJobEnqueue, {"job_type": "delete_everything", "server_id": "alpha"}),
    ],
)
def test_invalid_contracts_are_rejected(model, payload: object) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_validation_error_keeps_legacy_rendering_shape_and_adds_diagnostics() -> None:
    with pytest.raises(ValidationError) as captured:
        WorkshopRotationUpdate.model_validate({"item_id": "", "placement": "slot3"})

    payload = validation_failure(captured.value)

    assert payload["success"] is False
    assert str(payload["error"]).startswith("Invalid request:")
    assert payload["diagnostics"]
    assert {"field", "message", "code"} <= set(payload["diagnostics"][0])


def test_job_parameters_and_results_are_json_typed_and_normalized() -> None:
    assert normalize_job_parameters(
        "workshop_sync",
        {"server_id": " alpha ", "local_only": 1},
    ) == {"server_id": "alpha", "local_only": True, "all_servers": False}
    assert JobResult.model_validate({"success": True, "count": 2}).root == {
        "success": True,
        "count": 2,
    }

    with pytest.raises(ValidationError):
        JobResult.model_validate({"path": Path("not-json")})


def test_worker_rejects_non_json_result_at_the_durable_service_boundary(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    connection = connect(database_path)
    run_migrations(connection)
    connection.close()
    service = JobService(database_path)
    job = service.create(
        job_type="server_update",
        scope_type="server",
        server_id="alpha",
        parameters={"server_id": "alpha"},
        created_by="contract-test",
        correlation_id="contract-test-correlation",
        progress_total=1,
        replay_safe=False,
    )
    worker = JobWorker(service, {"server_update": lambda _context, _parameters: Path("not-json")})

    assert worker.run_once() is True
    completed = service.get(job.id)
    assert completed is not None
    assert completed["status"] == "failed"
    assert "json-compatible" in completed["error_summary"].lower()
    assert "not-json" not in str(completed)


def test_workshop_metadata_contract_renders_a_plain_view_model() -> None:
    item = WorkshopItem(
        item_id="111",
        title=" Falcon Ridge ",
        author=None,
        content_type="mission",
        source="steam_cache",
        installed=True,
        local=True,
        updated_at=None,
        metadata_available=False,
        mission_names=["FalconRidge"],
    )

    view = item.to_dict()

    assert isinstance(view, dict)
    assert view["title"] == "Falcon Ridge"
    assert view["can_add"] is True


def test_shared_limits_match_backend_contract_and_public_ui_policy() -> None:
    assert (FPS_MIN, FPS_MAX) == (1, 1000)
    assert MAX_PLAYERS_MAX == 256
    assert (PORT_MIN, PORT_MAX) == (1, 65535)
    assert SERVER_ID_MAX_LENGTH == 200
    assert (JOB_EVENTS_MAX, JOB_LIST_MAX) == (1000, 500)
    with pytest.raises(ValidationError):
        StartupSettingsUpdate.model_validate({"settings": {"max_players": 257}})
    with pytest.raises(ValidationError):
        ClusterJobEnqueue.model_validate({"job_type": "server_update", "server_id": "s" * (SERVER_ID_MAX_LENGTH + 1)})


def test_job_dispatch_rejects_unknown_types_and_accepts_mixed_version_cluster_payloads() -> None:
    with pytest.raises(ValueError, match="Unsupported job type"):
        normalize_job_parameters("future_unknown_job", {})

    old_peer = ClusterJobEnqueue.model_validate(
        {"job_type": "moderation_install", "server_id": "alpha", "parameters": {}}
    )
    newer_peer = ClusterJobEnqueue.model_validate(
        {
            "job_type": "server_update",
            "server_id": "alpha",
            "contract_version": 2,
            "future_additive_capability": True,
        }
    )

    assert old_peer.contract_version == 1
    assert newer_peer.contract_version == 2


def test_public_job_contract_has_no_normal_lease_fields() -> None:
    assert "lease_owner" not in JobView.model_fields
    assert "lease_expires_at" not in JobView.model_fields
    assert "lease" not in JobView.model_fields


def test_non_json_secret_repr_is_not_persisted(tmp_path: Path) -> None:
    class SecretResult:
        def __repr__(self) -> str:
            return "SecretResult(token=do-not-persist)"

    database_path = tmp_path / "secret-job.sqlite3"
    connection = connect(database_path)
    run_migrations(connection)
    connection.close()
    service = JobService(database_path)
    job = service.create(
        job_type="server_update",
        scope_type="server",
        server_id="alpha",
        parameters={"server_id": "alpha"},
        created_by="contract-test",
        correlation_id="contract-test-correlation",
        progress_total=1,
        replay_safe=False,
    )
    worker = JobWorker(service, {"server_update": lambda _context, _parameters: SecretResult()})

    assert worker.run_once() is True
    serialized = str(service.get(job.id))
    assert "do-not-persist" not in serialized
    assert "json-compatible" in serialized.lower()
