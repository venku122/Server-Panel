from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def panel_module(tmp_path_factory: pytest.TempPathFactory):
    source_root = Path(__file__).resolve().parents[1]
    runtime_root = tmp_path_factory.mktemp("panel-runtime")

    for source in source_root.glob("*.py"):
        shutil.copy2(source, runtime_root / source.name)
    shutil.copytree(source_root / "templates", runtime_root / "templates")
    shutil.copytree(source_root / "static", runtime_root / "static")
    shutil.copytree(source_root / "defaults", runtime_root / "defaults")
    shutil.copy2(source_root / "ports.json", runtime_root / "ports.json")
    shutil.copy2(source_root / "servers.json", runtime_root / "servers.json")

    os.environ["NO_PANEL_SECRET_KEY"] = "fork-test-only-secret"
    sys.path.insert(0, str(runtime_root))
    try:
        module = importlib.import_module("app")
        module.app.config.update(TESTING=True, SECRET_KEY="fork-test-only-secret")
        yield module
    finally:
        sys.path.remove(str(runtime_root))
        for name in ("app", "cluster", "config", "discord_bot", "remote_commander", "secret_store", "server_commands"):
            sys.modules.pop(name, None)


@pytest.fixture()
def managed_servers() -> list[dict[str, object]]:
    return [
        {
            "id": "alpha-operations",
            "name": "Alpha Operations — Full Name",
            "running": True,
            "location": "local",
            "node_id": "node-alpha",
        },
        {
            "id": "bravo-training",
            "name": "Bravo Training",
            "running": False,
            "location": "remote",
            "node_id": "node-bravo",
        },
    ]


@pytest.fixture()
def client(panel_module, managed_servers, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(panel_module, "_panel_servers_for_routes", lambda: managed_servers)
    monkeypatch.setattr(panel_module, "load_ports", lambda: [{"port": 7779, "name": "Alpha"}])
    test_client = panel_module.app.test_client()
    with test_client.session_transaction() as session:
        session.update(username="reviewadmin", role="admin", boot_id=panel_module.PANEL_BOOT_ID)
    return test_client
