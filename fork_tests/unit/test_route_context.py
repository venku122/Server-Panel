from __future__ import annotations


def test_route_maps_keep_global_and_server_sections_disjoint(panel_module) -> None:
    assert panel_module.SERVER_SECTION_PAGES == {
        "operations": {
            "template": "server/operations.html",
            "active_page": "control",
            "title": "Operations",
            "subtitle": "Lifecycle, mission, and server commands",
            "show_response": False,
        },
        "players": {
            "template": "server/players.html",
            "active_page": "bans",
            "title": "Players",
            "subtitle": "Manage kicked and banned players",
            "show_response": True,
        },
        "moderation": {
            "template": "server/moderation.html",
            "active_page": "moderation",
            "title": "Moderation",
            "subtitle": "Friendly-fire settings and notifications",
            "show_response": True,
        },
        "settings": {
            "template": "server/settings.html",
            "active_page": "server",
            "title": "Settings",
            "subtitle": "Gameplay and startup configuration",
            "show_response": False,
        },
        "noblackbox": {
            "template": "server/noblackbox.html",
            "active_page": "noblackbox",
            "title": "Recordings",
            "subtitle": "Recorder installation and configuration",
            "show_response": False,
        },
        "gallery": {
            "template": "server/gallery.html",
            "active_page": "gallery",
            "title": "Gallery",
            "subtitle": "Browse NoBlackBox recordings",
            "show_response": False,
        },
        "activity": {
            "template": "server/activity.html",
            "active_page": "activity",
            "title": "Activity",
            "subtitle": "Structured actions and outcomes for this server",
            "show_response": False,
            "admin_only": True,
        },
        "jobs": {
            "template": "server/jobs.html",
            "active_page": "jobs",
            "title": "Jobs",
            "subtitle": "Durable work and step history for this server",
            "show_response": False,
            "admin_only": True,
        },
    }
    assert panel_module.GLOBAL_PANEL_PAGES == {
        "deployment": {
            "template": "global/deployment.html",
            "active_page": "manage",
            "title": "Deployment",
            "subtitle": "Deploy and remove server instances",
            "show_response": True,
        },
        "activity": {
            "template": "global/activity.html",
            "active_page": "activity",
            "title": "Activity",
            "subtitle": "Structured panel and server actions",
            "show_response": False,
            "admin_only": True,
        },
        "jobs": {
            "template": "global/jobs.html",
            "active_page": "jobs",
            "title": "Jobs",
            "subtitle": "Durable background work across the panel",
            "show_response": False,
            "admin_only": True,
        },
        "ports": {
            "template": "global/ports.html",
            "active_page": "ports",
            "title": "Ports",
            "subtitle": "Manage ports and server names",
            "show_response": True,
        },
        "users": {
            "template": "global/users.html",
            "active_page": "users",
            "title": "Panel Users",
            "subtitle": "Accounts, failed logins, and IP blocks",
            "show_response": True,
        },
        "cluster": {
            "template": "global/cluster.html",
            "active_page": "cluster",
            "title": "Cluster Setup",
            "subtitle": "Create or join a LAN cluster",
            "show_response": True,
        },
        "integrations/discord": {
            "template": "global/discord.html",
            "active_page": "discord",
            "title": "Discord Bot",
            "subtitle": "Control the panel through Discord",
            "show_response": False,
        },
        "about": {
            "template": "global/about.html",
            "active_page": "about",
            "title": "About",
            "subtitle": "How the panel communicates with servers",
            "show_response": True,
        },
    }
    assert set(panel_module.SERVER_SECTION_PAGES) & set(panel_module.GLOBAL_PANEL_PAGES) == {
        "activity",
        "jobs",
    }
    for shared_section in ("activity", "jobs"):
        assert (
            panel_module.SERVER_SECTION_PAGES[shared_section]["template"]
            != panel_module.GLOBAL_PANEL_PAGES[shared_section]["template"]
        )


def test_unknown_server_section_returns_404(client) -> None:
    response = client.get("/servers/alpha-operations/not-a-section")
    assert response.status_code == 404
