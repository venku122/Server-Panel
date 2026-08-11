#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server


def copy_source(source_root: Path, runtime_root: Path, source_ref: str | None) -> None:
    if source_ref:
        archive_path = runtime_root / "source.tar"
        with archive_path.open("wb") as archive:
            subprocess.run(
                ["git", "archive", "--format=tar", source_ref],
                cwd=source_root,
                check=True,
                stdout=archive,
            )
        with tarfile.open(archive_path, mode="r:") as bundle:
            bundle.extractall(runtime_root)
        archive_path.unlink()
        return

    for source in source_root.glob("*.py"):
        shutil.copy2(source, runtime_root / source.name)
    for directory in ("templates", "static", "defaults", "server_panel"):
        source = source_root / directory
        if source.is_dir():
            shutil.copytree(source, runtime_root / directory)


def seed_runtime(runtime_root: Path, username: str, password: str) -> list[dict[str, object]]:
    alpha_install = runtime_root / "fixture-servers" / "alpha-operations"
    bravo_install = runtime_root / "fixture-servers" / "bravo-training"
    for install_dir in (alpha_install, bravo_install):
        install_dir.mkdir(parents=True)
        (install_dir / "DedicatedServerConfig.json").write_text("{}\n", encoding="utf-8")
        (install_dir / "RunServer.bat").write_text(
            "NuclearOptionServer.exe -batchmode -limitframerate 60 -ServerRemoteCommands 7779\n",
            encoding="utf-8",
        )

    servers: list[dict[str, object]] = [
        {
            "id": "alpha-operations",
            "name": "Alpha Operations — Full Name",
            "running": True,
            "location": "local",
            "node_id": "node-alpha",
            "install_dir": str(alpha_install),
        },
        {
            "id": "bravo-training",
            "name": "Bravo Training",
            "running": False,
            "location": "remote",
            "node_id": "node-bravo",
            "install_dir": str(bravo_install),
        },
    ]
    (runtime_root / "servers.json").write_text(
        json.dumps({"servers": servers}, indent=2) + "\n",
        encoding="utf-8",
    )
    (runtime_root / "ports.json").write_text(
        json.dumps({"ports": [{"port": 7779, "name": "Alpha"}]}, indent=2) + "\n",
        encoding="utf-8",
    )
    users = {
        "users": [
            {
                "username": username,
                "password_hash": generate_password_hash(password),
                "role": "admin",
                "created_at": "fork-fixture",
                "must_change_password": False,
            }
        ]
    }
    (runtime_root / "panel_users.json").write_text(json.dumps(users, indent=2) + "\n", encoding="utf-8")
    steamapps = runtime_root / "steamapps"
    cache = steamapps / "workshop" / "content" / "2168680"
    (cache / "111").mkdir(parents=True)
    (cache / "222").mkdir(parents=True)
    (cache / "333").mkdir(parents=True)
    (steamapps / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n  "0" {{ "path" "{runtime_root}" }}\n}}\n',
        encoding="utf-8",
    )
    (cache / "111" / "meta.json").write_text(
        json.dumps({"title": "Falcon Ridge", "author": "Aviator"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (cache / "111" / "FalconRidge.json").write_text('{"mission": true}\n', encoding="utf-8")
    (cache / "222" / "SilentValley.json").write_text('{"MissionObjects": []}\n', encoding="utf-8")
    (cache / "333" / "workshop.json").write_text(
        json.dumps({"title": "Weekend Operations", "children": ["111", "222", "999"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    existing = runtime_root / "missions" / "FalconRidge"
    existing.mkdir(parents=True)
    (existing / "FalconRidge.json").write_text('{"mission": "existing-version"}\n', encoding="utf-8")
    return servers


def main() -> int:
    source_value = os.environ.get("PANEL_SOURCE_ROOT", "").strip()
    if not source_value:
        raise RuntimeError("PANEL_SOURCE_ROOT must name a Server Panel worktree")
    source_root = Path(source_value).expanduser().resolve()
    if not (source_root / "app.py").is_file() or not (source_root / ".git").exists():
        raise RuntimeError(f"PANEL_SOURCE_ROOT is not a Server Panel worktree: {source_root}")

    source_ref = os.environ.get("PANEL_SOURCE_REF", "").strip() or None
    host = "127.0.0.1"
    port = int(os.environ.get("PANEL_FIXTURE_PORT", "5102"))
    username = os.environ.get("PANEL_REVIEW_USERNAME", "reviewadmin")
    password = os.environ.get("PANEL_REVIEW_PASSWORD", "fork-review-password")

    with tempfile.TemporaryDirectory(prefix="server-panel-browser-fixture-") as temp:
        runtime_root = Path(temp)
        copy_source(source_root, runtime_root, source_ref)
        servers = seed_runtime(runtime_root, username, password)
        os.environ["NO_PANEL_SECRET_KEY"] = "fork-browser-fixture-only-secret"
        os.environ["NO_PANEL_NODE_NAME"] = "ForkBrowserFixture"
        sys.path.insert(0, str(runtime_root))

        cluster_module = importlib.import_module("cluster")
        cluster_module.ClusterDiscovery.start = lambda _self: None
        panel_module = importlib.import_module("app")
        panel_module.app.config.update(TESTING=False, SECRET_KEY="fork-browser-fixture-only-secret")
        setattr(panel_module, "_panel_servers_for_routes", lambda: servers)
        setattr(panel_module, "load_ports", lambda: [{"port": 7779, "name": "Alpha"}])

        server = make_server(host, port, panel_module.app)
        source_description = f"{source_root}@{source_ref}" if source_ref else str(source_root)
        print(f"Fixture source: {source_description}", flush=True)
        print(f"Fixture runtime: {runtime_root}", flush=True)
        print(f"Fixture URL: http://{host}:{port}", flush=True)
        print(f"Fixture username: {username}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            sys.path.remove(str(runtime_root))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
