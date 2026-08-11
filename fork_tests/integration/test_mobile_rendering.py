from __future__ import annotations


def test_global_shell_renders_drawer_dialog_and_closed_diagnostics(client) -> None:
    response = client.get("/servers")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'class="mobile-appbar"' in html
    assert 'id="panel-sidebar"' in html
    assert 'id="app-dialog"' in html


def test_server_shell_keeps_sticky_server_context_and_single_column_diagnostics(client) -> None:
    response = client.get("/servers/alpha-operations/settings")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'class="mobile-scope-button"' in html
    assert "<strong>Alpha Operations — Full Name</strong>" in html
    assert 'class="page show settings-page"' in html
    assert 'aria-label="Server settings views"' in html
    assert 'id="app-dialog-input"' in html
    assert "sensitive values are redacted" in html
    assert '<details class="card diagnostics-disclosure space-before-4" open' not in html
