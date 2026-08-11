from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable, Iterable

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


MIGRATIONS = (
    Migration(1, "sqlite_storage_foundation", _storage_foundation),
    Migration(2, "audit_timeline", _audit_timeline),
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
