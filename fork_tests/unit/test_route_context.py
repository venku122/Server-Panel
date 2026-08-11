from __future__ import annotations


def test_route_maps_keep_global_and_server_sections_disjoint(panel_module) -> None:
    assert panel_module.SERVER_SECTION_PAGES == {
        "operations": "control",
        "players": "bans",
        "recordings": "noblackbox",
        "settings": "server",
    }
    assert panel_module.GLOBAL_PANEL_PAGES == {
        "deployment": "manage",
        "settings/ports": "ports",
        "settings/users": "users",
        "settings/cluster": "cluster",
        "settings/discord": "discord",
        "settings/about": "about",
    }
    assert set(panel_module.SERVER_SECTION_PAGES).isdisjoint(panel_module.GLOBAL_PANEL_PAGES)


def test_unknown_server_section_returns_404(client) -> None:
    response = client.get("/servers/alpha-operations/not-a-section")
    assert response.status_code == 404
