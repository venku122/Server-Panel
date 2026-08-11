# UX source map

| Concern | Production owner | Primary files |
|---|---|---|
| Scope registry, canonical routes, redirects | PR1 | `app.py`, `templates/components/navigation.html` |
| Desktop shell, Find, dense Servers, Overview, Operations, settings hierarchy | PR2 | `templates/layouts/*`, `templates/global/servers.html`, `templates/server/{overview,operations,settings}.html`, `static/css/product.css`, `static/js/core/shell.js` |
| Mobile app bar, bottom navigation, drawers, safe areas, focus | PR3 | `templates/components/{navigation,shell_overlays}.html`, `static/css/{layout,product}.css`, `static/js/core/navigation.js` |
| SQLite foundation | PR4 | `server_panel/storage/*` |
| Activity/log experience | PR5 | `templates/components/timeline.html`, `templates/{global,server}/activity.html`, `static/css/components/timeline.css`, `static/js/components/timeline.js` |
| Jobs/deployments experience | PR6 | `templates/components/jobs.html`, `templates/{global,server}/jobs.html`, `static/css/pages.css`, `static/js/jobs.js` |
| Settings History | PR7 | `templates/server/configuration_history.html`, `static/js/config-history.js` |
| Workshop browser | PR8 | `templates/server/workshop.html`, `static/css/workshop.css`, `static/js/workshop-library.js` |
| Players and Moderation | PR9 | `templates/server/players.html`, `server_panel/moderation/templates/moderation/index.html`, `static/css/player-management.css`, `static/app.js` |
| Validation fit/contracts | PR10 | `server_panel/contracts/*`, `server_panel/limits.py`, `server_panel/storage/jobs.py`, `templates/server/settings.html` |
| Rich visual fixture and acceptance harness | Fork-only review | `scripts/fork/serve-review-fixture.py`, `scripts/fork/capture-ux-vercel.cjs`, `fork_tests/*`, `artifacts/ux-vercel/*` |

Fork-only fixtures contain eight heterogeneous servers, 62 activity records, queued/running/succeeded/failed/cancelled/interrupted jobs, configuration versions, Workshop edge cases, twelve players, and moderation installation state. None of that fixture data exists on a production branch.
