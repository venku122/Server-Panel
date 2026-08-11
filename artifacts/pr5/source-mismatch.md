# PR 5 audit source boundary

Public `upstream/main` provides a small JSONL action log and localhost-only audit API, but no structured audit schema,
repository, service, Activity route, or hosted/provider implementation. PR 5 converts those public action-log call
sites through one structured service, preserves the JSONL mirror, and imports existing JSONL records idempotently.

The global/server timeline and filters expose only campaign-owned structured records. Request/response details are
bounded, recursively redacted, and collapsed by default. No provider orchestration, plan, assigned-port, hosted health,
or screenshot-only event is inferred. No job or configuration-version table is included.
