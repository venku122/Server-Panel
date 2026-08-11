from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from server_panel.storage import connect, run_migrations
from server_panel.storage.jobs import (
    JobCancelled,
    JobContext,
    JobRepository,
    JobService,
    JobWorker,
    LeaseLost,
    ReplayUnsafe,
)


def make_service(tmp_path: Path) -> tuple[Path, JobService]:
    database_path = tmp_path / "panel.sqlite3"
    connection = connect(database_path)
    run_migrations(connection)
    connection.close()
    return database_path, JobService(database_path)


def create_job(
    service: JobService,
    *,
    job_type: str = "server_update",
    server_id: str | None = "alpha",
    scope_type: str = "server",
    replay_safe: bool = False,
):
    return service.create(
        job_type=job_type,
        scope_type=scope_type,
        server_id=server_id,
        parameters={"server_id": server_id, "password": "must-be-redacted"},
        created_by="review-admin",
        correlation_id="job-test-correlation",
        progress_total=3,
        replay_safe=replay_safe,
    )


def expire_lease(database_path: Path, job_id: str) -> None:
    connection = connect(database_path)
    try:
        connection.execute(
            "UPDATE jobs SET lease_expires_at = '2000-01-01T00:00:00.000Z' WHERE id = ?",
            (job_id,),
        )
    finally:
        connection.close()


def test_job_schema_redaction_event_bounds_and_lease_disclosure(tmp_path: Path) -> None:
    database_path, service = make_service(tmp_path)
    job = create_job(service)
    claimed = service.claim_next("private-worker", lease_seconds=30)
    assert claimed is not None

    connection = connect(database_path)
    try:
        columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(jobs)")}
        assert {
            "status",
            "result_json",
            "cancel_requested",
            "lease_owner",
            "lease_expires_at",
            "parent_job_id",
            "replay_safe",
        } <= columns
        repository = JobRepository(connection)
        with repository.transaction():
            for index in range(1_005):
                repository.append_event(job.id, "info", f"event-{index}", {"token": "hidden"})
        events = repository.events(job.id)
        assert len(events) == 1_000
        assert events[-1].message == "event-1004"
        assert all("hidden" not in str(event.data_json) for event in events)
    finally:
        connection.close()

    ordinary = service.get(job.id)
    diagnostic = service.get(job.id, include_lease=True)
    assert ordinary is not None and "lease" not in ordinary
    assert diagnostic is not None and diagnostic["lease"]["owner"] == "private-worker"


