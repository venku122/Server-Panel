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


MIGRATIONS = (Migration(1, "sqlite_storage_foundation", _storage_foundation),)


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
        raise RuntimeError(f"Database contains migrations unknown to this panel version: {unexpected}")

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
