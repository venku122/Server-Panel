## Remediation (2026-08-05)

- Production: `8b3c73a66e0a309ef40d2b4429076785e3543666`; review: `07a8c24d448155dad0ac7bcd4ccc5a5cf7ea1030`.
- Added private-key-safe server redaction, stable cursor pagination/filter retention, authoritative SQLite with visible JSONL degradation, and correct recursion-path cycle handling.
- 65-test PR gate, including 550 equal-timestamp records and mirror failure: pass.

## Summary

- add the structured `audit_events` migration, repository, and centralized audit service;
- convert existing public action-log call sites while preserving a redacted, best-effort JSONL compatibility mirror;
- import pre-existing JSONL records idempotently without modifying the source file;
- add request correlation IDs, cursor-paginated global/server/API activity, server/actor/outcome/action filters,
  human-readable collapsed events, and redacted request/response disclosures;
- keep SQLite authoritative on JSONL failure, emit a process warning, and expose mirror degradation to administrators.

## Public-source boundary

Public `upstream/main` provides the legacy JSONL calls and localhost audit API. Hosted/provider source is unavailable,
so PR 5 records only public-main actions and campaign-owned structured fields. It does not infer provider plan,
orchestration, assigned-port, hosted-health, job, or configuration-version state.

## Validation

- full local fork gate: pass;
- 65 unit/integration tests covering shared client/server redaction vectors, 550-record stable pagination, filter
  preservation, repeated references and cycles, JSONL failure durability, all outcome states, restart persistence,
  idempotent legacy import, route rendering/scoping, correlation headers, and authorization;
- audit/migration Python modules, new timeline CSS, and changed templates pass strict checks;
- legacy quality ratchets, production/review identity, upstream-diff safety, diff hygiene, and secret scan pass.

This is a fork-review PR only. It does not authorize or open an upstream PR.
