## Summary

- add global/server URL scope and preserve public-main behavior;
- bound remote member aggregation with short timeouts and a cached unified view;
- preserve local entries when a member is unavailable and label stale/unavailable remote state;
- enforce server-side roles on administrator global pages and use named internal routes.

## Remediation (2026-08-05)

- Production: `feature/01-server-scope` at `6c077801ab7228e5c67c4122902c7554360c1ccc`.
- Review: `review/01-server-scope` at `677ae12078691c4323726d30dc42ff9c3c1afd00`.
- Added unavailable-member, local-fallback, stale-vs-empty, global authorization, and route-preserving navigation coverage.
- Local fork gate and production/review identity: pass.

## Public-source boundary

Public `upstream/main` at `9e1abb50f2f75a3c0b0850ace70c94edba684d55` is behavioral authority. Hosted screenshots are visual references only. Provider, plan, billing, orchestration, assigned-port, and other screenshot-only behavior is excluded.

This is a fork-review PR only. It does not authorize or open an upstream PR.
