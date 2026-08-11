# Server Panel fork campaign promotion manifest

Updated: 2026-08-03

Public production authority: `Talon-One-Fighter-Squadron/Server-Panel:main`

Verified public base: `9e1abb50f2f75a3c0b0850ace70c94edba684d55`

Fork: <https://github.com/venku122/Server-Panel>

No upstream pull request has been opened. Every row below is a fork-review increment; upstream promotion remains explicitly owner-gated.

| Sequence | Title | Fork PR | Production branch | Review branch | Fork PR base | Production SHA | Review SHA | CI | Lint/type | Tests | Screenshots | Upstream diff | Dependencies | Known limitations | Promotion order |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|
| 1 | Global/server scope and reliable status | [#1](https://github.com/venku122/Server-Panel/pull/1) | `feature/01-server-scope` | `review/01-server-scope` | `fork-integration` | `c76fd2d4861490527018da450505bad92940cc2b` | `95335e528550b011b4a14c99ec23e45111349054` | Pass ([run 30786566505](https://github.com/venku122/Server-Panel/actions/runs/30786566505)) | Pass, legacy-ratcheted | 8 pass; 8 browser assertions | 9 hashed captures | Pass; five production paths only | Public `upstream/main` | Hosted/provider controls omitted; mobile drawer reserved for PR 3 | 1 |
| 2 | Jinja components and CSS system | [#2](https://github.com/venku122/Server-Panel/pull/2) | `feature/02-jinja-components` | `review/02-jinja-components` | `review/01-server-scope` | `eef81b6d5a14645721c00408d3e2d6ac02d277ff` | `1280f445b8c4880404be8b2a00c43e495514a08d` | Pass ([run 30832737681](https://github.com/venku122/Server-Panel/actions/runs/30832737681)) | Pass; new files strict, legacy ratcheted, TypeScript diagnostics reduced by 12 | 14 pass; 11 browser assertions | 8 hashed before/after captures at desktop and iPhone viewports | Pass; production tree matches feature ref and fork-only paths are excluded | PR 1 | Preserve the response rail until PR 3; hosted/provider-only behavior remains excluded | 2 |
| 3 | Mobile/iOS, confirmation, and diagnostics | Pending | `feature/03-mobile-confirm-diagnostics` | `review/03-mobile-confirm-diagnostics` | `review/02-jinja-components` | Pending | Pending | Pending | Pending | Pending | Required | Pending | PR 2 | No toast framework or provider UI | 3 |
| 4 | SQLite foundation | Pending | `feature/04-sqlite-foundation` | `review/04-sqlite-foundation` | `review/03-mobile-confirm-diagnostics` | Pending | Pending | Pending | Pending | Pending | Not applicable | Pending | PR 3 | Existing JSON/file state remains authoritative outside new repositories | 4 |
| 5 | Audit timeline | Pending | `feature/05-audit-timeline` | `review/05-audit-timeline` | `review/04-sqlite-foundation` | Pending | Pending | Pending | Pending | Pending | Not required | Pending | PR 4 | Legacy JSONL import must remain idempotent and redacted | 5 |
| 6 | Durable in-process jobs | Pending | `feature/06-job-system` | `review/06-job-system` | `review/05-audit-timeline` | Pending | Pending | Pending | Pending | Pending | Not required | Pending | PR 5 | Interrupted non-idempotent jobs are never auto-replayed | 6 |
| 7 | Configuration versions | Pending | `feature/07-config-versions` | `review/07-config-versions` | `review/06-job-system` | Pending | Pending | Pending | Pending | Pending | Not required | Pending | PR 6 | Version history is not full backup/restore | 7 |
| 8 | Workshop library and selection | Pending | `feature/08-workshop-library` | `review/08-workshop-library` | `review/07-config-versions` | Pending | Pending | Pending | Pending | Pending | Required | Pending | PR 7 | Public source supports local cache/indexing and existing inputs; arbitrary remote collection metadata/download is conditional and will not be invented | 8 |
| 9 | Moderation module extraction | Pending | `feature/09-moderation-module` | `review/09-moderation-module` | `review/08-workshop-library` | Pending | Pending | Pending | Pending | Pending | Not required | Pending | PR 8 | Behavior-preserving extraction only | 9 |
| 10 | Pydantic contracts | Pending | `feature/10-pydantic-contracts` | `review/10-pydantic-contracts` | `review/09-moderation-module` | Pending | Pending | Pending | Pending | Pending | Not applicable | Pending | PR 9 | No user-visible redesign or repository-wide dictionary rewrite | 10 |

## Intentional hosted-reference differences

- Hosted screenshots are visual references only. Public source remains the behavioral authority.
- General hosted Mods behavior, plan limits, provider-assigned ports, provider/orchestrator integration, and provider update controls are excluded because their source is unavailable.
- Public-main-only Ports, Cluster Setup, Gallery, NoBlackBox, Discord, and Windows/SteamCMD behavior remain available and are placed in explicit global or server scope.
- Server cards and timelines expose only facts backed by public source and campaign-owned persistence. No screenshot-only health or provider state is inferred.

## Exact PR 1 promotion preparation

These commands prepare and revalidate PR 1 only after T.J. explicitly approves opening it upstream:

```bash
git -C /home/tjt/src/llm/server-panel fetch upstream --prune
git -C /home/tjt/src/llm/server-panel-pr1-feature rebase upstream/main
git -C /home/tjt/src/llm/server-panel-pr1-feature diff --check upstream/main...HEAD
git -C /home/tjt/src/llm/server-panel-pr1-feature diff --name-status upstream/main...HEAD
```

Then mirror the rebased production state into `review/01-server-scope`, rerun the full fork gate and screenshots, verify the denylist, and open only the explicitly approved upstream PR. Do not run this promotion workflow during the autonomous fork campaign.
