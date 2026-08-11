from __future__ import annotations

from pathlib import Path

from flask import Flask

from .db import (
    Repository,
    connect,
    get_db,
    init_app,
    initialize_wal,
    resolve_busy_timeout_ms,
    resolve_database_path,
    transaction,
)
from .migrations import Migration, run_migrations


def configure_storage(
    app: Flask,
    base_dir: Path,
    configured_path: str | Path | None = None,
    configured_busy_timeout_ms: str | int | None = None,
) -> Path:
    """Configure request connections and bring the embedded schema up to date."""
    database_path = resolve_database_path(base_dir, configured_path)
    busy_timeout_ms = resolve_busy_timeout_ms(configured_busy_timeout_ms)
    init_app(app, database_path, busy_timeout_ms)
    connection = connect(database_path, busy_timeout_ms)
    try:
        initialize_wal(connection)
        run_migrations(connection)
    finally:
        connection.close()
    return database_path


__all__ = [
    "Migration",
    "Repository",
    "configure_storage",
    "connect",
    "get_db",
    "initialize_wal",
    "resolve_busy_timeout_ms",
    "resolve_database_path",
    "run_migrations",
    "transaction",
]
