# PR 6 validation

Production base: `8b3c73a66e0a309ef40d2b4429076785e3543666` (`feature/05-audit-timeline`)

Production feature: `bf515d50f830987d841cbcaaf3d4fe6160ab4613` (`feature/06-job-system`)

The complete local fork gate passed on 2026-08-04:

- production/review identity, stacked ancestry, public-upstream diff safety, diff hygiene, and secret scan: pass;
- 81 unit/integration tests: pass;
- handler lease loss, heartbeat renewal failure, checkpoint/event/finalization ownership enforcement, and safe system diagnostics: pass;
- injected finalization failure leaves the worker alive and a second conflicting-free queued job subsequently succeeds: pass;
- invalid non-JSON handler results fail durably without stopping the next job: pass;
- expiry recovery marks work interrupted and never auto-replays it: pass;
- normal non-replay-safe retry rejection, replay-safe retry, typed forced acknowledgement, reason, actor, source job, and last completed step: pass;
- configured worker lease duration flows through `JobContext` checkpoints: pass;
- selected-server and global/all-node Workshop routes persist distinct scopes and parameters: pass;
- queued cancellation is immediate; running cancellation is exposed as `cancel_requested` with safe-checkpoint wording and no forced subprocess claim: pass;
- two worker instances execute one queued job exactly once through atomic SQLite claims and leases: pass;
- ordinary job JSON hides lease owners; explicit administrator lease diagnostics retain them: pass;
- messages, event data, event count, and handler results are bounded or validated: pass;
- global/server Jobs routes expose worker liveness and last error while preserving administrator authorization: pass;
- three campaign-owned storage modules pass strict Ruff lint/format and Mypy;
- the new Jobs script passes strict ESLint and JavaScript type checks; all six changed templates pass djLint;
- legacy Mypy diagnostics improve by three and Ruff diagnostics improve by one; ESLint, TypeScript, stylelint, and legacy-template ratchets are unchanged;
- 640 changed `app.py` lines are Ruff-format clean.

No screenshot evidence is required by the campaign for PR 6. The rendered Jobs surfaces and exact cancellation/retry disclosures are exercised through the real Flask fixture. Hosted screenshots remain visual references only.
