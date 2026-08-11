# Final validation

Status: fork-side cumulative gate passed; physical iPhone Safari pending due locked Mac.

## Automated results

- Full fork suite: 159 passed.
- Production/review identity: pass; review-only changes remain under `.github/`, `artifacts/`, `fork_tests/`, `fork_tools/`, and `scripts/fork/`.
- Production stack ancestry PR1→PR10: pass.
- Route parity: 16 source-backed route contracts, 38 critical JavaScript IDs.
- Python: compile pass; changed campaign modules pass pinned Ruff format/lint and mypy ratchet.
- Templates/frontend: djLint pass; JavaScript syntax and capture-harness ESLint pass; TypeScript, ESLint, stylelint, and legacy checks meet or improve their baselines.
- Security: secret scan and upstream-diff safety pass.
- Browser: 90 redesigned captures, zero overflow, zero console/page errors, all focus and no-preconfirmation-mutation assertions pass.

Machine-readable results are in `full-gate.json` and `screenshots/after/validation-results.json`.

## Accessibility evidence

- Skip target and semantic links/buttons retained.
- Sidebar collapse, Find, row detail, menus, drawers, and modals are keyboard reachable.
- Escape and focus-return assertions pass for sheets and both mobile drawers.
- Mobile bottom navigation includes visible labels and 44px+ targets.
- Status includes text, not color alone.
- Safe-area, dynamic viewport, no-input-zoom, and reduced-motion rules are present.

## Remaining source constraints

No reliable health score, utilization metrics, deployment URL, universal build metadata, or always-current player counts are invented. Remote Workshop and unavailable cluster state remain explicitly bounded/degraded.

## Promotion order

After owner approval, promote production branches strictly PR1, PR2, PR3, PR4, PR5, PR6, PR7, PR8, PR9, PR10. No upstream PR was opened during this campaign.
