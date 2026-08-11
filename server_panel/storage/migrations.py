from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .db import transaction

MigrationAction = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: MigrationAction

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("Migration versions must be positive integers.")
        if not self.name.strip():
            raise ValueError("Migration names must not be empty.")


def _storage_foundation(_connection: sqlite3.Connection) -> None:
    """Version marker for the schema-migration foundation itself."""


def _audit_timeline(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'server', 'system')),
            server_id TEXT,
            target_type TEXT,
            target_id TEXT,
            outcome TEXT NOT NULL CHECK (outcome IN ('success', 'failure', 'denied', 'unknown')),
            summary TEXT NOT NULL,
            request_json TEXT,
            response_json TEXT,
            job_id TEXT,
            legacy_key TEXT UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX audit_events_created_at_idx ON audit_events (created_at DESC, id DESC)")
    connection.execute("CREATE INDEX audit_events_server_idx ON audit_events (server_id, id DESC)")
    connection.execute("CREATE INDEX audit_events_actor_idx ON audit_events (actor, created_at DESC, id DESC)")
    connection.execute("CREATE INDEX audit_events_outcome_idx ON audit_events (outcome, created_at DESC, id DESC)")
    connection.execute("CREATE INDEX audit_events_action_idx ON audit_events (action, created_at DESC, id DESC)")
    connection.execute("CREATE INDEX audit_events_correlation_idx ON audit_events (correlation_id)")


def _durable_jobs(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'server')),
            server_id TEXT,
            status TEXT NOT NULL CHECK (
                status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted')
            ),
            parameters_json TEXT NOT NULL,
            result_json TEXT,
            progress_current INTEGER NOT NULL DEFAULT 0 CHECK (progress_current >= 0),
            progress_total INTEGER NOT NULL DEFAULT 0 CHECK (progress_total >= 0),
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            error_summary TEXT,
            cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0, 1)),
            attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt >= 1),
            lease_owner TEXT,
            lease_expires_at TEXT,
            parent_job_id TEXT REFERENCES jobs(id),
            correlation_id TEXT NOT NULL,
            replay_safe INTEGER NOT NULL DEFAULT 0 CHECK (replay_safe IN (0, 1))
        )
        """
    )
    connection.execute("CREATE INDEX jobs_created_at_idx ON jobs (created_at DESC, id DESC)")
    connection.execute("CREATE INDEX jobs_server_idx ON jobs (server_id, created_at DESC)")
    connection.execute("CREATE INDEX jobs_claim_idx ON jobs (status, created_at)")
    connection.execute(
        """
        CREATE TABLE job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            sequence INTEGER NOT NULL,
            level TEXT NOT NULL CHECK (level IN ('debug', 'info', 'warning', 'error')),
            message TEXT NOT NULL,
            data_json TEXT,
            created_at TEXT NOT NULL,
            UNIQUE (job_id, sequence)
        )
        """
    )
    connection.execute("CREATE INDEX job_events_job_idx ON job_events (job_id, sequence)")


def _configuration_versions(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE config_versions (
            id TEXT PRIMARY KEY,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            server_id TEXT NOT NULL,
            version_number INTEGER NOT NULL CHECK (version_number >= 1),
            content_json TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            change_summary TEXT NOT NULL,
            restored_from_version_id TEXT REFERENCES config_versions(id),
            restart_required INTEGER NOT NULL DEFAULT 0 CHECK (restart_required IN (0, 1)),
            UNIQUE (resource_type, resource_id, version_number)
        )
        """
    )
    connection.execute(
        "CREATE INDEX config_versions_resource_idx ON config_versions (resource_type, resource_id, version_number DESC)"
    )
    connection.execute("CREATE INDEX config_versions_server_idx ON config_versions (server_id, created_at DESC)")


MIGRATIONS = (
    Migration(1, "sqlite_storage_foundation", _storage_foundation),
    Migration(2, "audit_timeline", _audit_timeline),
    Migration(3, "durable_jobs", _durable_jobs),
    Migration(4, "configuration_versions", _configuration_versions),
)


def _ordered_migrations(migrations: Iterable[Migration]) -> tuple[Migration, ...]:
    ordered = tuple(sorted(migrations, key=lambda migration: migration.version))
    versions = [migration.version for migration in ordered]
    if len(versions) != len(set(versions)):
        raise ValueError("Migration versions must be unique.")
    return ordered


def _ensure_schema_table(connection: sqlite3.Connection) -> None:
    with transaction(connection):
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )


def run_migrations(
    connection: sqlite3.Connection,
    migrations: Iterable[Migration] = MIGRATIONS,
) -> tuple[int, ...]:
    """Apply each pending migration once, committing versions only after success."""
    ordered = _ordered_migrations(migrations)
    _ensure_schema_table(connection)

    known_versions = {migration.version for migration in ordered}
    recorded = connection.execute("SELECT version, name FROM schema_migrations ORDER BY version").fetchall()
    unexpected = [int(row["version"]) for row in recorded if int(row["version"]) not in known_versions]
    if unexpected:
        raise RuntimeError(
            f"Database schema is newer than this panel version (unknown migrations: {unexpected}). "
            "Schema downgrade is unsupported. Upgrade the panel or restore a database copy made for this version; "
            "see docs/sqlite-storage-recovery.md."
        )

    for migration in ordered:
        with transaction(connection):
            existing = connection.execute(
                "SELECT name FROM schema_migrations WHERE version = ?",
                (migration.version,),
            ).fetchone()
            if existing is not None:
                if str(existing["name"]) != migration.name:
                    raise RuntimeError(
                        f"Migration {migration.version} is recorded as {existing['name']!r}, expected {migration.name!r}."
                    )
                continue
            migration.apply(connection)
            connection.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (migration.version, migration.name),
            )

    return tuple(
        int(row["version"])
        for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    )
