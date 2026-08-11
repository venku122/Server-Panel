# Server Panel fork campaign promotion manifest

Updated: 2026-08-05 (PRs 1-10 remediation)

Public production authority: `Talon-One-Fighter-Squadron/Server-Panel:main`

Verified public base: `9e1abb50f2f75a3c0b0850ace70c94edba684d55`

Fork: <https://github.com/venku122/Server-Panel>

No upstream pull request has been opened. Every row below is a fork-review increment; upstream promotion remains explicitly owner-gated.

| Sequence | Title | Fork PR | Production branch | Review branch | Fork PR base | Production SHA | Review SHA | CI | Lint/type | Tests | Screenshots | Upstream diff | Dependencies | Known limitations | Promotion order |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|
| 1 | Global/server scope and reliable status | [#1](https://github.com/venku122/Server-Panel/pull/1) | `feature/01-server-scope` | `review/01-server-scope` | `fork-integration` | `6c077801ab7228e5c67c4122902c7554360c1ccc` | `677ae12078691c4323726d30dc42ff9c3c1afd00` | Pass ([run 30981073745](https://github.com/venku122/Server-Panel/actions/runs/30981073745)) | Pass, legacy-ratcheted | Route/cluster adversarial suite pass | Existing PR1 desktop/mobile evidence | Pass | Public main | Cached remote state may be stale and is labeled; provider controls excluded | 1 |
| 2 | Jinja components and CSS system | [#2](https://github.com/venku122/Server-Panel/pull/2) | `feature/02-jinja-components` | `review/02-jinja-components` | `review/01-server-scope` | `3c82bed3c2e8f0da77b7e1cf290527c9d3fc189e` | `4546064258e5663126da29affa7ea2d4271a5308` | Pass ([run 30981074586](https://github.com/venku122/Server-Panel/actions/runs/30981074586)) | Pass; 16-route architecture gate | Cumulative route/template suite pass | Existing PR2 desktop/mobile evidence | Pass | PR1 | Transitional legacy CSS only; provider UI excluded | 2 |
| 3 | Mobile/iOS, confirmation, and diagnostics | [#3](https://github.com/venku122/Server-Panel/pull/3) | `feature/03-mobile-confirm-diagnostics` | `review/03-mobile-confirm-diagnostics` | `review/02-jinja-components` | `ec581aa3374e1cace71cb6604e95847c4f7b3734` | `485a3d04466e3edd035acf1eeb799de0e53405ad` | Pass ([run 30981074943](https://github.com/venku122/Server-Panel/actions/runs/30981074943)) | Pass | 37 cumulative at PR gate; final stack 159 | Final Chromium: 24 assertions, 10 captures | Pass | PR2 | Physical iOS Safari pending and not claimed | 3 |
| 4 | SQLite foundation | [#4](https://github.com/venku122/Server-Panel/pull/4) | `feature/04-sqlite-foundation` | `review/04-sqlite-foundation` | `review/03-mobile-confirm-diagnostics` | `1561ff8b7aab69e3c8af9ad08074acf32d9ab24c` | `dd2d722934ca8004f3f8634a91cf2673eec3ebbd` | Pass ([run 30981073953](https://github.com/venku122/Server-Panel/actions/runs/30981073953)) | Pass | 50 cumulative at PR gate | Not applicable | Pass | PR3 | Schema downgrade intentionally unsupported | 4 |
| 5 | Audit timeline | [#5](https://github.com/venku122/Server-Panel/pull/5) | `feature/05-audit-timeline` | `review/05-audit-timeline` | `review/04-sqlite-foundation` | `8b3c73a66e0a309ef40d2b4429076785e3543666` | `07a8c24d448155dad0ac7bcd4ccc5a5cf7ea1030` | Pass ([run 30981073573](https://github.com/venku122/Server-Panel/actions/runs/30981073573)) | Pass | 65 cumulative at PR gate | Not required | Pass | PR4 | JSONL remains best-effort compatibility mirror | 5 |
| 6 | Durable in-process jobs | [#6](https://github.com/venku122/Server-Panel/pull/6) | `feature/06-job-system` | `review/06-job-system` | `review/05-audit-timeline` | `bf515d50f830987d841cbcaaf3d4fe6160ab4613` | `1da7599a6fd9244f84d91731626279ef45105fd1` | Pass ([run 30981509186](https://github.com/venku122/Server-Panel/actions/runs/30981509186)) | Pass | 81 cumulative at PR gate | Integration-rendered | Pass | PR5 | Non-idempotent jobs require typed force retry | 6 |
| 7 | Configuration versions | [#7](https://github.com/venku122/Server-Panel/pull/7) | `feature/07-config-versions` | `review/07-config-versions` | `review/06-job-system` | `25fb96e92bbd968c69abafb30b333a40011899f9` | `9d8562f7a204724c330515ab2f4e8d904bcb7a84` | Pass ([run 30981509366](https://github.com/venku122/Server-Panel/actions/runs/30981509366)) | Pass | 94 cumulative at PR gate | Integration-rendered | Pass | PR6 | Version history is not a full machine backup | 7 |
| 8 | Workshop library and selection | [#8](https://github.com/venku122/Server-Panel/pull/8) | `feature/08-workshop-library` | `review/08-workshop-library` | `review/07-config-versions` | `3da9a320e1e4c9e984fc168ebe2bf377d8458446` | `3ec3acf255935c49805c22445f6564a286f20089` | Pass ([run 30981509377](https://github.com/venku122/Server-Panel/actions/runs/30981509377)) | Pass | 108 cumulative at PR gate | Final Chromium: 16 assertions, 2 captures | Pass | PR7 | No invented Steam/remote-provider collection behavior | 8 |
| 9 | Moderation module extraction | [#9](https://github.com/venku122/Server-Panel/pull/9) | `feature/09-moderation-module` | `review/09-moderation-module` | `review/08-workshop-library` | `f671b8262a68199fd9e2f15784ba3aaa799b9452` | `b68f3289a579ff81528f0a29db57716d891cb6cd` | Pass ([run 30981509780](https://github.com/venku122/Server-Panel/actions/runs/30981509780)) | Pass | 124 cumulative at PR gate | Integration-rendered | Pass | PR8 | Public local moderation behavior only | 9 |
| 10 | Pydantic contracts | [#10](https://github.com/venku122/Server-Panel/pull/10) | `feature/10-pydantic-contracts` | `review/10-pydantic-contracts` | `review/09-moderation-module` | `e1549f0352daf927947103e1a0c8423c3697eddd` | `b2df0fc3f7c31b5add451728ecd5d4b9c9e12a07` (validated tip; evidence record follows) | Pass ([run 30981509820](https://github.com/venku122/Server-Panel/actions/runs/30981509820)) | Pass | 159 cumulative final stack | Final PR3/PR8 evidence retained | Pass | PR9 | Explicit public job map; provider jobs excluded | 10 |

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

## Exact owner-gated upstream order

After PR1 is explicitly approved, rebased, revalidated, opened, and merged upstream, repeat the same fresh-`upstream/main` preparation for PR2. Continue strictly in numeric order through PR10; never open the next upstream PR before its predecessor lands and its production branch is rebased on the new public main:

1. `feature/01-server-scope`
2. `feature/02-jinja-components`
3. `feature/03-mobile-confirm-diagnostics`
4. `feature/04-sqlite-foundation`
5. `feature/05-audit-timeline`
6. `feature/06-job-system`
7. `feature/07-config-versions`
8. `feature/08-workshop-library`
9. `feature/09-moderation-module`
10. `feature/10-pydantic-contracts`

Each upstream PR requires a separate explicit owner approval immediately before opening it. The fork campaign and green CI confer no upstream authorization.
