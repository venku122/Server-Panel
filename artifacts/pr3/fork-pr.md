## Remediation (2026-08-05)

- Production: `ec581aa3374e1cace71cb6604e95847c4f7b3734`; review: `485a3d04466e3edd035acf1eeb799de0e53405ad`.
- Redaction now handles complete, oversized, incomplete, multiple, RSA, EC, OpenSSH, and generic private-key blocks before truncation.
- Foreground diagnostics retain a bounded 20-record history and background traffic cannot replace the latest operator record.
- Final-tree Chromium: 24 assertions and 10 captures with no errors/overflow. Physical iOS Safari remains pending and is not claimed.

## Summary

- add iPhone/compact-landscape drawer navigation, sticky server context, safe-area spacing, dynamic viewport units, and document-native scrolling;
- replace active native alert/confirm/prompt use with shared accessible confirmation, prompt, status, and field-error behavior;
- make request/response diagnostics closed by default, text-only, redacted before truncation, and bounded to the 20
  most recent foreground requests without polling overwrite;
- minimize startup-settings and server-delete responses so install paths, full server records, and sensitive fields are not returned.

## Public-source boundary

Public `upstream/main` is the behavioral authority. Hosted screenshots are visual references only. Provider plan
controls, assigned-port behavior, orchestration state, provider update controls, and other provider-only operations are
not implemented because their source is unavailable. Public-main Cluster, Discord, NoBlackBox, Gallery, Ports, and
SteamCMD behavior remains supported in explicit global/server scope.

## Validation

- full local fork gate: pass;
- 37 unit/integration tests;
- 24 browser assertions;
- 18 hashed before/after captures at 1200x800, 1600x1000, 390x844, and 844x390;
- no horizontal overflow, console errors, or page errors;
- new JS/CSS strict checks pass; legacy ESLint 6 to 2; TypeScript checkJs 236 to 232;
- production/review identity, upstream-diff safety, diff hygiene, secret scan, and formatter ratchets pass.

Physical iOS Safari was unavailable; the mobile evidence is Chromium emulation and is not represented as physical
Safari validation. Final PR 3 campaign approval remains pending that required real-device pass.

This is a fork-review PR only. It does not authorize or open an upstream PR.
