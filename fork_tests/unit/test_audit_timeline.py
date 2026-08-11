from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from server_panel.storage import connect, run_migrations
from server_panel.storage.audit import OUTCOMES, AuditService, redact_payload, serialize_payload


ROOT = Path(__file__).resolve().parents[2]


def redaction_vectors() -> list[dict[str, object]]:
    return cast(
        list[dict[str, object]],
        json.loads((ROOT / "fork_tools/validation/redaction-vectors.json").read_text(encoding="utf-8")),
    )


def materialize_vector(vector: dict[str, object]) -> object:
    repeat = vector.get("repeat")
    if isinstance(repeat, dict):
        return str(repeat["text"]) * int(repeat["count"]) + str(vector.get("suffix") or "")
    return vector["value"]


def make_service(tmp_path: Path):
    connection = connect(tmp_path / "panel.sqlite3")
    run_migrations(connection)
    return connection, AuditService(lambda: connection, tmp_path / "panel_audit.jsonl")


def test_audit_serialization_redacts_and_bounds_payloads() -> None:
    circular: dict[str, object] = {}
    circular["self"] = circular
    payload = {
        "password": "visible-password",
        "nested": {"token": "visible-token"},
        "message": "Bearer visible-bearer?api_key=visible-query",
        "many": {f"key-{index}": index for index in range(60)},
        "circular": circular,
    }

    redacted = redact_payload(payload)
    serialized = serialize_payload(payload)

    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert "visible-bearer" not in serialized
    assert "visible-query" not in serialized
    assert redacted["many"]["__truncated__"] == "10 more keys"
    assert redacted["circular"]["self"] == "[CIRCULAR]"


def test_shared_redaction_vectors_match_client_and_server_contract() -> None:
    for vector in redaction_vectors():
        serialized = json.dumps(redact_payload(materialize_vector(vector)), ensure_ascii=False)
        for forbidden in cast(list[str], vector["forbidden"]):
            assert forbidden not in serialized, vector["id"]
        if vector.get("expect_truncated"):
            assert "… [truncated]" in serialized, vector["id"]


def test_repeated_references_are_not_cycles_but_actual_cycles_are_bounded() -> None:
    shared = {"ordinary": "retained"}
    repeated = redact_payload({"first": shared, "second": shared})
    assert repeated == {"first": shared, "second": shared}

    cycle: list[object] = []
    cycle.append(cycle)
    assert redact_payload(cycle) == ["[CIRCULAR]"]


def test_audit_filtering_outcomes_and_restart_persistence(tmp_path: Path) -> None:
    connection, service = make_service(tmp_path)
    try:
        for index, outcome in enumerate(OUTCOMES):
            service.record(
                actor="reviewadmin" if index < 3 else "operator",
                action=f"server.test.{outcome}",
                correlation_id=f"correlation-{outcome}",
                scope_type="server",
                server_id="alpha" if index < 3 else "bravo",
                target_type="server",
                target_id="alpha" if index < 3 else "bravo",
                outcome=outcome,
                summary=f"Recorded {outcome}",
                request_payload={"password": "hidden", "index": index},
            )

        assert {event["outcome"] for event in service.list_events()} == set(OUTCOMES)
        assert {event["server_id"] for event in service.list_events(actor="reviewadmin")} == {"alpha"}
        failures = service.list_events(server_id="alpha", outcome="failure")
        assert len(failures) == 1
        assert failures[0]["summary"] == "Recorded failure"
        assert failures[0]["request"]["password"] == "[REDACTED]"
    finally:
        connection.close()

    restarted = connect(tmp_path / "panel.sqlite3")
    try:
        persistent = AuditService(lambda: restarted, tmp_path / "panel_audit.jsonl")
        assert len(persistent.list_events()) == 4
        assert persistent.import_legacy() == 0
    finally:
        restarted.close()


def test_legacy_jsonl_import_is_idempotent_and_preserves_source(tmp_path: Path) -> None:
    legacy_path = tmp_path / "panel_audit.jsonl"
    legacy_record = {
        "time": "2026-08-03 10:00:00",
        "user": "legacy-admin",
        "event": "user_password_reset",
        "details": {"username": "legacy-user", "password": "must-not-leak"},
    }
    legacy_path.write_text(json.dumps(legacy_record) + "\n", encoding="utf-8")
    original = legacy_path.read_bytes()
    connection = connect(tmp_path / "panel.sqlite3")
    run_migrations(connection)
    service = AuditService(lambda: connection, legacy_path)
    try:
        assert service.import_legacy() == 1
        assert service.import_legacy() == 0
        events = service.list_events()
        assert len(events) == 1
        assert events[0]["action"] == "panel.user.password_reset"
        assert events[0]["target_id"] == "legacy-user"
        assert events[0]["request"]["password"] == "[REDACTED]"
        assert legacy_path.read_bytes() == original
    finally:
        connection.close()


def test_audit_clear_removes_database_and_legacy_mirror(tmp_path: Path) -> None:
    connection, service = make_service(tmp_path)
    try:
        service.record(actor="admin", action="panel.test", summary="Test")
        assert service.list_events()
        assert (tmp_path / "panel_audit.jsonl").read_text(encoding="utf-8")
        service.clear()
        assert service.list_events() == []
        assert (tmp_path / "panel_audit.jsonl").read_text(encoding="utf-8") == ""
    finally:
        connection.close()


def test_cursor_pagination_crosses_500_equal_timestamp_records_and_preserves_filters(tmp_path: Path) -> None:
    connection, service = make_service(tmp_path)
    try:
        for index in range(550):
            service.record(
                actor="alice" if index % 2 else "bob",
                action="server.update" if index % 3 else "server.start",
                scope_type="server",
                server_id="alpha" if index % 5 else "bravo",
                outcome="success" if index % 7 else "failure",
                created_at="2026-08-04T12:00:00.000Z",
                mirror_legacy=False,
            )

        cursor = None
        ids: list[int] = []
        while True:
            page = service.list_events_page(cursor=cursor, limit=73)
            ids.extend(event["id"] for event in page["events"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert len(ids) == 550
        assert ids == sorted(ids, reverse=True)
        assert len(set(ids)) == 550

        cursor = None
        filtered_ids: list[int] = []
        while True:
            page = service.list_events_page(
                server_id="alpha",
                actor="alice",
                outcome="success",
                action="server.update",
                cursor=cursor,
                limit=7,
            )
            for event in page["events"]:
                filtered_ids.append(event["id"])
                assert event["server_id"] == "alpha"
                assert event["actor"] == "alice"
                assert event["outcome"] == "success"
                assert event["action"] == "server.update"
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert len(filtered_ids) > 7
        assert filtered_ids == sorted(filtered_ids, reverse=True)
    finally:
        connection.close()


def test_jsonl_mirror_failure_keeps_sqlite_event_and_reports_degradation(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = connect(tmp_path / "panel.sqlite3")
    run_migrations(connection)
    mirror_directory = tmp_path / "mirror-directory"
    mirror_directory.mkdir()
    service = AuditService(lambda: connection, mirror_directory)
    try:
        with caplog.at_level("WARNING"):
            event, inserted = service.record(actor="admin", action="panel.test", summary="Mirror failure test")
        assert inserted is True
        assert service.list_events(action="panel.test")[0]["id"] == event.id
        status = service.mirror_status()
        assert status["authoritative_store"] == "sqlite"
        assert status["compatibility_mirror"] == "jsonl"
        assert status["degraded"] is True
        assert status["failure_count"] == 1
        assert "SQLite remains authoritative" in caplog.text
    finally:
        connection.close()
