## Remediation (2026-08-05)

- Production: `e1549f0352daf927947103e1a0c8423c3697eddd`; validated review tip: `b2df0fc3f7c31b5add451728ecd5d4b9c9e12a07` (final metadata-only record is a child).
- Public limits are shared across contracts/backend/HTML/JavaScript; unknown jobs reject explicitly; version-1 peers tolerate missing/additive fields.
- Invalid persisted rows render bounded warnings, leases remain diagnostics-only, and invalid non-JSON results fail safely without stopping the queue.
- 145-test PR-specific gate and 159-test final cumulative gate: pass.

## Summary

- add strict Pydantic contracts for public-main configuration, Workshop, moderation, durable-job, and cluster submission boundaries;
- share public FPS, player, port, identifier, event, and list limits across backend validation, rendered HTML, JavaScript, and persistence;
- keep version-1 cluster submissions compatible with omitted fields and additive newer-peer fields while rejecting unknown job types;
- tolerate invalid historical job rows with safe warnings and prevent them from entering runtime dispatch;
- keep worker lease identifiers behind explicit administrator diagnostics and prevent non-JSON or credential-bearing values from reaching durable job/audit data.

## Public-source boundary

Public `upstream/main` remains behavioral authority. The contracts cover only operations present in public main. Hosted screenshots are visual references only, and no private provider schema, hosted control-plane behavior, or provider-only operation is added.

## Validation

- full local fork gate: pass;
- 145 cumulative tests, including bounds, mixed-version compatibility, explicit job coverage, unknown-operation rejection, malformed historical rows, secret-safe persistence, and diagnostics-only lease exposure: pass;
- strict fork-code lint/type/compile and production/review identity gates: pass.

This is a fork-review PR only. It does not authorize or open an upstream PR.
