# PRs 1-10 remediation baseline

Captured: 2026-08-04T22:40:00-05:00

This is the preserved pre-remediation audit. `git fetch --all --prune` passed. The upstream default branch was `main`, and upstream, fork `main`, and `fork-integration` all resolved to public base `9e1abb50f2f75a3c0b0850ace70c94edba684d55`.

The named `SERVER-PANEL-FORK-PRS-1-10-INDEPENDENT-REVIEW.md` was absent from the attachment bundle and all campaign worktrees. The remediation directive contains the branch-specific corrective requirements and is the controlling finding source for this run.

| PR | Production SHA before remediation | Review SHA before remediation | Fork PR base |
|---:|---|---|---|
| 1 | `c76fd2d4861490527018da450505bad92940cc2b` | `95335e528550b011b4a14c99ec23e45111349054` | `fork-integration` |
| 2 | `eef81b6d5a14645721c00408d3e2d6ac02d277ff` | `57a7155d5930f9cada0ce30b242be2a4ac63114d` | `review/01-server-scope` |
| 3 | `c82a576c83ae5f43136618b7809fe2b9db97e291` | `68ddf3ba9bff19c043c1cb7f5110eacd428c4745` | `review/02-jinja-components` |
| 4 | `8ae6cb12f4d88e2b4b462a7971ca5a632373de89` | `401f85585903a65ba5df117e57c3242f2426a43e` | `review/03-mobile-confirm-diagnostics` |
| 5 | `70f13decab2bccdbb73a15344b8c9ca16048494a` | `9d9acd5bcbc33c8cdae6d1d7ee0111903eb54469` | `review/04-sqlite-foundation` |
| 6 | `51b83ea0f9887d96fd770743fb0ce35a5e7a250a` | `4941b7f6dfd3228a27139373c0539931f6ec5127` | `review/05-audit-timeline` |
| 7 | `06d8320e13d728986e4eb70874d2bde48651b77a` | `ef5f2b0dcc5787cc5b843bb00696820bb748655c` | `review/06-job-system` |
| 8 | `6eabb52bef0a0b04bd4f639a31fd8796d2d87716` | `265b2ad38e20929525053cb4fa17074c8a21e874` | `review/07-config-versions` |
| 9 | `5648ff2bc44ab99fd98c1ca938b98fbb35883300` | `8fd5ba19422d6109b50e28b0d060f5d5aa8ad73d` | `review/08-workshop-library` |
| 10 | `34e126ec3363335eb91149ab8282ca2770c0e011` | `707ecd892afc07d1ace56b733761a6dc14abeb8f` | `review/09-moderation-module` |

All production and review predecessor relationships passed ancestry checks. All ten fork PRs were open drafts with successful `full-gate` checks. The fresh pre-remediation cumulative gate passed 83 tests, strict fork-code lint/type/format, compile, legacy ratchets, secret scan, and review/production identity. No upstream PR existed.
