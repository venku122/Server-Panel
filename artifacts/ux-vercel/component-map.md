# Component map

| Primitive | Use |
|---|---|
| Sidebar + scope switcher | Desktop panel/server scope and prioritized navigation; resizable/collapsible preference only |
| Mobile app bar + bottom nav | Persistent scope context and one-handed primary navigation |
| More / server-selector Drawer | Secondary mobile navigation and scope change |
| Find palette | Cmd/Ctrl+K grouped route search; navigation only |
| Table | Servers, Activity, configuration history, and other comparable rows |
| Entity list | Players, recent Activity, recent Jobs, and descriptive resources |
| Description list | Static server/job/event metadata |
| Tabs | True URL-backed siblings only |
| Sheet | Desktop read-mostly associated detail |
| Drawer detail | Mobile form of Sheet |
| Menu | Secondary row actions and retry/cancel controls |
| Modal | Blocking restore, Workshop review, and destructive confirmation |
| Note | Persistent warnings and source limitations |
| Progress | Running jobs, moderation installation, and long operations |
| Empty state | No resources, no results, and recoverable absence |

Status uses text plus compact semantic color: green running/succeeded, blue active, amber stale/warning, red failed/destructive, neutral stopped/unknown. Unknown source values use an em dash.
