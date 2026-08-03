from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from server_panel.contracts.jobs import JobResult

from .audit import serialize_payload
from .db import Repository, connect

TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})
RETRYABLE_STATUSES = frozenset({"failed", "cancelled", "interrupted"})
MAX_JOB_EVENTS = 1_000
MAX_EVENT_MESSAGE_LENGTH = 2_000

LOGGER = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _lease_deadline(seconds: int) -> str:
    return (
        (datetime.now(timezone.utc) + timedelta(seconds=max(1, seconds)))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _deserialize(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _strict_json_payload(value: Any) -> str | None:
    """Redact a payload only after proving its original shape is JSON-compatible."""
    if value is None:
        return None
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Job results must be finite, JSON-compatible values.") from error
    return cast(str | None, serialize_payload(value))


@dataclass(frozen=True)
class JobEvent:
    id: int
    job_id: str
    sequence: int
    level: str
    message: str
    data_json: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "sequence": self.sequence,
            "level": self.level,
            "message": self.message,
            "data": _deserialize(self.data_json, None),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Job:
    id: str
    job_type: str
    scope_type: str
    server_id: str | None
    status: str
    parameters_json: str
    result_json: str | None
    progress_current: int
    progress_total: int
    created_by: str
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None
    error_summary: str | None
    cancel_requested: bool
    attempt: int
    lease_owner: str | None
    lease_expires_at: str | None
    parent_job_id: str | None
    correlation_id: str
    replay_safe: bool

    def to_dict(
        self,
        events: list[JobEvent] | None = None,
        *,
        include_lease: bool = False,
        last_event: JobEvent | None = None,
    ) -> dict[str, Any]:
        public_status = "cancel_requested" if self.status == "running" and self.cancel_requested else self.status
        payload: dict[str, Any] = {
            "id": self.id,
            "job_type": self.job_type,
            "scope_type": self.scope_type,
            "server_id": self.server_id,
            "status": public_status,
            "parameters": _deserialize(self.parameters_json, {}),
            "result": _deserialize(self.result_json, None),
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_summary": self.error_summary,
            "cancel_requested": self.cancel_requested,
            "attempt": self.attempt,
            "parent_job_id": self.parent_job_id,
            "correlation_id": self.correlation_id,
            "replay_safe": self.replay_safe,
            "last_completed_step": last_event.message if last_event is not None else None,
        }
        if include_lease:
            payload["lease"] = {
                "owner": self.lease_owner,
                "expires_at": self.lease_expires_at,
            }
        if events is not None:
            payload["events"] = [event.to_dict() for event in events]
        return payload


class JobRepository(Repository):
    @staticmethod
    def _job(row: sqlite3.Row) -> Job:
        return Job(
            id=str(row["id"]),
            job_type=str(row["job_type"]),
            scope_type=str(row["scope_type"]),
            server_id=str(row["server_id"]) if row["server_id"] is not None else None,
            status=str(row["status"]),
            parameters_json=str(row["parameters_json"]),
            result_json=str(row["result_json"]) if row["result_json"] is not None else None,
            progress_current=int(row["progress_current"]),
            progress_total=int(row["progress_total"]),
            created_by=str(row["created_by"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            started_at=str(row["started_at"]) if row["started_at"] is not None else None,
            finished_at=str(row["finished_at"]) if row["finished_at"] is not None else None,
            error_summary=str(row["error_summary"]) if row["error_summary"] is not None else None,
            cancel_requested=bool(row["cancel_requested"]),
            attempt=int(row["attempt"]),
            lease_owner=str(row["lease_owner"]) if row["lease_owner"] is not None else None,
            lease_expires_at=(str(row["lease_expires_at"]) if row["lease_expires_at"] is not None else None),
            parent_job_id=str(row["parent_job_id"]) if row["parent_job_id"] is not None else None,
            correlation_id=str(row["correlation_id"]),
            replay_safe=bool(row["replay_safe"]),
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> JobEvent:
        return JobEvent(
            id=int(row["id"]),
            job_id=str(row["job_id"]),
            sequence=int(row["sequence"]),
            level=str(row["level"]),
            message=str(row["message"]),
            data_json=str(row["data_json"]) if row["data_json"] is not None else None,
            created_at=str(row["created_at"]),
        )

    def get(self, job_id: str) -> Job | None:
        row = self.connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job(row) if row is not None else None

    def list_jobs(
        self,
        server_id: str | None = None,
        limit: int = 200,
        *,
        status: str | None = None,
        job_type: str | None = None,
        query: str | None = None,
        since: str | None = None,
    ) -> list[Job]:
        bounded = max(1, min(int(limit), 500))
        clauses: list[str] = []
        parameters: list[Any] = []
        if server_id:
            clauses.append("server_id = ?")
            parameters.append(server_id)
        if status:
            clauses.append(
                "CASE WHEN status = 'running' AND cancel_requested = 1 THEN 'cancel_requested' ELSE status END = ?"
            )
            parameters.append(status)
        if job_type:
            clauses.append("job_type = ?")
            parameters.append(job_type)
        if query:
            needle = f"%{query.strip()}%"
            clauses.append(
                "(id LIKE ? OR job_type LIKE ? OR created_by LIKE ? OR "
                "COALESCE(server_id, '') LIKE ? OR COALESCE(error_summary, '') LIKE ?)"
            )
            parameters.extend((needle, needle, needle, needle, needle))
        if since:
            clauses.append("created_at >= ?")
            parameters.append(since)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(bounded)
        rows = self.connection.execute(
            f"SELECT * FROM jobs{where} ORDER BY created_at DESC, id DESC LIMIT ?",  # noqa: S608
            parameters,
        ).fetchall()
        return [self._job(row) for row in rows]

    def events(self, job_id: str) -> list[JobEvent]:
        rows = self.connection.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY sequence", (job_id,)
        ).fetchall()
        return [self._event(row) for row in rows]

    def last_event(self, job_id: str) -> JobEvent | None:
        row = self.connection.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY sequence DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return self._event(row) if row is not None else None

    def last_completed_step(self, job_id: str) -> JobEvent | None:
        row = self.connection.execute(
            """
            SELECT * FROM job_events
            WHERE job_id = ?
              AND message NOT IN (
                'Job queued.', 'Worker claimed job.', 'Job succeeded.', 'Job failed.',
                'Job cancelled.', 'Job interrupted.', 'Queued job cancelled.'
              )
              AND message NOT LIKE 'A linked retry was queued.%'
              AND message NOT LIKE 'A forced linked retry was queued.%'
              AND message NOT LIKE 'Cancellation requested;%'
              AND message NOT LIKE 'A worker lost ownership%'
              AND message NOT LIKE 'The worker could not persist%'
            ORDER BY sequence DESC LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        return self._event(row) if row is not None else None

    def append_event(self, job_id: str, level: str, message: str, data: Any | None = None) -> JobEvent:
        normalized_level = level if level in {"debug", "info", "warning", "error"} else "info"
        data_json = serialize_payload(data)
        if data_json is not None and len(data_json) > 16_000:
            data_json = serialize_payload(
                {
                    "truncated": True,
                    "original_serialized_bytes": len(data_json.encode("utf-8")),
                }
            )
        sequence_row = self.connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM job_events WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        sequence = int(sequence_row["next_sequence"])
        cursor = self.connection.execute(
            """
            INSERT INTO job_events (job_id, sequence, level, message, data_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                sequence,
                normalized_level,
                str(message)[:MAX_EVENT_MESSAGE_LENGTH],
                data_json,
                _utc_now(),
            ),
        )
        self.connection.execute(
            """
            DELETE FROM job_events
            WHERE job_id = ? AND sequence <= ?
            """,
            (job_id, sequence - MAX_JOB_EVENTS),
        )
        row = self.connection.execute("SELECT * FROM job_events WHERE id = ?", (cursor.lastrowid,)).fetchone()
        if row is None:
            raise RuntimeError("Job event was not readable after insert.")
        return self._event(row)

    def create(
        self,
        *,
        job_type: str,
        scope_type: str,
        server_id: str | None,
        parameters: Mapping[str, Any],
        created_by: str,
        correlation_id: str,
        progress_total: int,
        replay_safe: bool,
        parent_job_id: str | None = None,
        attempt: int = 1,
    ) -> Job:
        now = _utc_now()
        job_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO jobs (
                id, job_type, scope_type, server_id, status, parameters_json, progress_total,
                created_by, created_at, updated_at, attempt, parent_job_id, correlation_id, replay_safe
            ) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                job_type,
                scope_type,
                server_id,
                serialize_payload(dict(parameters)) or "{}",
                max(0, int(progress_total)),
                created_by,
                now,
                now,
                max(1, int(attempt)),
                parent_job_id,
                correlation_id,
                int(replay_safe),
            ),
        )
        self.append_event(job_id, "info", "Job queued.")
        created = self.get(job_id)
        if created is None:
            raise RuntimeError("Job was not readable after insert.")
        return created

    def claim_next(self, owner: str, lease_seconds: int) -> Job | None:
        now = _utc_now()
        row = self.connection.execute(
            """
            SELECT candidate.*
            FROM jobs AS candidate
            WHERE candidate.status = 'queued'
              AND candidate.cancel_requested = 0
              AND NOT EXISTS (
                SELECT 1 FROM jobs AS active
                WHERE active.status = 'running'
                  AND (
                    candidate.server_id IS NULL
                    OR active.server_id IS NULL
                    OR active.server_id = candidate.server_id
                  )
              )
            ORDER BY candidate.created_at, candidate.id
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        job_id = str(row["id"])
        changed = self.connection.execute(
            """
            UPDATE jobs
            SET status = 'running', started_at = COALESCE(started_at, ?), updated_at = ?,
                lease_owner = ?, lease_expires_at = ?
            WHERE id = ? AND status = 'queued' AND cancel_requested = 0
            """,
            (now, now, owner, _lease_deadline(lease_seconds), job_id),
        ).rowcount
        if changed != 1:
            return None
        self.append_event(job_id, "info", "Worker claimed job.")
        return self.get(job_id)


class JobCancelled(RuntimeError):
    pass


class LeaseLost(RuntimeError):
    pass


class ReplayUnsafe(ValueError):
    def __init__(self, message: str, acknowledgement: str, last_completed_step: str | None) -> None:
        super().__init__(message)
        self.acknowledgement = acknowledgement
        self.last_completed_step = last_completed_step


class JobService:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def _connection(self) -> sqlite3.Connection:
        return cast(sqlite3.Connection, connect(self.database_path))

    def create(self, **values: Any) -> Job:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                return repository.create(**values)
        finally:
            connection.close()

    def get(
        self,
        job_id: str,
        include_events: bool = True,
        *,
        include_lease: bool = False,
    ) -> dict[str, Any] | None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            job = repository.get(job_id)
            if job is None:
                return None
            events = repository.events(job_id) if include_events else None
            last_step = repository.last_completed_step(job_id)
            return job.to_dict(events, include_lease=include_lease, last_event=last_step)
        finally:
            connection.close()

    def list(
        self,
        server_id: str | None = None,
        limit: int = 200,
        *,
        status: str | None = None,
        job_type: str | None = None,
        query: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            return [
                job.to_dict(last_event=repository.last_completed_step(job.id))
                for job in repository.list_jobs(
                    server_id,
                    limit,
                    status=status,
                    job_type=job_type,
                    query=query,
                    since=since,
                )
            ]
        finally:
            connection.close()

    def claim_next(self, owner: str, lease_seconds: int = 120) -> Job | None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                return repository.claim_next(owner, lease_seconds)
        finally:
            connection.close()

    def recover_interrupted(self) -> int:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            now = _utc_now()
            with repository.transaction():
                rows = connection.execute(
                    """
                    SELECT id FROM jobs
                    WHERE status = 'running' AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
                    """,
                    (now,),
                ).fetchall()
                for row in rows:
                    job_id = str(row["id"])
                    connection.execute(
                        """
                        UPDATE jobs
                        SET status = 'interrupted', updated_at = ?, finished_at = ?,
                            error_summary = ?, lease_owner = NULL, lease_expires_at = NULL
                        WHERE id = ? AND status = 'running'
                        """,
                        (now, now, "Worker lease expired before completion.", job_id),
                    )
                    repository.append_event(
                        job_id,
                        "error",
                        "Job marked interrupted during startup recovery; it was not replayed.",
                    )
                return len(rows)
        finally:
            connection.close()

    def renew(self, job_id: str, owner: str, lease_seconds: int = 120) -> None:
        connection = self._connection()
        try:
            with connection:
                changed = connection.execute(
                    """
                    UPDATE jobs SET updated_at = ?, lease_expires_at = ?
                    WHERE id = ? AND status = 'running' AND lease_owner = ?
                    """,
                    (_utc_now(), _lease_deadline(lease_seconds), job_id, owner),
                ).rowcount
            if changed != 1:
                raise LeaseLost("The job lease is no longer owned by this worker.")
        finally:
            connection.close()

    def checkpoint(
        self,
        job_id: str,
        owner: str,
        *,
        message: str | None = None,
        current: int | None = None,
        total: int | None = None,
        data: Any | None = None,
        lease_seconds: int = 120,
    ) -> None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                job = repository.get(job_id)
                if job is None or job.status != "running" or job.lease_owner != owner:
                    raise LeaseLost("The job lease is no longer owned by this worker.")
                if job.cancel_requested:
                    raise JobCancelled("Cancellation requested at a safe checkpoint.")
                next_current = job.progress_current if current is None else max(0, int(current))
                next_total = job.progress_total if total is None else max(0, int(total))
                changed = connection.execute(
                    """
                    UPDATE jobs
                    SET progress_current = ?, progress_total = ?, updated_at = ?, lease_expires_at = ?
                    WHERE id = ? AND status = 'running' AND lease_owner = ?
                    """,
                    (
                        next_current,
                        next_total,
                        _utc_now(),
                        _lease_deadline(lease_seconds),
                        job_id,
                        owner,
                    ),
                ).rowcount
                if changed != 1:
                    raise LeaseLost("The job lease changed while saving a checkpoint.")
                if message:
                    repository.append_event(job_id, "info", message, data)
        finally:
            connection.close()

    def append_worker_event(
        self,
        job_id: str,
        owner: str,
        level: str,
        message: str,
        data: Any | None = None,
    ) -> None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                job = repository.get(job_id)
                if job is None or job.status != "running" or job.lease_owner != owner:
                    raise LeaseLost("The job lease is no longer owned by this worker.")
                if job.cancel_requested:
                    raise JobCancelled("Cancellation requested at a safe checkpoint.")
                repository.append_event(job_id, level, message, data)
        finally:
            connection.close()

    def append_system_event(
        self,
        job_id: str,
        level: str,
        message: str,
        data: Any | None = None,
    ) -> None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                if repository.get(job_id) is not None:
                    repository.append_event(job_id, level, message, data)
        finally:
            connection.close()

    def finish(
        self,
        job_id: str,
        owner: str,
        status: str,
        *,
        result: Any | None = None,
        error_summary: str | None = None,
    ) -> Job:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Invalid terminal job status: {status}")
        result_json = _strict_json_payload(result)
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                now = _utc_now()
                changed = connection.execute(
                    """
                    UPDATE jobs
                    SET status = ?, result_json = ?, error_summary = ?, updated_at = ?, finished_at = ?,
                        lease_owner = NULL, lease_expires_at = NULL,
                        progress_current = CASE
                            WHEN ? = 'succeeded' AND progress_total > 0 THEN progress_total
                            ELSE progress_current
                        END
                    WHERE id = ? AND status = 'running' AND lease_owner = ?
                    """,
                    (
                        status,
                        result_json,
                        str(error_summary)[:1000] if error_summary else None,
                        now,
                        now,
                        status,
                        job_id,
                        owner,
                    ),
                ).rowcount
                if changed != 1:
                    raise LeaseLost("The job could not be completed because its lease changed.")
                repository.append_event(
                    job_id,
                    "info" if status == "succeeded" else "error",
                    f"Job {status}.",
                    {"error": error_summary} if error_summary else None,
                )
                job = repository.get(job_id)
                if job is None:
                    raise RuntimeError("Completed job could not be read.")
                return job
        finally:
            connection.close()

    def cancel(self, job_id: str) -> Job | None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                job = repository.get(job_id)
                if job is None:
                    return None
                now = _utc_now()
                if job.status == "queued":
                    connection.execute(
                        """
                        UPDATE jobs SET status = 'cancelled', cancel_requested = 1,
                            updated_at = ?, finished_at = ? WHERE id = ?
                        """,
                        (now, now, job_id),
                    )
                    repository.append_event(job_id, "warning", "Queued job cancelled.")
                elif job.status == "running" and not job.cancel_requested:
                    connection.execute(
                        "UPDATE jobs SET cancel_requested = 1, updated_at = ? WHERE id = ?",
                        (now, job_id),
                    )
                    repository.append_event(
                        job_id,
                        "warning",
                        "Cancellation requested; waiting for the next safe checkpoint. Running subprocesses are not force-killed.",
                    )
                return repository.get(job_id)
        finally:
            connection.close()

    def retry(
        self,
        job_id: str,
        created_by: str,
        correlation_id: str,
        *,
        force: bool = False,
        acknowledgement: str | None = None,
        reason: str | None = None,
    ) -> Job | None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                original = repository.get(job_id)
                if original is None:
                    return None
                if original.status not in RETRYABLE_STATUSES:
                    raise ValueError("Only failed, cancelled, or interrupted jobs can be retried.")
                last_event = repository.last_completed_step(original.id)
                expected_acknowledgement = f"FORCE RETRY {original.id}"
                forced = not original.replay_safe
                if forced and not force:
                    raise ReplayUnsafe(
                        "This job type is not replay-safe. A normal retry was not queued.",
                        expected_acknowledgement,
                        last_event.message if last_event is not None else None,
                    )
                if forced and str(acknowledgement or "").strip() != expected_acknowledgement:
                    raise ReplayUnsafe(
                        "Forced retry acknowledgement did not match the required text.",
                        expected_acknowledgement,
                        last_event.message if last_event is not None else None,
                    )
                normalized_reason = str(reason or "").strip()
                if forced and not normalized_reason:
                    raise ReplayUnsafe(
                        "A reason is required for a forced retry.",
                        expected_acknowledgement,
                        last_event.message if last_event is not None else None,
                    )
                parameters = _deserialize(original.parameters_json, {})
                if forced:
                    parameters = {
                        **parameters,
                        "_forced_retry": {
                            "actor": created_by,
                            "reason": normalized_reason[:500],
                            "source_job_id": original.id,
                            "last_completed_step": last_event.message if last_event is not None else None,
                        },
                    }
                retried = repository.create(
                    job_type=original.job_type,
                    scope_type=original.scope_type,
                    server_id=original.server_id,
                    parameters=parameters,
                    created_by=created_by,
                    correlation_id=correlation_id,
                    progress_total=original.progress_total,
                    replay_safe=original.replay_safe,
                    parent_job_id=original.id,
                    attempt=original.attempt + 1,
                )
                repository.append_event(
                    original.id,
                    "warning" if forced else "info",
                    "A forced linked retry was queued." if forced else "A linked retry was queued.",
                    {
                        "retry_job_id": retried.id,
                        "actor": created_by,
                        "reason": normalized_reason[:500] if forced else None,
                        "last_completed_step": last_event.message if last_event is not None else None,
                    },
                )
                return retried
        finally:
            connection.close()


JobHandler = Callable[["JobContext", Mapping[str, Any]], Any]


class JobContext:
    def __init__(
        self,
        service: JobService,
        job: Job,
        owner: str,
        lease_seconds: int,
        lease_lost: threading.Event,
    ) -> None:
        self.service = service
        self.job = job
        self.owner = owner
        self.lease_seconds = lease_seconds
        self.lease_lost = lease_lost

    def _ensure_lease(self) -> None:
        if self.lease_lost.is_set():
            raise LeaseLost("The worker heartbeat lost this job lease.")

    def checkpoint(
        self,
        message: str,
        *,
        current: int | None = None,
        total: int | None = None,
        data: Any | None = None,
    ) -> None:
        self._ensure_lease()
        self.service.checkpoint(
            self.job.id,
            self.owner,
            message=message,
            current=current,
            total=total,
            data=data,
            lease_seconds=self.lease_seconds,
        )

    def event(self, message: str, level: str = "info", data: Any | None = None) -> None:
        self._ensure_lease()
        self.service.append_worker_event(self.job.id, self.owner, level, message, data)


class JobWorker:
    def __init__(
        self,
        service: JobService,
        handlers: Mapping[str, JobHandler],
        *,
        poll_interval: float = 0.5,
        lease_seconds: int = 120,
        owner: str | None = None,
        on_terminal: Callable[[Job, str, Any | None, str | None], None] | None = None,
    ) -> None:
        self.service = service
        self.handlers = handlers
        self.poll_interval = max(0.05, float(poll_interval))
        self.lease_seconds = max(1, int(lease_seconds))
        self.owner = owner or f"panel-{uuid.uuid4()}"
        self.on_terminal = on_terminal
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._started_at: str | None = None
        self._last_error: str | None = None
        self._last_error_at: str | None = None

    def _record_error(self, error: BaseException) -> None:
        with self._status_lock:
            self._last_error = str(error) or error.__class__.__name__
            self._last_error_at = _utc_now()
        LOGGER.exception("Job worker iteration failed; the worker will continue.", exc_info=error)

    def status(self, *, include_diagnostics: bool = False) -> dict[str, Any]:
        with self._status_lock:
            payload: dict[str, Any] = {
                "alive": bool(self._thread is not None and self._thread.is_alive()),
                "started_at": self._started_at,
                "last_error": self._last_error,
                "last_error_at": self._last_error_at,
                "poll_interval_seconds": self.poll_interval,
                "lease_seconds": self.lease_seconds,
                "multi_process_mode": "supported by atomic SQLite claims and expiring leases",
            }
        if include_diagnostics:
            payload["lease_owner"] = self.owner
        return payload

    def start(self) -> None:
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            try:
                self.service.recover_interrupted()
            except Exception as error:  # noqa: BLE001 - startup must expose, not hide, worker health
                self._record_error(error)
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="server-panel-job-worker", daemon=True)
            with self._status_lock:
                self._started_at = _utc_now()
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(max(0.0, timeout))

    def _loop(self) -> None:
        next_recovery = 0.0
        while not self._stop.is_set():
            try:
                if time.monotonic() >= next_recovery:
                    self.service.recover_interrupted()
                    next_recovery = time.monotonic() + 10.0
                if not self.run_once():
                    self._stop.wait(self.poll_interval)
            except Exception as error:  # noqa: BLE001 - one iteration must never kill the worker
                self._record_error(error)
                self._stop.wait(max(self.poll_interval, 0.5))

    def run_once(self) -> bool:
        job = self.service.claim_next(self.owner, self.lease_seconds)
        if job is None:
            return False
        handler = self.handlers.get(job.job_type)
        parameters = _deserialize(job.parameters_json, {})
        result: Any | None = None
        terminal_status = "failed"
        error_summary: str | None = None
        heartbeat_stop = threading.Event()
        lease_lost = threading.Event()
        lease_error: list[BaseException] = []

        def heartbeat() -> None:
            interval = max(0.25, self.lease_seconds / 3)
            while not heartbeat_stop.wait(interval):
                try:
                    self.service.renew(job.id, self.owner, self.lease_seconds)
                except Exception as error:  # noqa: BLE001 - all renewal failures invalidate ownership
                    lease_error.append(error)
                    lease_lost.set()
                    return

        heartbeat_thread = threading.Thread(
            target=heartbeat,
            name=f"server-panel-job-lease-{job.id[:8]}",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            if handler is None:
                raise RuntimeError(f"No worker handler is registered for {job.job_type!r}.")
            raw_result = handler(
                JobContext(self.service, job, self.owner, self.lease_seconds, lease_lost),
                parameters,
            )
            if lease_lost.is_set():
                raise LeaseLost(str(lease_error[-1]) if lease_error else "The worker heartbeat lost the lease.")
            _strict_json_payload(raw_result)
            try:
                result = JobResult.model_validate(raw_result).root
            except ValidationError as error:
                raise RuntimeError("Job handler returned a non-JSON result.") from error
            terminal_status = "succeeded"
        except JobCancelled as error:
            terminal_status = "cancelled"
            error_summary = str(error)
        except LeaseLost as error:
            LOGGER.warning("Job %s lost its lease; no terminal state will be written by this worker: %s", job.id, error)
            try:
                self.service.append_system_event(
                    job.id,
                    "warning",
                    "A worker lost ownership of this job; handler output and terminal state were discarded.",
                )
            except Exception as diagnostic_error:  # noqa: BLE001 - best-effort diagnostic only
                LOGGER.warning("Could not append lease-loss diagnostic for job %s: %s", job.id, diagnostic_error)
            return True
        except Exception as error:  # noqa: BLE001 - handler failures become durable job failures
            terminal_status = "failed"
            error_summary = str(error) or error.__class__.__name__
            result = None
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)
        try:
            finished = self.service.finish(
                job.id,
                self.owner,
                terminal_status,
                result=result,
                error_summary=error_summary,
            )
        except LeaseLost as error:
            LOGGER.warning("Job %s lost its lease during finalization: %s", job.id, error)
            try:
                self.service.append_system_event(
                    job.id,
                    "warning",
                    "A worker lost ownership while finalizing this job; no terminal state was written.",
                )
            except Exception as diagnostic_error:  # noqa: BLE001 - best-effort diagnostic only
                LOGGER.warning("Could not append finalization diagnostic for job %s: %s", job.id, diagnostic_error)
            return True
        except Exception as error:  # noqa: BLE001 - persistence errors cannot terminate the worker
            self._record_error(error)
            try:
                self.service.append_system_event(
                    job.id,
                    "error",
                    "The worker could not persist this job's terminal state; recovery will mark it interrupted after lease expiry.",
                )
            except Exception as diagnostic_error:  # noqa: BLE001 - best-effort diagnostic only
                LOGGER.warning(
                    "Could not append finalization-failure diagnostic for job %s: %s", job.id, diagnostic_error
                )
            return True
        if self.on_terminal is not None:
            try:
                self.on_terminal(finished, terminal_status, result, error_summary)
            except Exception as error:  # noqa: BLE001 - audit callback must not kill the worker
                _ = error
        return True
