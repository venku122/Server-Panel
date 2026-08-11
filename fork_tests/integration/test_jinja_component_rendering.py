from __future__ import annotations


def test_componentized_global_shell_renders_server_cards(client) -> None:
    response = client.get("/servers")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Alpha Operations — Full Name" in html
    assert 'href="/servers/alpha-operations"' in html
    assert "/static/css/" in html
    assert 'style="' not in html


def test_componentized_server_shell_preserves_route_context(client) -> None:
    response = client.get("/servers/alpha-operations/operations")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Alpha Operations — Full Name" in html
    assert 'scope: "server"' in html
    assert 'serverId: "alpha-operations"' in html
    assert "/static/css/" in html
