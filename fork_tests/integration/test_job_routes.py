from __future__ import annotations

from pathlib import Path

from server_panel.storage import connect, run_migrations
from server_panel.storage.jobs import JobService


class IdleWorker:
    def start(self) -> None:
        return None

    def status(self, *, include_diagnostics: bool = False):
        payload = {
            "alive": True,
            "last_error": None,
            "last_error_at": None,
            "multi_process_mode": "test atomic claims",
        }
        if include_diagnostics:
            payload["lease_owner"] = "private-test-owner"
        return payload


def isolated_service(tmp_path: Path, service_type=JobService) -> JobService:
    database_path = tmp_path / "route-jobs.sqlite3"
    connection = connect(database_path)
    run_migrations(connection)
    connection.close()
    return service_type(database_path)


def test_job_pages_api_worker_status_and_explicit_lease_diagnostics(
    client, panel_module, managed_servers, monkeypatch, tmp_path: Path
) -> None:
    service = isolated_service(tmp_path, panel_module._job_storage.JobService)
    monkeypatch.setattr(panel_module, "JOB_SERVICE", service)
    monkeypatch.setattr(panel_module, "JOB_WORKER", IdleWorker())
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "admin"})
    monkeypatch.setattr(
        panel_module,
        "_find_server_in_unified_view",
        lambda server_id: next(server for server in managed_servers if server["id"] == server_id),
    )

    queued = client.post(
        "/local/update-server",
        json={"server_id": "alpha-operations"},
        headers={"X-Correlation-ID": "route-job-correlation"},
    )
    payload = queued.get_json()
    job_id = payload["job"]["id"]
    claimed = service.claim_next("sensitive-owner", lease_seconds=30)
    assert claimed is not None
    service.cancel(job_id)

    global_page = client.get("/jobs")
    server_page = client.get("/servers/alpha-operations/jobs")
    listing = client.get("/api/jobs")
    ordinary = client.get(f"/api/jobs/{job_id}")
    diagnostic = client.get(f"/api/jobs/{job_id}?diagnostics=lease")
    assert queued.status_code == 202
    assert global_page.status_code == 200
    assert "data-worker-status" not in global_page.get_data(as_text=True)
    assert server_page.status_code == 200 and job_id in server_page.get_data(as_text=True)
    assert "Cancellation pending at safe checkpoint" in server_page.get_data(as_text=True)
    assert listing.get_json()["worker"]["alive"] is True
    assert "lease" not in ordinary.get_json()["job"]
    assert ordinary.get_json()["job"]["events"][0]["message"] == "Job queued."
    assert diagnostic.get_json()["job"]["lease"]["owner"] == "sensitive-owner"

    with panel_module.app.app_context():
        linked = [event for event in panel_module.AUDIT_SERVICE.list_events(limit=20) if event.get("job_id") == job_id]
    assert linked and linked[0]["action"] == "job.created"


def test_retry_route_rejects_normal_and_requires_exact_force_ack(
    client, panel_module, monkeypatch, tmp_path: Path
) -> None:
    service = isolated_service(tmp_path, panel_module._job_storage.JobService)
    monkeypatch.setattr(panel_module, "JOB_SERVICE", service)
    monkeypatch.setattr(panel_module, "JOB_WORKER", IdleWorker())
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "admin"})
    job = service.create(
        job_type="server_update",
        scope_type="server",
        server_id="alpha",
        parameters={"server_id": "alpha"},
        created_by="reviewadmin",
        correlation_id="unsafe-route-job",
        progress_total=3,
        replay_safe=False,
    )
    assert service.claim_next("worker").id == job.id
    service.checkpoint(job.id, "worker", message="Stopped selected server")
    service.finish(job.id, "worker", "failed", error_summary="SteamCMD failed")

    rejected = client.post(f"/api/jobs/{job.id}/retry", json={})
    rejected_payload = rejected.get_json()
    assert rejected.status_code == 409
    assert rejected_payload["force_required"] is True
    assert rejected_payload["last_completed_step"] == "Stopped selected server"
    assert rejected_payload["acknowledgement"] == f"FORCE RETRY {job.id}"

    forced = client.post(
        f"/api/jobs/{job.id}/retry",
        json={
            "force": True,
            "acknowledgement": f"FORCE RETRY {job.id}",
            "reason": "reviewed partial update",
        },
    )
    assert forced.status_code == 202
    assert forced.get_json()["job"]["parent_job_id"] == job.id


def test_selected_and_global_workshop_routes_enqueue_distinct_scopes(
    client, panel_module, monkeypatch, tmp_path: Path
) -> None:
    service = isolated_service(tmp_path, panel_module._job_storage.JobService)
    monkeypatch.setattr(panel_module, "JOB_SERVICE", service)
    monkeypatch.setattr(panel_module, "JOB_WORKER", IdleWorker())
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "admin"})
    monkeypatch.setattr(panel_module, "load_servers", lambda: [{"id": "alpha-operations"}])

    selected = client.post("/local/sync-workshop-missions", json={"server_id": "alpha-operations"})
    global_sync = client.post("/api/sync-workshop-missions", json={"server_id": "alpha-operations"})
    selected_job = selected.get_json()["job"]
    global_job = global_sync.get_json()["job"]
    assert selected.status_code == 202 and selected_job["scope_type"] == "server"
    assert selected_job["server_id"] == "alpha-operations"
    assert selected_job["parameters"] == {
        "all_servers": False,
        "local_only": True,
        "server_id": "alpha-operations",
    }
    assert global_sync.status_code == 202 and global_job["scope_type"] == "global"
    assert global_job["server_id"] is None
    assert global_job["parameters"]["all_servers"] is True
    assert global_job["parameters"]["local_only"] is False


def test_jobs_require_admin(panel_module, managed_servers, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        panel_module,
        "JOB_SERVICE",
        isolated_service(tmp_path, panel_module._job_storage.JobService),
    )
    monkeypatch.setattr(panel_module, "JOB_WORKER", IdleWorker())
    monkeypatch.setattr(panel_module, "_panel_servers_for_routes", lambda: managed_servers)
    monkeypatch.setattr(panel_module, "_get_user", lambda _username: {"role": "mod"})
    test_client = panel_module.app.test_client()
    with test_client.session_transaction() as session:
        session.update(username="moderator", role="mod", boot_id=panel_module.PANEL_BOOT_ID)

    assert test_client.get("/jobs").status_code == 403
    assert test_client.get("/servers/alpha-operations/jobs").status_code == 403
    assert test_client.get("/api/jobs/unknown").status_code == 403
