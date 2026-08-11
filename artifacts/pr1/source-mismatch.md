# Public source and hosted-reference mismatch

Verified on 2026-08-02 before PR 1 implementation.

- Public `upstream/main` and the public `v1.9` tag both resolved to `9e1abb50f2f75a3c0b0850ace70c94edba684d55`.
- The public `v1.9` release ZIP was materially different from that tagged Git commit. It included later files and behavior, including Playlists and Waitress, but still did not supply the hosted General Mods, plan, or provider implementation shown by the hosted references.
- The hosted site identified in the directive was serving PteroCA 0.6.5 during preflight, not a source-identifiable deployment of this Flask repository.
- The hosted screenshots therefore remain design references, not evidence that their provider-specific behavior exists in public source.

## PR 1 implementation boundary

This branch implements only behavior supported by public `main`: its Flask routes, server inventory, existing APIs, templates, and static client. It does not copy or infer unavailable provider code.

The screenshot references influenced hierarchy and visual language: a global server index, explicit server context, full names, breadcrumbs, scoped status, cards, and mobile-safe layout. They did not authorize invented health metrics, plan state, provider controls, General Mods behavior, or hidden API contracts.

## Intentional differences from the hosted screenshots

- Public `main` contains Ports, Cluster Setup, Gallery, NoBlackBox, and Discord surfaces that are not all visible in the hosted screenshots. PR 1 preserves them and assigns them to explicit global or server scope.
- PR 1 keeps the public monolithic Jinja/CSS structure. Template component extraction is reserved for PR 2.
- At iPhone width, PR 1 safely stacks the existing sidebar and content and removes horizontal clipping. It does not invent the hosted mobile drawer; mobile confirmation/diagnostics work is reserved for PR 3.
- Server cards show only public-source facts: name, running/stopped result, local/remote location, and node identifier. Screenshot-only health, plan, provider, and mod state are omitted.
- No provider-specific deployment, authentication, billing, hosting, or plan behavior is included because its source was not available.
