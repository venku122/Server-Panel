from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from .audit import redact_payload, serialize_payload
from .db import Repository, connect

TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})
RETRYABLE_STATUSES = frozenset({"failed", "cancelled", "interrupted"})


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

    def to_dict(self, events: list[JobEvent] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "job_type": self.job_type,
            "scope_type": self.scope_type,
            "server_id": self.server_id,
            "status": self.status,
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
            "lease_owner": self.lease_owner,
            "lease_expires_at": self.lease_expires_at,
            "parent_job_id": self.parent_job_id,
            "correlation_id": self.correlation_id,
            "replay_safe": self.replay_safe,
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

    def list_jobs(self, server_id: str | None = None, limit: int = 200) -> list[Job]:
        bounded = max(1, min(int(limit), 500))
        if server_id:
            rows = self.connection.execute(
                "SELECT * FROM jobs WHERE server_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (server_id, bounded),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, id DESC LIMIT ?", (bounded,)
            ).fetchall()
        return [self._job(row) for row in rows]

    def events(self, job_id: str) -> list[JobEvent]:
        rows = self.connection.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY sequence", (job_id,)
        ).fetchall()
        return [self._event(row) for row in rows]

    def append_event(self, job_id: str, level: str, message: str, data: Any | None = None) -> JobEvent:
        normalized_level = level if level in {"debug", "info", "warning", "error"} else "info"
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
                str(message)[:4000],
                serialize_payload(data),
                _utc_now(),
            ),
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
        self.append_event(job_id, "info", "Worker claimed job.", {"lease_owner": owner})
        return self.get(job_id)


class JobCancelled(RuntimeError):
    pass


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

    def get(self, job_id: str, include_events: bool = True) -> dict[str, Any] | None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            job = repository.get(job_id)
            if job is None:
                return None
            return job.to_dict(repository.events(job_id) if include_events else None)
        finally:
            connection.close()

    def list(self, server_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        connection = self._connection()
        try:
            return [job.to_dict() for job in JobRepository(connection).list_jobs(server_id, limit)]
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
                raise RuntimeError("The job lease is no longer owned by this worker.")
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
    ) -> None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                job = repository.get(job_id)
                if job is None or job.status != "running" or job.lease_owner != owner:
                    raise RuntimeError("The job lease is no longer owned by this worker.")
                if job.cancel_requested:
                    raise JobCancelled("Cancellation requested at a safe checkpoint.")
                next_current = job.progress_current if current is None else max(0, int(current))
                next_total = job.progress_total if total is None else max(0, int(total))
                connection.execute(
                    """
                    UPDATE jobs
                    SET progress_current = ?, progress_total = ?, updated_at = ?, lease_expires_at = ?
                    WHERE id = ?
                    """,
                    (next_current, next_total, _utc_now(), _lease_deadline(120), job_id),
                )
                if message:
                    repository.append_event(job_id, "info", message, data)
        finally:
            connection.close()

    def append_event(self, job_id: str, level: str, message: str, data: Any | None = None) -> None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
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
                        serialize_payload(result),
                        str(error_summary)[:1000] if error_summary else None,
                        now,
                        now,
                        status,
                        job_id,
                        owner,
                    ),
                ).rowcount
                if changed != 1:
                    raise RuntimeError("The job could not be completed because its lease changed.")
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
                elif job.status == "running":
                    connection.execute(
                        "UPDATE jobs SET cancel_requested = 1, updated_at = ? WHERE id = ?", (now, job_id)
                    )
                    repository.append_event(job_id, "warning", "Cancellation requested.")
                return repository.get(job_id)
        finally:
            connection.close()

    def retry(self, job_id: str, created_by: str, correlation_id: str) -> Job | None:
        connection = self._connection()
        try:
            repository = JobRepository(connection)
            with repository.transaction():
                original = repository.get(job_id)
                if original is None:
                    return None
                if original.status not in RETRYABLE_STATUSES:
                    raise ValueError("Only failed, cancelled, or interrupted jobs can be retried.")
                retried = repository.create(
                    job_type=original.job_type,
                    scope_type=original.scope_type,
                    server_id=original.server_id,
                    parameters=_deserialize(original.parameters_json, {}),
                    created_by=created_by,
                    correlation_id=correlation_id,
                    progress_total=original.progress_total,
                    replay_safe=original.replay_safe,
                    parent_job_id=original.id,
                    attempt=original.attempt + 1,
                )
                repository.append_event(original.id, "info", "A linked retry was queued.", {"retry_job_id": retried.id})
                return retried
        finally:
            connection.close()


JobHandler = Callable[["JobContext", Mapping[str, Any]], Any]


class JobContext:
    def __init__(self, service: JobService, job: Job, owner: str) -> None:
        self.service = service
        self.job = job
        self.owner = owner

    def checkpoint(
        self,
        message: str,
        *,
        current: int | None = None,
        total: int | None = None,
        data: Any | None = None,
    ) -> None:
        self.service.checkpoint(
            self.job.id,
            self.owner,
            message=message,
            current=current,
            total=total,
            data=data,
        )

    def event(self, message: str, level: str = "info", data: Any | None = None) -> None:
        self.service.append_event(self.job.id, level, message, data)


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

    def start(self) -> None:
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self.service.recover_interrupted()
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="server-panel-job-worker", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(max(0.0, timeout))

    def _loop(self) -> None:
        next_recovery = 0.0
        while not self._stop.is_set():
            if time.monotonic() >= next_recovery:
                self.service.recover_interrupted()
                next_recovery = time.monotonic() + 10.0
            if not self.run_once():
                self._stop.wait(self.poll_interval)

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

        def heartbeat() -> None:
            interval = max(0.25, self.lease_seconds / 3)
            while not heartbeat_stop.wait(interval):
                try:
                    self.service.renew(job.id, self.owner, self.lease_seconds)
                except Exception:  # noqa: BLE001 - a lost lease is enforced by finish/checkpoint
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
            result = handler(JobContext(self.service, job, self.owner), parameters)
            terminal_status = "succeeded"
        except JobCancelled as error:
            terminal_status = "cancelled"
            error_summary = str(error)
        except Exception as error:  # noqa: BLE001 - handler failures become durable job failures
            terminal_status = "failed"
            error_summary = str(error) or error.__class__.__name__
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)
        finished = self.service.finish(
            job.id,
            self.owner,
            terminal_status,
            result=redact_payload(result),
            error_summary=error_summary,
        )
        if self.on_terminal is not None:
            try:
                self.on_terminal(finished, terminal_status, result, error_summary)
            except Exception as error:  # noqa: BLE001 - audit callback must not kill the worker
                _ = error
        return True
