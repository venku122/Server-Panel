## Summary

- extract the public moderation feature behind typed route, service, repository, installer, and background-poller boundaries;
- retain durable moderation install jobs and compatible browser response/poll shapes;
- derive browser ticket actors only from the authenticated session and accept cluster actors only after signed-request verification;
- return stable 400/401/403/404 semantics across invalid input, authentication, authorization, and missing resources;
- strip DLL URL credentials, query, and fragment before persisting job or audit metadata.

## Public-source boundary

Public `upstream/main` remains behavioral authority. This extraction covers its local moderation settings, tickets, DLL installer, notifications, and signed cluster transport only. No provider moderation service, hosted identity, or proprietary enforcement behavior is introduced.

## Validation

- full local fork gate: pass;
- 124 cumulative tests, including actor spoof, signed actor, invalid signature, role, missing resource, invalid URL, sanitized job/audit persistence, and response compatibility: pass;
- production/review identity and stack ancestry: pass.

This is a fork-review PR only. It does not authorize or open an upstream PR.