def test_claims_prevent_double_work_and_serialize_conflicting_scopes(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    alpha_first = create_job(service, server_id="alpha")
    alpha_second = create_job(service, server_id="alpha", job_type="noblackbox_install")
    global_job = create_job(service, server_id=None, scope_type="global", job_type="workshop_sync")
    bravo = create_job(service, server_id="bravo")

    assert service.claim_next("worker-one").id == alpha_first.id
    assert service.claim_next("worker-two").id == bravo.id
    assert service.claim_next("worker-three") is None
    service.finish(alpha_first.id, "worker-one", "succeeded", result={"updated": True})
    assert service.claim_next("worker-three").id == alpha_second.id
    service.finish(alpha_second.id, "worker-three", "succeeded")
    assert service.claim_next("worker-three") is None
    service.finish(bravo.id, "worker-two", "succeeded")
    assert service.claim_next("worker-three").id == global_job.id


def test_expired_lease_is_interrupted_and_never_auto_replayed(tmp_path: Path) -> None:
    database_path, service = make_service(tmp_path)
    job = create_job(service)
    assert service.claim_next("dead-worker", lease_seconds=1).id == job.id
    expire_lease(database_path, job.id)

    assert service.recover_interrupted() == 1
    assert service.get(job.id)["status"] == "interrupted"
    executions: list[str] = []
    worker = JobWorker(service, {"server_update": lambda _context, _parameters: executions.append("ran")})
    assert worker.run_once() is False
    assert executions == []


def test_configured_lease_duration_is_used_by_checkpoints(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    job = create_job(service)
    assert service.claim_next("worker", lease_seconds=2).id == job.id
    before = time.time()
    service.checkpoint(job.id, "worker", message="Configured lease", lease_seconds=7)
    claimed = service.get(job.id, include_lease=True)
    expires = claimed["lease"]["expires_at"]
    from datetime import datetime

    deadline = datetime.fromisoformat(expires.replace("Z", "+00:00")).timestamp()
    assert 6 <= deadline - before <= 8


def test_lease_loss_blocks_checkpoint_event_and_terminal_write(tmp_path: Path) -> None:
    database_path, service = make_service(tmp_path)
    job = create_job(service)
    claimed = service.claim_next("former-owner")
    assert claimed is not None
    connection = connect(database_path)
    try:
        connection.execute(
            "UPDATE jobs SET lease_owner = 'new-owner' WHERE id = ?",
            (job.id,),
        )
    finally:
        connection.close()

    with pytest.raises(LeaseLost):
        service.checkpoint(job.id, "former-owner", message="must not persist")
    with pytest.raises(LeaseLost):
        service.append_worker_event(job.id, "former-owner", "info", "must not persist")
    with pytest.raises(LeaseLost):
        service.finish(job.id, "former-owner", "succeeded", result={"unsafe": True})
    messages = [event["message"] for event in service.get(job.id)["events"]]
    assert "must not persist" not in messages
    assert service.get(job.id)["status"] == "running"


def test_renewal_failure_stops_handler_output_and_success_finalization(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    job = create_job(service)

    class RenewalFailureService:
        def __getattr__(self, name):
            return getattr(service, name)

        def renew(self, *_args, **_kwargs):
            raise LeaseLost("renewal deliberately failed")

    def handler(context, _parameters):
        time.sleep(0.45)
        context.event("must not survive lease loss")
        return {"unsafe": True}

    worker = JobWorker(
        RenewalFailureService(),
        {"server_update": handler},
        owner="renewal-failure-worker",
        lease_seconds=1,
    )
    assert worker.run_once() is True
    persisted = service.get(job.id)
    assert persisted["status"] == "running"
    assert "must not survive lease loss" not in [event["message"] for event in persisted["events"]]
    assert any("lost ownership" in event["message"] for event in persisted["events"])


def test_finalization_failure_does_not_kill_worker_and_second_job_succeeds(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    first = create_job(service, server_id="alpha")
    second = create_job(service, server_id="bravo")

    class FinishOnceFailureService:
        failed = False

        def __getattr__(self, name):
            return getattr(service, name)

        def finish(self, *args, **kwargs):
            if not self.failed:
                self.failed = True
                raise sqlite3.OperationalError("deliberate finalization failure")
            return service.finish(*args, **kwargs)

    worker = JobWorker(
        FinishOnceFailureService(),
        {"server_update": lambda _context, parameters: {"server_id": parameters["server_id"]}},
        poll_interval=0.02,
        lease_seconds=2,
    )
    worker.start()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and service.get(second.id)["status"] != "succeeded":
        time.sleep(0.02)
    assert worker.status()["alive"] is True
    worker.stop()
    assert service.get(first.id)["status"] == "running"
    assert service.get(second.id)["status"] == "succeeded"
    assert "deliberate finalization failure" in str(worker.status()["last_error"])


def test_invalid_result_fails_job_and_worker_runs_next_job(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    invalid = create_job(service, server_id="alpha", job_type="invalid")
    valid = create_job(service, server_id="bravo", job_type="valid")
    worker = JobWorker(
        service,
        {"invalid": lambda _context, _parameters: {"not-json"}, "valid": lambda *_args: {"ok": True}},
    )
    assert worker.run_once() is True
    assert worker.run_once() is True
    assert service.get(invalid.id)["status"] == "failed"
    assert "JSON-compatible" in service.get(invalid.id)["error_summary"]
    assert service.get(valid.id)["status"] == "succeeded"


def test_retry_policy_requires_typed_ack_reason_and_records_provenance(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    unsafe = create_job(service, replay_safe=False)
    assert service.claim_next("worker").id == unsafe.id
    service.checkpoint(unsafe.id, "worker", message="Stopped server", current=1)
    service.finish(unsafe.id, "worker", "failed", error_summary="update failed")

    with pytest.raises(ReplayUnsafe) as normal:
        service.retry(unsafe.id, "review-admin", "retry")
    assert normal.value.acknowledgement == f"FORCE RETRY {unsafe.id}"
    assert normal.value.last_completed_step == "Stopped server"
    with pytest.raises(ReplayUnsafe, match="acknowledgement"):
        service.retry(unsafe.id, "review-admin", "retry", force=True, acknowledgement="wrong", reason="ops")
    with pytest.raises(ReplayUnsafe, match="reason"):
        service.retry(
            unsafe.id,
            "review-admin",
            "retry",
            force=True,
            acknowledgement=f"FORCE RETRY {unsafe.id}",
        )

    forced = service.retry(
        unsafe.id,
        "review-admin",
        "retry",
        force=True,
        acknowledgement=f"FORCE RETRY {unsafe.id}",
        reason="verified partial SteamCMD failure",
    )
    assert forced is not None
    forced_payload = service.get(forced.id)
    assert forced_payload["parameters"]["_forced_retry"] == {
        "actor": "review-admin",
        "last_completed_step": "Stopped server",
        "reason": "verified partial SteamCMD failure",
        "source_job_id": unsafe.id,
    }
    service.cancel(forced.id)

    safe = create_job(service, server_id="bravo", job_type="verified_safe", replay_safe=True)
    assert service.claim_next("safe-worker").id == safe.id
    service.finish(safe.id, "safe-worker", "failed", error_summary="transient")
    normal_retry = service.retry(safe.id, "review-admin", "safe-retry")
    assert normal_retry is not None and normal_retry.parent_job_id == safe.id


def test_running_cancel_is_pending_until_safe_checkpoint(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    queued = create_job(service, server_id="alpha")
    cancelled = service.cancel(queued.id)
    assert cancelled is not None and cancelled.status == "cancelled"

    running = create_job(service, server_id="bravo")
    assert service.claim_next("worker").id == running.id
    requested = service.cancel(running.id)
    assert requested is not None and requested.status == "running" and requested.cancel_requested
    public = service.get(running.id)
    assert public["status"] == "cancel_requested"
    assert "safe checkpoint" in public["events"][-1]["message"]
    with pytest.raises(JobCancelled, match="safe checkpoint"):
        service.checkpoint(running.id, "worker", message="Before subprocess")
    service.finish(running.id, "worker", "cancelled", error_summary="Operator cancelled")
    assert service.get(running.id)["status"] == "cancelled"


def test_duplicate_workers_execute_a_job_only_once(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    job = create_job(service)
    calls: list[str] = []
    lock = threading.Lock()

    def handler(_context, _parameters):
        with lock:
            calls.append("called")
        time.sleep(0.05)
        return {"ok": True}

    first = JobWorker(service, {"server_update": handler}, poll_interval=0.01, owner="worker-one")
    second = JobWorker(service, {"server_update": handler}, poll_interval=0.01, owner="worker-two")
    first.start()
    second.start()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and service.get(job.id)["status"] != "succeeded":
        time.sleep(0.02)
    first.stop()
    second.stop()
    assert service.get(job.id)["status"] == "succeeded"
    assert calls == ["called"]


def test_context_uses_worker_lease_and_local_loss_flag(tmp_path: Path) -> None:
    _database_path, service = make_service(tmp_path)
    create_job(service)
    claimed = service.claim_next("worker")
    lost = threading.Event()
    context = JobContext(service, claimed, "worker", 9, lost)
    context.checkpoint("uses nine-second lease")
    assert context.lease_seconds == 9
    lost.set()
    with pytest.raises(LeaseLost, match="heartbeat"):
        context.event("must not be emitted")
