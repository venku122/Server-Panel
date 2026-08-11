from __future__ import annotations

import importlib
import sqlite3

import pytest


def test_app_startup_creates_the_migrated_campaign_schema_in_fixture_runtime(panel_module) -> None:
    database_path = panel_module.PANEL_DATABASE_PATH
    assert database_path.name == "panel.sqlite3"
    assert database_path.parent.name == "data"
    assert database_path.is_file()

    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        versions = connection.execute("SELECT version, name FROM schema_migrations").fetchall()
    finally:
        connection.close()

    assert tables == {"audit_events", "job_events", "jobs", "schema_migrations"}
    assert versions == [
        (1, "sqlite_storage_foundation"),
        (2, "audit_timeline"),
        (3, "durable_jobs"),
    ]
    verification = sqlite3.connect(database_path)
    try:
        assert verification.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        verification.close()


def test_flask_context_reuses_then_closes_its_connection(panel_module) -> None:
    storage = importlib.import_module("server_panel.storage")
    with panel_module.app.test_request_context("/servers"):
        connection = storage.get_db()
        assert storage.get_db() is connection
        assert connection.execute("SELECT 1").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
