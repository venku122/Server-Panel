# PR 3 browser evidence

PR 3 compares the committed PR 2 production base with the committed PR 3 production feature at 1200x800,
1600x1000, 390x844 iPhone portrait emulation, and 844x390 compact-landscape emulation. The fixture copies only
committed source into a temporary runtime, seeds synthetic local/remote server records, and disables LAN discovery.

The after capture verifies the off-canvas drawer and focus return, sticky server context, dynamic document scrolling,
16px mobile inputs, closed-by-default diagnostics, bounded secret redaction, shared confirmation dialogs, typed
destructive confirmation, field-level error focus, and horizontal-overflow absence. Destructive confirmation is
exercised only with deliberately incorrect typed input; no DELETE request is sent.

Physical iOS Safari was unavailable in this environment. The committed evidence is Chromium mobile emulation and is
not represented as physical-Safari validation.
