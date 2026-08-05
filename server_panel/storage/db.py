from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, cast

from flask import Flask, current_app, g


DATABASE_CONFIG_KEY = "PANEL_DATABASE_PATH"
BUSY_TIMEOUT_CONFIG_KEY = "PANEL_DATABASE_BUSY_TIMEOUT_MS"
DEFAULT_DATABASE_PATH = Path("data/panel.sqlite3")
DEFAULT_BUSY_TIMEOUT_MS = 5000
_REQUEST_CONNECTION_KEY = "panel_database"


class StorageConfigurationError(ValueError):
    """Raised when the configured database cannot provide durable file storage."""


def _reject_memory_database(value: str) -> None:
    normalized = value.strip().lower()
    if normalized == ":memory:" or (normalized.startswith("file:") and "mode=memory" in normalized):
        raise StorageConfigurationError("The production panel database must be file-backed, not in-memory.")


def resolve_database_path(base_dir: Path, configured_path: str | Path | None = None) -> Path:
    """Resolve a configured path without depending on the process working directory."""
    raw = str(configured_path or DEFAULT_DATABASE_PATH).strip()
    if not raw:
        raw = str(DEFAULT_DATABASE_PATH)
    _reject_memory_database(raw)
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def resolve_busy_timeout_ms(configured_timeout_ms: str | int | None = None) -> int:
    """Validate the configured lock wait while retaining the five-second default."""
    raw = (
        DEFAULT_BUSY_TIMEOUT_MS
        if configured_timeout_ms is None or str(configured_timeout_ms).strip() == ""
        else configured_timeout_ms
    )
    try:
        timeout_ms = int(raw)
    except (TypeError, ValueError) as error:
        raise StorageConfigurationError("SQLite busy timeout must be an integer number of milliseconds.") from error
    if timeout_ms < 0 or timeout_ms > 600_000:
        raise StorageConfigurationError("SQLite busy timeout must be between 0 and 600000 milliseconds.")
    return timeout_ms


def connect(database_path: Path, busy_timeout_ms: str | int | None = None) -> sqlite3.Connection:
    """Open one configured SQLite connection for the current request/thread."""
    path = Path(database_path).expanduser().resolve()
    _reject_memory_database(str(path))
    timeout_ms = resolve_busy_timeout_ms(busy_timeout_ms)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        str(path),
        timeout=timeout_ms / 1000,
        isolation_level=None,
        check_same_thread=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {timeout_ms}")
    return connection


def initialize_wal(connection: sqlite3.Connection) -> None:
    """Enable and verify persistent WAL mode once during application startup."""
    selected = connection.execute("PRAGMA journal_mode = WAL").fetchone()
    active = connection.execute("PRAGMA journal_mode").fetchone()
    selected_mode = str(selected[0]).lower() if selected is not None else "unknown"
    active_mode = str(active[0]).lower() if active is not None else "unknown"
    if selected_mode != "wal" or active_mode != "wal":
        raise StorageConfigurationError(
            f"SQLite WAL initialization failed (selected={selected_mode}, active={active_mode}); "
            "verify that the database directory is writable and supports file locking."
        )


@contextmanager
def transaction(connection: sqlite3.Connection, mode: str = "IMMEDIATE") -> Iterator[sqlite3.Connection]:
    """Run a non-nested explicit transaction and always roll back failed work."""
    normalized_mode = mode.strip().upper()
    if normalized_mode not in {"DEFERRED", "IMMEDIATE", "EXCLUSIVE"}:
        raise ValueError(f"Unsupported SQLite transaction mode: {mode}")
    if connection.in_transaction:
        raise RuntimeError("Nested SQLite transactions are not supported by the storage foundation.")
    connection.execute(f"BEGIN {normalized_mode}")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def get_db() -> sqlite3.Connection:
    """Return the Flask-context connection, opening exactly one when first requested."""
    connection = cast(sqlite3.Connection | None, g.get(_REQUEST_CONNECTION_KEY))
    if connection is None:
        configured = current_app.config[DATABASE_CONFIG_KEY]
        connection = connect(Path(configured), current_app.config[BUSY_TIMEOUT_CONFIG_KEY])
        setattr(g, _REQUEST_CONNECTION_KEY, connection)
    return connection


def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop(_REQUEST_CONNECTION_KEY, None)
    if connection is not None:
        connection.close()


def init_app(app: Flask, database_path: Path, busy_timeout_ms: int) -> None:
    app.config[DATABASE_CONFIG_KEY] = str(database_path)
    app.config[BUSY_TIMEOUT_CONFIG_KEY] = busy_timeout_ms
    app.teardown_appcontext(close_db)


class Repository:
    """Small common base for repositories added by later campaign increments."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    @contextmanager
    def transaction(self, mode: str = "IMMEDIATE") -> Iterator[sqlite3.Connection]:
        with transaction(self.connection, mode) as connection:
            yield connection
