# Audit storage and compatibility mirror

SQLite is the authoritative audit store. Global Activity, Server Activity, and the localhost administrator audit API
read bounded pages directly from `audit_events`, ordered by `(created_at DESC, id DESC)`. Opaque cursors retain that
stable boundary when timestamps are equal. Server, actor, outcome, and action filters are applied in SQL and preserved
in older/newer navigation links.

`panel_audit.jsonl` remains a best-effort compatibility mirror for older tooling. A JSONL append or reset failure never
rolls back the committed SQLite event. The panel writes an operational warning to its process logs, keeps processing
future audit events without recursively auditing the warning, and shows the degraded mirror state to administrators on
Activity pages and in the local audit API response.

Reset and downgrade handling for the authoritative database is documented in `docs/sqlite-storage-recovery.md`.
