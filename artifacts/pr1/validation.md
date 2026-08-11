# PR 1 validation record

Production branch: `feature/01-server-scope`

Review branch: `review/01-server-scope`

Base: public `upstream/main` at `9e1abb50f2f75a3c0b0850ace70c94edba684d55`

## Automated and render coverage

- Root redirects to the global `/servers` index.
- Server cards are normal anchors and retain full server names.
- Overview, Operations, Players, Moderation, Settings, NoBlackBox, and Gallery derive their server target from the URL.
- Deployment, Ports, Panel Users, Cluster Setup, Discord, and About render with a null server target.
- Invalid server IDs return HTTP 404 with a clear recovery list.
- Repeated deep-link requests render the same server and section.
- The new server template passes full djLint formatting and linting.
- Touched legacy files add no Ruff, mypy, djLint, ESLint, TypeScript, or Stylelint diagnostics relative to public main.
- The production diff rejects fork-only paths, generated artifacts, and common secret signatures.

## Browser matrix

Chromium 149 exercised the real Flask app with two seeded managed servers.

- Back, forward, refresh, and the server switcher preserve route-derived scope.
- A failed server command creates a server-scoped page alert and no global Error pill.
- A global page produces no `server_id` query target.
- Desktop 1200x800 and 1440x900 captures have no horizontal overflow.
- iPhone portrait 390x844 global and server views have no horizontal overflow.
- The 390x844 baseline PNG reported a 517px layout viewport and horizontal overflow; the after capture reports the requested 390px layout viewport without overflow.
- Unexpected console errors: zero.
- Page errors: zero.
- The recorded 404 console entry is expected and belongs to the deliberate invalid-server negative test.

See `after/validation-results.json` for the machine-readable assertion and viewport record.

## Upstream legacy ratchet

Public main is not globally clean under the new fork tools. The gate compares normalized diagnostics against a fresh `git archive` of public main and fails on additions. PR 1 removes one Ruff, one djLint, and one ESLint diagnostic while holding the existing mypy, TypeScript, and Stylelint counts steady. The validator also verifies that Ruff would not reformat any changed `app.py` line.
