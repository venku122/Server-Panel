# PR 2 browser evidence

The capture matrix is defined in `fork_tools/validation/pr02-browser.json`. The fixture launcher copies only source
code/assets into a temporary runtime, seeds two synthetic servers and one synthetic admin, disables LAN discovery,
and never runs the source worktree's `app.py` entry point or background schedulers.

Install the pinned browser tooling once in the review worktree:

```bash
npm ci --prefix fork_tools
fork_tools/node_modules/.bin/playwright install chromium
```

Start the committed PR 1 baseline fixture in one terminal:

```bash
PANEL_SOURCE_ROOT=/home/tjt/src/llm/server-panel-feature \
PANEL_SOURCE_REF=feature/01-server-scope \
PANEL_FIXTURE_PORT=5102 \
PANEL_REVIEW_USERNAME=reviewadmin \
PANEL_REVIEW_PASSWORD=fork-review-password \
/home/tjt/src/llm/server-panel-venv/bin/python scripts/fork/serve-review-fixture.py
```

Capture it from the PR 2 review worktree in a second terminal:

```bash
PANEL_BASE_URL=http://127.0.0.1:5102 \
PANEL_CAPTURE_PHASE=before \
PANEL_REVIEW_USERNAME=reviewadmin \
PANEL_REVIEW_PASSWORD=fork-review-password \
node scripts/fork/capture-pr2.cjs
```

Stop the fixture, restart it with `PANEL_SOURCE_REF=feature/02-jinja-components`, and repeat the capture command with
`PANEL_CAPTURE_PHASE=after`. Then build the hashed manifest:

```bash
/home/tjt/src/llm/server-panel-venv/bin/python scripts/fork/build-evidence-manifest.py \
  --config fork_tools/validation/pr02-browser.json
```

The full gate verifies the recorded base and feature commits, capture hashes, required desktop/iPhone viewports,
named browser assertions, overflow results, and unexpected console/page errors.
