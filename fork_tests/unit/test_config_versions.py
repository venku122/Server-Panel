from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from server_panel.storage import connect, run_migrations
from server_panel.storage.config_versions import (
    ConfigVersionService,
    PartialMutationFailure,
    apply_compensating_file_mutation,
    canonical_content,
)


def make_service(tmp_path: Path) -> ConfigVersionService:
    database_path = tmp_path / "panel.sqlite3"
    connection = connect(database_path)
    run_migrations(connection)
    connection.close()
    return ConfigVersionService(database_path)


def save(service: ConfigVersionService, content, **overrides):
    values = {
        "resource_type": "dedicated_server_config",
        "resource_id": "alpha",
        "server_id": "alpha",
        "content": content,
        "created_by": "review-admin",
        "change_summary": "Saved dedicated configuration",
    }
    values.update(overrides)
    return service.save(**values)


def save_change(service: ConfigVersionService, previous, content, **overrides):
    values = {
        "resource_type": "dedicated_server_config",
        "resource_id": "alpha",
        "server_id": "alpha",
        "previous_content": previous,
        "content": content,
        "created_by": "review-admin",
        "change_summary": "Saved dedicated configuration",
    }
    values.update(overrides)
    return service.save_change(**values)


def test_first_change_captures_one_baseline_then_new_version(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    changed, created, baseline = save_change(service, {"ServerName": "Original"}, {"ServerName": "Changed"})
    assert created is True
    assert baseline is not None and baseline.version_number == 1
    assert baseline.content == {"ServerName": "Original"}
    assert changed is not None and changed.version_number == 2

    second, created, duplicate_baseline = save_change(
        service,
        {"ServerName": "Changed"},
        {"ServerName": "Again"},
    )
    assert created is True and second is not None and second.version_number == 3
    assert duplicate_baseline is None
    assert [version["version_number"] for version in service.list(server_id="alpha")] == [3, 2, 1]


def test_noop_save_creates_no_baseline_or_version(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    version, created, baseline = save_change(service, {"FPS": 60}, {"FPS": 60})
    assert (version, created, baseline) == (None, False, None)
    assert service.list(server_id="alpha") == []


def test_concurrent_saves_receive_unique_version_numbers(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    def write(value: int) -> int:
        version, created, _baseline = save_change(
            service,
            {"FPS": 0},
            {"FPS": value},
        )
        assert created and version is not None
        return int(version.version_number)

    with ThreadPoolExecutor(max_workers=6) as pool:
        assigned = sorted(pool.map(write, range(1, 7)))
    assert assigned == [2, 3, 4, 5, 6, 7]
    assert len({version["version_number"] for version in service.list(server_id="alpha")}) == 7


def test_metadata_failure_restores_replaced_and_new_files(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    created = tmp_path / "created.json"
    existing.write_text("before", encoding="utf-8")

    def fail_metadata():
        raise RuntimeError("injected config version save failure")

    with pytest.raises(RuntimeError, match="injected"):
        apply_compensating_file_mutation(
            {existing: b"after", created: b"temporary"},
            fail_metadata,
        )
    assert existing.read_text(encoding="utf-8") == "before"
    assert not created.exists()


def test_rollback_failure_is_an_explicit_partial_failure(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("before", encoding="utf-8")

    def fail_metadata():
        raise RuntimeError("database unavailable")

    def fail_rollback(_path: Path, _content: bytes) -> None:
        raise OSError("rollback disk failure")

    with pytest.raises(PartialMutationFailure) as raised:
        apply_compensating_file_mutation(
            {target: b"after"},
            fail_metadata,
            rollback_file=fail_rollback,
        )
    assert "rollback was incomplete" in str(raised.value)
    assert "rollback disk failure" in raised.value.rollback_failures[0]
    assert target.read_text(encoding="utf-8") == "after"


def test_restore_is_forced_as_new_version_with_lineage(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    first, _created = save(service, {"FPS": None, "remote_commands_port": None})
    _second, _created = save(service, {"FPS": 90, "remote_commands_port": 7777})
    restored, created = save(
        service,
        first.content,
        change_summary="Restored v1",
        restored_from_version_id=first.id,
        restart_required=True,
        force=True,
    )
    assert created is True and restored.version_number == 3
    assert restored.restored_from_version_id == first.id
    assert restored.content["FPS"] is None


def test_diff_and_normalization_remain_structural(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    first, _created = save(service, {"Name": "Alpha", "Nested": {"FPS": 60}, "Text": "a\nb"})
    second, _created = save(service, {"Name": "Bravo", "Nested": {"Port": 7777}, "Text": "a\nc"})
    by_path = {change["path"]: change for change in service.diff(second.id)["changes"]}
    assert by_path["$.Nested.FPS"]["kind"] == "removed"
    assert by_path["$.Nested.Port"]["kind"] == "added"
    assert by_path["$.Text"]["unified"][-1] == "+c"
    assert canonical_content({"a": "one\r\ntwo"})[2] == canonical_content({"a": "one\ntwo"})[2]


def test_resources_are_isolated_and_cross_resource_diff_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    dedicated, _created = save(service, {"FPS": 60})
    startup, _created = save(
        service,
        {"fps": 60},
        resource_type="startup_settings",
        change_summary="Startup",
    )
    with pytest.raises(ValueError, match="same resource"):
        service.diff(dedicated.id, startup.id)
    with pytest.raises(ValueError, match="Unsupported"):
        save(service, {}, resource_type="provider_plan")
