## Summary

- split global and server-scoped routes into shared Jinja layouts/components;
- establish CSS token/component/page ownership without removing public-main functionality;
- enforce a 16-route parity matrix, critical DOM IDs, no inline styles, and no unallowlisted legacy CSS additions.

## Remediation (2026-08-05)

- Production: `feature/02-jinja-components` at `3c82bed3c2e8f0da77b7e1cf290527c9d3fc189e`.
- Review: `review/02-jinja-components` at `4546064258e5663126da29affa7ea2d4271a5308`.
- Human/machine route parity, CSS ownership documentation, strict architecture checks, and refreshed desktop/iPhone evidence: pass.

## Public-source boundary

Public `upstream/main` remains behavioral authority. Hosted screenshots are design references only. No provider plans, assigned ports, hosted orchestration/update controls, or other source-unavailable behavior is included.

This is a fork-review PR only. It does not authorize or open an upstream PR.
