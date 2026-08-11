# Route parity matrix

Machine-readable source: `fork_tools/validation/pr02-route-parity.json`

The matrix records the source-backed route contract after the Jinja/CSS
decomposition. “Authenticated” means the page route accepts either panel role;
mutation APIs retain their own authorization. Global administrator pages are
also enforced server-side by their page routes.

| Page | Route | Required role | Template | Critical JavaScript IDs | Empty-state contract | Local behavior | Remote behavior | Response diagnostics |
|---|---|---|---|---|---|---|---|---|
| Global Servers | `/servers` | Authenticated | `global/servers.html` | None | No servers is distinct from remote-member failure | Local records always render | Live or age-bounded cached/unavailable | No |
| Deployment | `/deployment` | Admin | `global/deployment.html` | `page-manage`, `sm-create`, `server-pills` | Empty list retains create controls | Public-main local deployment | Source-backed coordinator node selection | Yes |
| Ports | `/ports` | Admin | `global/ports.html` | `page-ports`, `ports-table`, `save-ports` | Empty table retains actions | Editable local ports | Signed member ports with failure warning | Yes |
| Cluster | `/cluster` | Admin | `global/cluster.html` | `page-cluster`, `cluster-status`, `cluster-members` | No discovery/members is explicit | Public-main cluster controls | Signed member/discovery state | Yes |
| Panel Users | `/users` | Admin | `global/users.html` | `page-users`, `users-panel`, `users-list` | Each list is independently empty | Authoritative local user store | Existing signed synchronization | Yes |
| Discord | `/integrations/discord` | Admin | `global/discord.html` | `page-discord`, `discord-save`, `discord-status` | Not configured/stopped is explicit | Local source-backed bot | No provider orchestration | No |
| About | `/about` | Authenticated | `global/about.html` | `page-about`, `branding-status` | Defaults render without customization | Public-main behavior/branding | No hosted facts | Yes |
| Server Overview | `/servers/<server_id>` | Authenticated | `server/overview.html` | `page-dashboard`, `start-server-btn`, `mission1-name` | Unknown ID returns recoverable list | URL-selected local server | URL-selected signed/cached remote | Yes |
| Operations | `/servers/<server_id>/operations` | Authenticated | `server/operations.html` | `page-control`, `send-chat-message-form`, `set-next-mission-form` | Failures remain visible | URL-selected local command | Existing signed proxy | Yes |
| Players | `/servers/<server_id>/players` | Authenticated | `server/players.html` | `page-bans`, `kick-player-form`, `ban-player-form` | Empty player list is valid | Selected local server | Existing signed proxy | Yes |
| Moderation | `/servers/<server_id>/moderation` | Authenticated | `server/moderation.html` | `page-moderation`, `mod-load-btn`, `mod-save-btn` | Missing/unavailable config is explicit | Selected local config | Signed public-source path | Yes |
| Settings | `/servers/<server_id>/settings` | Authenticated | `server/settings.html` | `page-server`, `startup-load-btn`, `dedicated-save-btn` | Missing values render blank/default | Selected local server only | Signed errors remain visible | Yes |
| NoBlackBox | `/servers/<server_id>/noblackbox` | Authenticated | `server/noblackbox.html` | `page-noblackbox`, `nobb-save-btn`, `nobb-progress` | Not-installed/config-missing is explicit | Selected local installation | Existing signed member path | No |
| Gallery | `/servers/<server_id>/gallery` | Authenticated | `server/gallery.html` | `page-gallery`, `gallery-refresh`, `gallery-files` | Empty recordings list is valid | Selected local recordings | Existing signed fetch/cache | Yes |
| Login | `/login` | Public | `login.html` | None | No error renders login form | Local user store | No provider auth | No |
| First-run setup | `/first-run` | Authenticated | `first_run.html` | None | No error renders required controls | Local bootstrap account | No provider setup | No |

Every panel shell also receives its documented title, subtitle, page scope,
server context (where applicable), and shared ports/server context. The machine
gate verifies every listed template and critical ID, rejects inline styles in
converted templates, and rejects unallowlisted additions to legacy CSS.
