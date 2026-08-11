from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from server_panel.storage import Migration, Repository, configure_storage, connect, get_db, run_migrations, transaction
from server_panel.storage.db import StorageConfigurationError, resolve_busy_timeout_ms, resolve_database_path


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def test_fresh_creation_uses_required_pragmas_and_only_schema_metadata(tmp_path: Path) -> None:
    app = Flask("sqlite-fresh")
    database_path = configure_storage(app, tmp_path, "state/panel.sqlite3")

    assert database_path == (tmp_path / "state" / "panel.sqlite3").resolve()
    assert database_path.is_file()
    connection = connect(database_path)
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert table_names(connection) == {"audit_events", "schema_migrations"}
        assert run_migrations(connection) == (1, 2)
    finally:
        connection.close()


def test_wal_is_initialized_once_and_persists_for_later_connections(tmp_path: Path) -> None:
    database_path = tmp_path / "panel.sqlite3"
    first = connect(database_path)
    try:
        assert first.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        first.close()

    configure_storage(Flask("sqlite-wal"), tmp_path, database_path)
    reopened = connect(database_path)
    try:
        assert reopened.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        reopened.close()


def test_configurable_busy_timeout_is_used_by_request_connections(tmp_path: Path) -> None:
    app = Flask("sqlite-timeout")
    configure_storage(app, tmp_path, "panel.sqlite3", 1379)

    with app.app_context():
        connection = get_db()
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 1379
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    assert resolve_busy_timeout_ms(None) == 5000
    assert resolve_busy_timeout_ms("0") == 0
    with pytest.raises(StorageConfigurationError, match="integer"):
        resolve_busy_timeout_ms("later")
    with pytest.raises(StorageConfigurationError, match="between 0 and 600000"):
        resolve_busy_timeout_ms(600_001)


def test_repeated_startup_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "panel.sqlite3"
    first = connect(database_path)
    try:
        assert run_migrations(first) == (1, 2)
        assert run_migrations(first) == (1, 2)
        assert first.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2
    finally:
        first.close()

    restarted = connect(database_path)
    try:
        assert run_migrations(restarted) == (1, 2)
    finally:
        restarted.close()


def test_custom_migration_runs_once(tmp_path: Path) -> None:
    calls = 0

    def add_probe(connection: sqlite3.Connection) -> None:
        nonlocal calls
        calls += 1
        connection.execute("CREATE TABLE migration_probe (value TEXT NOT NULL)")

    migrations = (
        Migration(1, "foundation", lambda _connection: None),
        Migration(2, "probe", add_probe),
    )
    connection = connect(tmp_path / "panel.sqlite3")
    try:
        assert run_migrations(connection, migrations) == (1, 2)
        assert run_migrations(connection, migrations) == (1, 2)
        assert calls == 1
        assert "migration_probe" in table_names(connection)
    finally:
        connection.close()


def test_failed_migration_rolls_back_schema_and_version(tmp_path: Path) -> None:
    def fail_after_write(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE rolled_back_probe (value TEXT NOT NULL)")
        connection.execute("INSERT INTO rolled_back_probe (value) VALUES ('temporary')")
        raise RuntimeError("intentional migration failure")

    migrations = (
        Migration(1, "foundation", lambda _connection: None),
        Migration(2, "failure", fail_after_write),
    )
    connection = connect(tmp_path / "panel.sqlite3")
    try:
        with pytest.raises(RuntimeError, match="intentional migration failure"):
            run_migrations(connection, migrations)
        assert "rolled_back_probe" not in table_names(connection)
        versions = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        assert [row["version"] for row in versions] == [1]
        assert connection.in_transaction is False
    finally:
        connection.close()


def test_multiple_connections_share_committed_state(tmp_path: Path) -> None:
    database_path = tmp_path / "panel.sqlite3"
    first = connect(database_path)
    second = connect(database_path)
    try:
        run_migrations(first)
        with transaction(first):
            first.execute("CREATE TABLE connection_probe (value TEXT NOT NULL)")
            first.execute("INSERT INTO connection_probe (value) VALUES ('visible')")
        assert second.execute("SELECT value FROM connection_probe").fetchone()[0] == "visible"
    finally:
        first.close()
        second.close()


def test_temporary_database_paths_are_isolated(tmp_path: Path) -> None:
    first = connect(tmp_path / "first" / "panel.sqlite3")
    second = connect(tmp_path / "second" / "panel.sqlite3")
    try:
        run_migrations(first)
        run_migrations(second)
        with Repository(first).transaction():
            first.execute("CREATE TABLE isolated_probe (value INTEGER NOT NULL)")
        assert "isolated_probe" in table_names(first)
        assert "isolated_probe" not in table_names(second)
    finally:
        first.close()
        second.close()


def test_memory_database_configuration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(StorageConfigurationError, match="file-backed"):
        resolve_database_path(tmp_path, ":memory:")
    with pytest.raises(StorageConfigurationError, match="file-backed"):
        resolve_database_path(tmp_path, "file:temporary?mode=memory&cache=shared")


def test_unknown_migration_version_has_actionable_recovery_error(tmp_path: Path) -> None:
    database_path = configure_storage(Flask("sqlite-future"), tmp_path, "panel.sqlite3")
    connection = connect(database_path)
    try:
        connection.execute("INSERT INTO schema_migrations(version, name) VALUES (99, 'future_schema')")
        with pytest.raises(RuntimeError) as raised:
            run_migrations(connection)
    finally:
        connection.close()

    message = str(raised.value)
    assert "newer than this panel version" in message
    assert "Schema downgrade is unsupported" in message
    assert "docs/sqlite-storage-recovery.md" in message


def test_recovery_documentation_matches_config_and_reset_behavior() -> None:
    documentation = (Path(__file__).resolve().parents[2] / "docs/sqlite-storage-recovery.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "Schema downgrade is unsupported",
        "NO_PANEL_DATABASE_PATH",
        "NO_PANEL_DATABASE_BUSY_TIMEOUT_MS",
        "DATABASE_BUSY_TIMEOUT_MS",
        "panel.sqlite3-wal",
        "panel.sqlite3-shm",
        "servers.json",
        "ports.json",
        "standard error",
    ):
        assert required in documentation
