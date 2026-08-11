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
from datetime import datetime, timedelta, timezone
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
    server_specs = [
        ("alpha-operations", "Alpha Operations", True, "local", "node-alpha"),
        ("bravo-training", "Bravo Training", False, "local", "node-alpha"),
        ("charlie-ranked", "Charlie Ranked East", True, "remote", "node-charlie"),
        ("delta-unavailable", "Delta Remote — Connection Unavailable", False, "remote", "node-delta"),
        (
            "echo-community",
            "Echo Community Server With A Deliberately Long Operator-Facing Name",
            True,
            "local",
            "node-alpha",
        ),
        ("foxtrot-empty", "Foxtrot Empty", True, "local", "node-alpha"),
        ("golf-event", "Golf Weekend Event", False, "local", "node-alpha"),
        ("hotel-testing", "Hotel Integration Testing", True, "remote", "node-hotel"),
    ]
    install_dirs = {
        server_id: runtime_root / "fixture-servers" / server_id
        for server_id, _name, _running, _location, _node_id in server_specs
    }
    for install_dir in install_dirs.values():
        install_dir.mkdir(parents=True)
        (install_dir / "DedicatedServerConfig.json").write_text(
            json.dumps({"ServerName": install_dir.name, "MaxPlayers": 16}, indent=2) + "\n",
            encoding="utf-8",
        )
        (install_dir / "RunServer.bat").write_text(
            "NuclearOptionServer.exe -batchmode -limitframerate 60 -ServerRemoteCommands 7779\n",
            encoding="utf-8",
        )

    servers: list[dict[str, object]] = []
    for index, (server_id, name, running, location, node_id) in enumerate(server_specs):
        servers.append(
            {
                "id": server_id,
                "name": name,
                "running": running,
                "location": location,
                "node_id": node_id,
                "node_name": node_id.replace("node-", "").title(),
                "install_dir": str(install_dirs[server_id]),
                "remote_commands_port": 7779 + index,
                "game_port": 27015 + index,
                "query_port": 27025 + index,
                "mission1_group": "User",
                "mission1_name": "FalconRidge" if server_id == "alpha-operations" else "",
                "player_count": 12 if server_id == "alpha-operations" else 0,
                "stale": server_id == "delta-unavailable",
                "status_error": "Remote member did not answer the last health check"
                if server_id == "delta-unavailable"
                else None,
            }
        )
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
    (cache / "444").mkdir(parents=True)
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
    (cache / "444" / "meta.json").write_text(
        json.dumps(
            {
                "title": "Operation Long Horizon — Combined Arms Campaign With Extended Briefing",
                "author": "Fixture Squadron Mission Team",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (cache / "444" / "LongHorizon.json").write_text('{"objectives": []}\n', encoding="utf-8")
    existing = runtime_root / "missions" / "FalconRidge"
    existing.mkdir(parents=True)
    (existing / "FalconRidge.json").write_text('{"mission": "existing-version"}\n', encoding="utf-8")

    moderation_root = install_dirs["alpha-operations"] / "BepInEx"
    plugin = moderation_root / "plugins" / "NO_KillFeedConsole" / "NO_KillFeedConsole.dll"
    config = moderation_root / "config" / "com.nicho.no.killfeedconsole.cfg"
    state = moderation_root / "config" / "NO_KillFeedConsoleAdmin" / "moderation-state.json"
    plugin.parent.mkdir(parents=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    state.parent.mkdir(parents=True)
    plugin.write_bytes(b"fork-review-placeholder")
    config.write_text(
        "[Integration]\nEnableAutoKick = true\nAircraftTolerance = 1\nVehicleTolerance = 2\nShipTolerance = 1\n",
        encoding="utf-8",
    )
    state.write_text(json.dumps({"Tickets": [], "ClosedTickets": []}, indent=2) + "\n", encoding="utf-8")
    return servers


def seed_operational_data(panel_module) -> None:
    """Populate high-density, non-production review states after services initialize."""
    with panel_module.app.app_context():
        config_ids: list[str] = []
        for number, max_players in enumerate((12, 20, 24), start=1):
            result = panel_module._record_config_version(
                "dedicated_server_config",
                "alpha-operations",
                {"ServerName": "Alpha Operations", "MaxPlayers": max_players, "Password": "fixture-secret"},
                actor="config-admin",
                correlation_id=f"fixture-config-{number}",
                change_summary=f"Set maximum players to {max_players}",
                restart_required=number > 1,
                force=True,
            )
            config_ids.append(str(result["version"]["id"]))

        jobs = panel_module.JOB_SERVICE

        def create_job(job_type, *, replay_safe=True, correlation_id, total=4):
            return jobs.create(
                job_type=job_type,
                scope_type="server",
                server_id="alpha-operations",
                parameters={"server_id": "alpha-operations"},
                created_by="release-admin",
                correlation_id=correlation_id,
                progress_total=total,
                replay_safe=replay_safe,
            )

        succeeded = create_job("server_update", correlation_id="fixture-job-succeeded")
        jobs.claim_next("fixture-worker")
        jobs.checkpoint(succeeded.id, "fixture-worker", message="Downloaded server update", current=3, total=4)
        jobs.finish(succeeded.id, "fixture-worker", "succeeded", result={"version": "1.9.4"})

        failed = create_job("moderation_install", replay_safe=False, correlation_id="fixture-job-failed", total=3)
        jobs.claim_next("fixture-worker")
        jobs.checkpoint(failed.id, "fixture-worker", message="Stopped selected server", current=1, total=3)
        jobs.finish(failed.id, "fixture-worker", "failed", error_summary="Plugin download checksum did not match")

        interrupted = create_job("noblackbox_install", correlation_id="fixture-job-interrupted", total=3)
        jobs.claim_next("fixture-worker")
        jobs.checkpoint(interrupted.id, "fixture-worker", message="Installed BepInEx prerequisites", current=2, total=3)
        jobs.finish(
            interrupted.id, "fixture-worker", "interrupted", error_summary="Worker lease expired during restart"
        )

        cancelled = create_job("workshop_sync", correlation_id="fixture-job-cancelled", total=2)
        jobs.cancel(cancelled.id)

        retry = jobs.retry(
            failed.id,
            "incident-admin",
            "fixture-job-forced-retry",
            force=True,
            acknowledgement=f"FORCE RETRY {failed.id}",
            reason="Checksum source verified manually",
        )
        if retry is not None:
            jobs.claim_next("fixture-worker")
            jobs.checkpoint(
                retry.id, "fixture-worker", message="Downloading verified plugin artifact", current=2, total=3
            )

        queued = create_job("workshop_sync", correlation_id="fixture-job-queued", total=2)

        actors = ("release-admin", "config-admin", "moderator-jules", "cluster-member")
        outcomes = ("success", "success", "success", "failure", "denied")
        actions = (
            "server.lifecycle.started",
            "server.settings.updated",
            "moderation.ticket.denied",
            "workshop.rotation.updated",
            "job.checkpoint.recorded",
        )
        now = datetime.now(timezone.utc)
        for index in range(62):
            server_id = None if index % 7 == 0 else ("alpha-operations" if index % 3 else "charlie-ranked")
            summary = f"Fixture event {index + 1}: {actions[index % len(actions)].replace('.', ' ')}"
            if index == 11:
                summary += " after validating every remote member and preserving the previous server configuration"
            panel_module.AUDIT_SERVICE.record(
                actor=actors[index % len(actors)],
                action=actions[index % len(actions)],
                correlation_id=f"fixture-correlation-{index:03d}",
                scope_type="global" if server_id is None else "server",
                server_id=server_id,
                target_type="config_version" if index % 13 == 0 else "server",
                target_id=config_ids[index % len(config_ids)] if index % 13 == 0 else (server_id or "panel"),
                outcome=outcomes[index % len(outcomes)],
                summary=summary,
                request_payload={"password": "must-redact", "index": index},
                response_payload={"success": outcomes[index % len(outcomes)] == "success"},
                job_id=(retry.id if retry is not None else queued.id) if index % 9 == 0 else None,
                created_at=(now - timedelta(minutes=index * 7))
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"),
                mirror_legacy=False,
            )


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
        setattr(
            panel_module.server_commands,
            "get_player_list",
            lambda _commander: (
                "Success",
                {
                    "Players": [
                        {"Name": name, "SteamId": f"7656119800000{index:04d}"}
                        for index, name in enumerate(
                            (
                                "Aviator",
                                "Long Callsign That Exercises Dense Entity Truncation",
                                "Viper",
                                "Night Owl",
                                "Rook",
                                "GroundControl",
                                "Maverick",
                                "Iceman",
                                "Phoenix",
                                "Cyclone",
                                "Kodiak",
                                "Sundown",
                            )
                        )
                    ]
                },
            ),
        )
        seed_operational_data(panel_module)

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
