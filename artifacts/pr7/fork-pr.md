## Remediation (2026-08-05)

- Production: `25fb96e92bbd968c69abafb30b333a40011899f9`; review: `9d8562f7a204724c330515ab2f4e8d904bcb7a84`.
- First writes capture a unique baseline; staged replacements compensate on metadata failure; exact absent startup values and multi-file restores are recoverable.
- Concurrent version numbers, remote-error disclosure, no-op suppression, and restore lineage are verified by the 94-test PR gate.

## Summary

- capture the authoritative pre-change baseline before the first managed dedicated, startup, or NOBlackBox mutation without duplicating baselines;
- stage file writes beside their destination, replace atomically, persist version/audit metadata, and compensate every changed file when later persistence fails;
- restore exact startup absence semantics across BAT flags, MaxPlayers, and server metadata while preserving unrelated BAT arguments;
- make multi-file startup restore one compensating mutation and record every restore as a new lineage-linked version;
- serialize concurrent version assignment transactionally, skip no-op saves, and surface remote failure distinctly from an empty history.

## Public-source boundary

Public `upstream/main` remains behavioral authority. Only its dedicated config, startup settings, and NOBlackBox config are versioned. Hosted screenshots are visual references only and do not establish provider history, plans, backups, orchestration, or secrets.

## Validation

- full local fork gate: pass;
- 94 unit/integration tests, including baseline, concurrency, no-op, metadata failure, rollback failure, exact absent-value restore, multi-file compensation, lineage, and remote error cases: pass;
- production/review identity, stack ancestry, upstream-diff safety, diff hygiene, secret scan, strict campaign-owned checks, and legacy ratchets: pass.

This is a fork-review PR only. It does not authorize or open an upstream PR.
