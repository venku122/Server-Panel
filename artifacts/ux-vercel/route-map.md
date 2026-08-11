# Route map

## Canonical panel routes

| Route | Scope / purpose | Access |
|---|---|---|
| `/servers` | Server resource list | Authenticated |
| `/activity` | All-server activity | Admin |
| `/jobs` | All-server durable jobs | Admin |
| `/deployment` | Server deployment | Admin |
| `/settings/ports` | Ports | Admin |
| `/settings/cluster` | Cluster | Admin |
| `/settings/users` | Panel users | Admin |
| `/settings/discord` | Discord integration | Admin |
| `/settings/about` | About | Authenticated |

`/settings` redirects to `/settings/ports`. Legacy `/ports`, `/cluster`, `/users`, `/integrations/discord`, and `/about` redirect with query parameters preserved.

## Canonical selected-server routes

| Route suffix under `/servers/<server_id>` | Purpose |
|---|---|
| `` | Overview |
| `/operations` | Lifecycle, mission, commands |
| `/players` | Connected players and direct actions |
| `/players/moderation` | Moderation sibling |
| `/workshop` | Workshop catalog and rotation |
| `/activity` | Server-scoped activity |
| `/jobs` | Server-scoped jobs |
| `/recordings` | Recorder |
| `/recordings/gallery` | Recording gallery sibling |
| `/settings` | General/gameplay settings |
| `/settings/history` | Configuration history sibling |

Legacy `/moderation`, `/noblackbox`, `/gallery`, and `/configuration-history` redirect to their canonical siblings with query parameters preserved. Scope switching is URL-derived and preserves compatible sections between servers and between global/server Activity and Jobs.
