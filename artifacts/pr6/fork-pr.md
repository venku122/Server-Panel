## Summary

- make the durable worker survive handler, renewal, lease-loss, and terminal-write failures while exposing liveness and last error to administrators;
- enforce lease ownership on renewal, checkpoints, handler events, and finalization, with cooperative cancellation and safe system diagnostics;
- define conservative per-job replay policy, reject unsafe normal retries, and require typed acknowledgement plus an audited reason for a forced linked retry;
- pass the configured lease duration through `JobContext`, validate JSON-compatible results, bound event data/count, and hide lease owners outside explicit admin diagnostics;
- preserve selected-server Workshop behavior separately from the explicit global/all-node operation;
- migrate the public-main moderation install operation into the same durable queue and document the multi-worker startup model.

## Public-source boundary

Public `upstream/main` is behavioral authority. Hosted screenshots are visual references only and do not supply provider queue, orchestration, health, plan, or retry behavior. All migrated mutation jobs remain non-replay-safe because public main provides no transactional rollback or proven idempotence.

## Validation

- full local fork gate: pass;
- 81 unit/integration tests, including every mandatory lease-loss, finish-failure, worker-survival, retry, cancellation, Workshop-scope, recovery, and duplicate-worker adversarial case: pass;
- production/review identity, stack ancestry, upstream-diff safety, diff hygiene, secret scan, strict campaign-owned Python/JS/template checks, and legacy quality ratchets: pass;
- worker liveness, explicit lease diagnostics, cancellation wording, forced-retry provenance, and audit linkage exercised through the real Flask fixture.

This is a fork-review PR only. It does not authorize or open an upstream PR.
