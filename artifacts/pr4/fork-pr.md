## Summary

- add the file-backed `data/panel.sqlite3` path with configuration/environment override support;
- initialize and verify persistent WAL once at startup, while keeping foreign keys and a configurable busy timeout on
  each Flask request/thread connection;
- add explicit commit/rollback transactions, application-context cleanup, an ordered idempotent migration runner, and
  the `schema_migrations` version table;
- add a small repository base for later audit, job, and configuration-history increments.
- document unsupported downgrade behavior, rollback copies, intentional metadata reset, and startup error locations.

## Scope boundary

Public `upstream/main` contains no database abstraction. Hosted/provider source is unavailable, so PR 4 follows the
directive's embedded-SQLite path. It adds no external service, audit UI/table, job table, configuration-version table,
provider integration, or migration of existing JSON/file-backed state.

## Validation

- full local fork gate: pass;
- 50 unit/integration tests covering fresh creation, restart/idempotence, failure rollback, multiple connections,
  request connection teardown, temporary isolation, in-memory rejection, configurable timeouts, future-schema errors,
  and recovery-document accuracy;
- startup-only WAL persistence and required per-connection pragmas verified;
- fixture schema contains only `schema_migrations`;
- new storage modules pass strict Ruff format/lint and Mypy;
- legacy quality ratchets, production/review identity, upstream-diff safety, diff hygiene, and secret scan pass.

No screenshots apply because this PR has no UI change. This is a fork-review PR only and does not authorize or open an
upstream PR.
