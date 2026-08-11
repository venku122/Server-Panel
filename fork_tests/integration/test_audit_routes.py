from __future__ import annotations


def record_event(panel_module, **values) -> None:
    with panel_module.app.app_context():
        panel_module.AUDIT_SERVICE.record(**values)


def test_global_activity_renders_collapsed_redacted_timeline_and_filters(client, panel_module) -> None:
    record_event(
        panel_module,
        actor="route-admin",
        action="server.settings.updated",
        correlation_id="route-correlation-alpha",
        scope_type="server",
        server_id="alpha-operations",
        target_type="server",
        target_id="Alpha Operations — Full Name",
        outcome="success",
        summary="Changed Alpha FPS",
        request_payload={"password": "route-secret", "fps": 90},
        response_payload={"success": True},
    )
    record_event(
        panel_module,
        actor="route-admin",
        action="server.update.failed",
        correlation_id="route-correlation-bravo",
        scope_type="server",
        server_id="bravo-training",
        target_type="server",
        target_id="Bravo Training",
        outcome="failure",
        summary="Bravo update failed",
    )

    response = client.get(
        "/activity?server_id=alpha-operations&outcome=success&actor=route-admin&action=server.settings.updated"
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Changed Alpha FPS" in html
    assert "Bravo update failed" not in html
    assert "[REDACTED]" in html
    assert "route-secret" not in html
    assert 'class="diagnostics-disclosure audit-details"' in html
    assert 'class="diagnostics-disclosure audit-details" open' not in html
    assert 'name="action"' in html


def test_server_activity_is_route_scoped_and_exposes_correlation_header(client, panel_module) -> None:
    record_event(
        panel_module,
        actor="route-scope-admin",
        action="server.scope.checked",
        correlation_id="route-scope-alpha",
        scope_type="server",
        server_id="alpha-operations",
        target_type="server",
        target_id="Alpha Operations — Full Name",
        outcome="denied",
        summary="Alpha scoped event",
    )
    record_event(
        panel_module,
        actor="route-scope-admin",
        action="server.scope.checked",
        correlation_id="route-scope-bravo",
        scope_type="server",
        server_id="bravo-training",
        target_type="server",
        target_id="Bravo Training",
        outcome="success",
        summary="Bravo scoped event",
    )

    response = client.get(
        "/servers/alpha-operations/activity",
        headers={"X-Correlation-ID": "incoming-correlation-123"},
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "incoming-correlation-123"
    assert "Alpha scoped event" in html
    assert "Bravo scoped event" not in html
    assert 'scope: "server"' in html
    assert 'serverId: "alpha-operations"' in html


def test_activity_requires_admin(panel_module, managed_servers, monkeypatch) -> None:
    monkeypatch.setattr(panel_module, "_panel_servers_for_routes", lambda: managed_servers)
    test_client = panel_module.app.test_client()
    with test_client.session_transaction() as session:
        session.update(username="moderator", role="mod", boot_id=panel_module.PANEL_BOOT_ID)

    assert test_client.get("/activity").status_code == 403
    assert test_client.get("/servers/alpha-operations/activity").status_code == 403


def test_local_audit_api_pages_and_preserves_filters(client, panel_module, monkeypatch) -> None:
    monkeypatch.setattr(
        panel_module,
        "_get_user",
        lambda username: {"username": username, "role": "admin"},
    )
    for index in range(230):
        record_event(
            panel_module,
            actor="api-admin" if index % 2 else "other-admin",
            action="server.api.test",
            scope_type="server",
            server_id="alpha-operations",
            outcome="success",
            created_at="2026-08-04T12:00:00.000Z",
            mirror_legacy=False,
        )

    first = client.get(
        "/api/audit-logs?server_id=alpha-operations&actor=api-admin&outcome=success&action=server.api.test&limit=40"
    )
    payload = first.get_json()
    assert first.status_code == 200
    assert len(payload["logs"]) == 40
    assert payload["pagination"]["next_cursor"]
    assert payload["filters"] == {
        "server_id": "alpha-operations",
        "actor": "api-admin",
        "outcome": "success",
        "action": "server.api.test",
    }
    assert payload["mirror"]["authoritative_store"] == "sqlite"

    second = client.get(
        "/api/audit-logs?server_id=alpha-operations&actor=api-admin&outcome=success"
        f"&action=server.api.test&limit=40&cursor={payload['pagination']['next_cursor']}"
    )
    second_payload = second.get_json()
    assert second.status_code == 200
    assert second_payload["pagination"]["previous_cursor"]
    assert {event["id"] for event in payload["logs"]}.isdisjoint({event["id"] for event in second_payload["logs"]})


def test_activity_navigation_keeps_filter_query(client, panel_module) -> None:
    for index in range(55):
        record_event(
            panel_module,
            actor="filter-admin",
            action="server.filter.test",
            scope_type="server",
            server_id="alpha-operations",
            outcome="failure",
            created_at=f"2026-08-04T12:00:{index:02d}.000Z",
            mirror_legacy=False,
        )

    response = client.get(
        "/activity?server_id=alpha-operations&actor=filter-admin&outcome=failure&action=server.filter.test"
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Older activity" in html
    assert "server_id=alpha-operations" in html
    assert "actor=filter-admin" in html
    assert "outcome=failure" in html
    assert "action=server.filter.test" in html


def test_activity_exposes_jsonl_mirror_degradation_to_admin(client, panel_module, monkeypatch) -> None:
    monkeypatch.setattr(panel_module.AUDIT_SERVICE, "_mirror_failures", 2)
    monkeypatch.setattr(panel_module.AUDIT_SERVICE, "_mirror_last_error", "permission denied")
    monkeypatch.setattr(panel_module.AUDIT_SERVICE, "_mirror_last_failed_at", "2026-08-04T12:00:00.000Z")

    response = client.get("/activity")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "SQLite audit history is intact" in html
    assert "JSONL compatibility mirror is degraded" in html
    assert "2 mirror operation(s) failed" in html
