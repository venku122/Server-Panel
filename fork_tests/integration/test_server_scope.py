from __future__ import annotations

import re

import pytest


def _context_value(html: str, key: str) -> str:
    match = re.search(rf"\b{re.escape(key)}:\s*([^,\n]+)", html)
    assert match, f"missing {key} from NO_PANEL_CONTEXT"
    return match.group(1).strip()


def test_root_redirects_to_global_server_list(client) -> None:
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/servers")


def test_global_server_list_uses_normal_links_and_full_names(client) -> None:
    response = client.get("/servers")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'href="/servers/alpha-operations"' in html
    assert 'href="/servers/bravo-training"' in html
    assert "Alpha Operations — Full Name" in html
    assert 'id="pill"' not in html


def test_each_server_route_derives_context_from_url(client) -> None:
    routes = {
        "/servers/alpha-operations": "dashboard",
        "/servers/alpha-operations/operations": "control",
        "/servers/alpha-operations/players": "bans",
        "/servers/alpha-operations/moderation": "moderation",
        "/servers/alpha-operations/settings": "server",
        "/servers/alpha-operations/noblackbox": "noblackbox",
        "/servers/alpha-operations/gallery": "gallery",
        "/servers/alpha-operations/activity": "activity",
    }
    for route, page in routes.items():
        response = client.get(route)
        html = response.get_data(as_text=True)
        assert response.status_code == 200, route
        assert _context_value(html, "scope") == '"server"'
        assert _context_value(html, "serverId") == '"alpha-operations"'
        assert _context_value(html, "activePage") == f'"{page}"'
        assert "Alpha Operations — Full Name" in html
        assert 'href="/servers"' in html


def test_global_routes_never_inherit_a_server_target(client) -> None:
    routes = {
        "/deployment": "manage",
        "/ports": "ports",
        "/users": "users",
        "/cluster": "cluster",
        "/integrations/discord": "discord",
        "/about": "about",
        "/activity": "activity",
    }
    for route, page in routes.items():
        response = client.get(route)
        html = response.get_data(as_text=True)
        assert response.status_code == 200, route
        assert _context_value(html, "scope") == '"global"'
        assert _context_value(html, "serverId") == "null"
        assert _context_value(html, "activePage") == f'"{page}"'


def test_invalid_server_is_explicit_and_recoverable(client) -> None:
    response = client.get("/servers/not-real")
    html = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "not-real" in html
    assert "was not found" in html
    assert 'href="/servers/alpha-operations"' in html


def test_deep_link_refresh_renders_the_same_target(client) -> None:
    first = client.get("/servers/bravo-training/operations")
    refreshed = client.get("/servers/bravo-training/operations")
    assert first.status_code == refreshed.status_code == 200
    assert _context_value(first.get_data(as_text=True), "serverId") == '"bravo-training"'
    assert _context_value(refreshed.get_data(as_text=True), "serverId") == '"bravo-training"'


def _authenticated_client(panel_module, role: str = "admin"):
    test_client = panel_module.app.test_client()
    with test_client.session_transaction() as session:
        session.update(username="route-reviewer", role=role, boot_id=panel_module.PANEL_BOOT_ID)
    return test_client


def _configure_unavailable_member(panel_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panel_module.cluster_state, "is_enabled", lambda: True)
    monkeypatch.setattr(panel_module.cluster_state, "is_coordinator", lambda: True)
    monkeypatch.setitem(
        panel_module.cluster_state.state,
        "members",
        [{"node_id": "node-bravo", "node_name": "Bravo node"}],
    )

    def unavailable(_member, _path, _payload, timeout):
        assert timeout == panel_module.SERVER_ROUTE_REMOTE_TIMEOUT_SEC
        return {"success": False, "error": "test timeout"}

    monkeypatch.setattr(panel_module, "_cluster_signed_post_to_member", unavailable)


def test_global_servers_preserves_local_and_cached_remote_on_member_failure(
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        panel_module,
        "load_servers",
        lambda: [{"id": "alpha", "name": "Alpha Local", "install_dir": "alpha"}],
    )
    monkeypatch.setattr(panel_module, "_is_server_running", lambda _path: True)
    monkeypatch.setattr(panel_module, "_SERVERS_VIEW_CACHE", {})
    monkeypatch.setattr(panel_module, "_SERVERS_VIEW_CACHE_UPDATED_AT", {})
    panel_module._cache_servers_view(
        [
            {
                "id": "bravo",
                "name": "Bravo Cached",
                "location": "remote",
                "node_id": "node-bravo",
                "running": False,
            }
        ]
    )
    _configure_unavailable_member(panel_module, monkeypatch)

    response = _authenticated_client(panel_module).get("/servers")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Alpha Local" in html
    assert "Bravo Cached" in html
    assert "Bravo node is unavailable" in html
    assert "Unavailable (cached)" in html


def test_local_server_page_renders_when_remote_member_is_unavailable(
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        panel_module,
        "load_servers",
        lambda: [{"id": "alpha", "name": "Alpha Local", "install_dir": "alpha"}],
    )
    monkeypatch.setattr(panel_module, "load_ports", lambda: [])
    monkeypatch.setattr(panel_module, "_is_server_running", lambda _path: False)
    monkeypatch.setattr(panel_module, "_SERVERS_VIEW_CACHE", {})
    monkeypatch.setattr(panel_module, "_SERVERS_VIEW_CACHE_UPDATED_AT", {})
    _configure_unavailable_member(panel_module, monkeypatch)

    response = _authenticated_client(panel_module).get("/servers/alpha")

    assert response.status_code == 200
    assert "Alpha Local" in response.get_data(as_text=True)


def test_remote_failure_is_not_rendered_as_an_empty_healthy_cluster(
    panel_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(panel_module, "load_servers", lambda: [])
    monkeypatch.setattr(panel_module, "_SERVERS_VIEW_CACHE", {})
    monkeypatch.setattr(panel_module, "_SERVERS_VIEW_CACHE_UPDATED_AT", {})
    _configure_unavailable_member(panel_module, monkeypatch)

    response = _authenticated_client(panel_module).get("/servers")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Bravo node is unavailable" in html
    assert "No servers configured" in html


@pytest.mark.parametrize(
    "path",
    ["/deployment", "/ports", "/users", "/cluster", "/integrations/discord"],
)
def test_non_admin_cannot_render_admin_global_pages(
    panel_module,
    managed_servers,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setattr(panel_module, "_panel_servers_for_routes", lambda: managed_servers)
    response = _authenticated_client(panel_module, role="mod").get(path)
    assert response.status_code == 403


def test_non_admin_can_render_non_admin_global_pages(
    panel_module,
    managed_servers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(panel_module, "_panel_servers_for_routes", lambda: managed_servers)
    response = _authenticated_client(panel_module, role="mod").get("/about")
    assert response.status_code == 200


def test_global_navigation_uses_named_route_outputs(client) -> None:
    html = client.get("/servers").get_data(as_text=True)
    for path in ("/deployment", "/ports", "/users", "/cluster", "/integrations/discord", "/about"):
        assert f'href="{path}"' in html
    assert 'href="/logout"' in html
