from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_pr2_has_layered_jinja_shells_and_shared_components() -> None:
    expected = {
        "templates/base.html",
        "templates/layouts/global.html",
        "templates/layouts/server.html",
        "templates/components/navigation.html",
        "templates/components/breadcrumbs.html",
        "templates/components/server_card.html",
        "templates/components/page_header.html",
        "templates/components/status_message.html",
        "templates/global/servers.html",
        "templates/global/deployment.html",
        "templates/server/overview.html",
        "templates/server/operations.html",
    }
    missing = sorted(path for path in expected if not (ROOT / path).is_file())
    assert not missing, f"missing PR2 Jinja primitives: {missing}"


def test_route_templates_use_layouts_without_inline_styles() -> None:
    route_templates = {
        "templates/global/servers.html": "layouts/global.html",
        "templates/global/deployment.html": "layouts/global.html",
        "templates/global/ports.html": "layouts/global.html",
        "templates/global/users.html": "layouts/global.html",
        "templates/global/cluster.html": "layouts/global.html",
        "templates/global/discord.html": "layouts/global.html",
        "templates/global/about.html": "layouts/global.html",
        "templates/server/overview.html": "layouts/server.html",
        "templates/server/operations.html": "layouts/server.html",
        "templates/server/players.html": "layouts/server.html",
        "templates/server/moderation.html": "layouts/server.html",
        "templates/server/settings.html": "layouts/server.html",
        "templates/server/noblackbox.html": "layouts/server.html",
        "templates/server/gallery.html": "layouts/server.html",
    }
    for relative_path, layout in route_templates.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert re.search(rf'{{%\s*extends\s+["\']{re.escape(layout)}["\']\s*%}}', source)
        assert not re.search(r"\sstyle\s*=", source, re.IGNORECASE)


def test_routes_do_not_render_the_giant_legacy_templates() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert not re.search(r"render_template\(\s*['\"]index\.html['\"]", app_source)
    assert not re.search(r"render_template\(\s*['\"]servers\.html['\"]", app_source)


def test_pr2_has_css_tokens_layout_and_components() -> None:
    expected = {
        "static/css/tokens.css",
        "static/css/base.css",
        "static/css/layout.css",
    }
    missing = sorted(path for path in expected if not (ROOT / path).is_file())
    assert not missing, f"missing PR2 CSS primitives: {missing}"
    component_files = sorted((ROOT / "static/css/components").glob("*.css"))
    assert component_files, "PR2 requires reusable CSS component modules"


def test_route_parity_matrix_covers_every_source_backed_page_and_critical_id() -> None:
    matrix = json.loads((ROOT / "fork_tools/validation/pr02-route-parity.json").read_text(encoding="utf-8"))
    routes = matrix["routes"]
    assert len(routes) == 16
    assert {route["name"] for route in routes} == {
        "Global Servers",
        "Deployment",
        "Ports",
        "Cluster",
        "Panel Users",
        "Discord",
        "About",
        "Server Overview",
        "Operations",
        "Players",
        "Moderation",
        "Settings",
        "NoBlackBox",
        "Gallery",
        "Login",
        "First-run setup",
    }
    required = {
        "role",
        "template",
        "context",
        "js_ids",
        "empty_state",
        "local_behavior",
        "remote_behavior",
        "response_diagnostics",
    }
    app_script = (ROOT / "static/app.js").read_text(encoding="utf-8")
    for route in routes:
        assert required.issubset(route)
        template = ROOT / route["template"]
        source = template.read_text(encoding="utf-8")
        assert "style=" not in source.lower()
        for dom_id in route["js_ids"]:
            assert re.search(rf'\bid=["\']{re.escape(dom_id)}["\']', source)
            assert dom_id in app_script


def test_css_ownership_is_documented_and_enforced_by_the_fork_gate() -> None:
    ownership = (ROOT / "docs/css-architecture.md").read_text(encoding="utf-8")
    for required_text in (
        "static/style.css",
        "static/css/components/",
        "static/css/pages.css",
        "static/css/tokens.css",
        "inline `style=` attributes are prohibited",
    ):
        assert required_text in ownership

    validator = (ROOT / "scripts/fork/validate-pr.py").read_text(encoding="utf-8")
    assert "Converted template contains an inline style" in validator
    assert "Legacy static/style.css received unallowlisted additions" in validator
    assert "Critical DOM id" in validator
