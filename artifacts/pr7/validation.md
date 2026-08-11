# PR 7 validation

Production base: `bf515d50f830987d841cbcaaf3d4fe6160ab4613` (`feature/06-job-system`)

Production feature: `25fb96e92bbd968c69abafb30b333a40011899f9` (`feature/07-config-versions`)

The complete local fork gate passed on 2026-08-04:

- production/review identity, stacked ancestry, public-upstream diff safety, diff hygiene, and secret scan: pass;
- 94 unit/integration tests: pass;
- first managed mutation captures exactly one baseline and then the changed version: pass;
- concurrent saves receive unique monotonically numbered versions through `BEGIN IMMEDIATE` plus the unique constraint: pass;
- no-op mutation creates neither a baseline nor a duplicate version: pass;
- staged atomic file replacement compensates existing and newly created files when metadata persistence fails: pass;
- injected rollback failure returns an explicit partial-failure state with the failed path/reason: pass;
- startup restore removes historically absent FPS, remote-command-port, metadata, and MaxPlayers settings while preserving unrelated BAT arguments: pass;
- multi-file BAT/dedicated-config/server-metadata restore rolls every file back on version-save failure: pass;
- restore creates a new version with `restored_from_version_id` lineage and never deletes history: pass;
- remote failure is rendered as an administrator-visible error rather than an empty list: pass;
- dedicated config and NOBlackBox settings/config use staged compensated writes with baseline metadata: pass;
- three campaign-owned storage modules pass strict Ruff lint/format and Mypy;
- new configuration-history JavaScript passes strict ESLint/type checks and both changed templates pass djLint;
- legacy Ruff, Mypy, ESLint, TypeScript, stylelint, and template ratchets are unchanged;
- 725 changed `app.py` lines are Ruff-format clean.

No screenshot evidence is required by the campaign for PR 7. Baseline/history rendering and remote failure disclosure are exercised through the real Flask fixture.
