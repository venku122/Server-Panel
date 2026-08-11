# PR 3 public-source and hosted-reference boundary

Public `upstream/main` remains the behavioral authority. Hosted screenshots informed compact navigation, sticky
context, single-column content, and disclosure hierarchy only.

The hosted provider's plan controls, assigned-port behavior, orchestration state, provider update controls, and any
other provider-only operations are absent from public source and intentionally remain absent. PR 3 applies the shared
mobile, confirmation, status, diagnostics-redaction, and response-minimization behavior only to operations implemented
by public main.

The public application also differs structurally from the hosted reference: it contains public-main Cluster, Discord,
NoBlackBox, Gallery, Ports, and SteamCMD controls. PR 3 preserves those supported controls while placing them in the
fork's explicit global/server scopes; it does not infer screenshot-only health or provider state.
