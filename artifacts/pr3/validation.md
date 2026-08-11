# PR 3 validation

Production base: `3c82bed3c2e8f0da77b7e1cf290527c9d3fc189e` (`feature/02-jinja-components`)

Production feature: `ec581aa3374e1cace71cb6604e95847c4f7b3734` (`feature/03-mobile-confirm-diagnostics`)

The complete local fork gate passed on 2026-08-03:

- production/review identity, stacked ancestry, public-upstream diff safety, diff hygiene, and secret scan: pass;
- 37 unit/integration tests: pass;
- 24 browser assertions and 18 hashed before/after captures: pass;
- 1200x800, 1600x1000, 390x844, and 844x390 viewport coverage with no horizontal overflow: pass;
- browser console errors and page errors: zero;
- new JavaScript and CSS files: strict lint/type checks pass;
- changed legacy JavaScript diagnostics: 6 to 2; no new diagnostics;
- TypeScript checkJs diagnostics: 236 to 232; no new diagnostics;
- Mypy, Ruff, stylelint, and legacy template ratchets: unchanged or improved;
- changed `app.py` lines: Ruff-format clean.

The browser gate confirms native dialogs are not invoked, incorrect typed confirmation sends no DELETE request,
diagnostics remain closed by default, all required secret vectors are redacted before truncation, and background
refreshes do not replace foreground history. Field errors receive focus, mobile inputs render at 16px, the compact
drawer returns focus on Escape, and document scrolling remains natural.

Physical iOS Safari was unavailable. Mobile evidence uses Chromium emulation and is not claimed as a physical-Safari
result. The automated gate passes, but final PR 3 campaign approval remains blocked on the required real-device pass.
