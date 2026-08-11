# Final remediated fork-stack validation

Public base: `9e1abb50f2f75a3c0b0850ace70c94edba684d55` (`upstream/main`)

Final production tip: `e1549f0352daf927947103e1a0c8423c3697eddd` (`feature/10-pydantic-contracts`)

## Automated gate

- All ten production branches and all ten review branches have correct stacked ancestry.
- Every review production subtree matches its production branch; fork-only tests, tooling, CI, and artifacts remain outside production.
- Full cumulative suite: 159 tests pass, including the reusable ten-boundary failure-injection matrix.
- Campaign-owned strict Python: Ruff lint/format and Mypy pass; all Python compilation passes.
- Legacy ratchets improve or remain unchanged: Ruff, Mypy, ESLint, TypeScript checkJs, djLint, and Stylelint pass.
- Changed JavaScript syntax, strict new-script checks, template architecture, DOM IDs, inline-style prohibition, legacy CSS ownership, secret scan, and upstream-diff denylist pass.
- All ten refreshed fork PR `full-gate` checks reached `SUCCESS`; corrected review workflows for PRs 6-10 validate their own base/feature increments.

The cumulative validator uses remediated PR1 as its base because PR1 predates the PR2 legacy-CSS ownership allowlist; PR1 independently passed its own public-main gate. Machine-readable output is in `final-stack-gate.json`.

## Browser evidence

- Final-tree PR3 suite: Chromium 149, 24 assertions, 10 captures across 1200x800, 1600x1000, 390x844, and 844x390; zero failed assertions, console errors, page errors, or horizontal overflow.
- Final-tree PR8 suite: Chromium 149, 16 assertions, two captures at 1200x800 and 390x844; zero failed assertions, console errors, page errors, or horizontal overflow.
- The real Flask fixture exercised diagnostics history/suppression, confirmations, focus, mobile layouts, Workshop browsing, conflict preview, incomplete-collection acknowledgement, and remote limitations. Worker/configuration/invalid-job/moderation failure behavior is covered by the real Flask integration suite.

## Security and remaining boundary

Private-key/token fixtures, nested secret redaction, URL credential stripping, cluster signature rejection, browser actor spoof rejection, lease hiding, public-path minimization, and secret scan pass. Physical iOS Safari remains pending and is not claimed. No upstream PR was opened, updated, or commented on.
