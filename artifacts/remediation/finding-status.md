# Remediation finding status

The independent-review file named by the directive was not present in the supplied attachments or repository. The IDs below therefore map every numbered corrective subsection in the controlling remediation directive. Test names are representative; each PR validation artifact contains its complete gate.

| Finding ID | PR | Severity | Corrective commit(s) | Tests/evidence | Result | Final status | Residual limitation |
|---|---:|---|---|---|---|---|---|
| R-5.1 bounded remote aggregation | 1 | High | `e3269dc`, `d5c2287` | unavailable-member/server-scope route tests | Pass | Fixed | Cached remote entries can be stale and are labeled |
| R-5.2 global-page authorization | 1 | High | `e3269dc` | non-admin global route matrix | Pass | Fixed | None |
| R-5.3 named internal links | 1 | Low | `6c07780` | route-preserving switch/navigation tests | Pass | Fixed | None |
| R-6.1 route parity matrix | 2 | Medium | `0f1022c` (review) | 16-route machine/human matrix | Pass | Fixed | None |
| R-6.2 CSS ownership | 2 | Low | `a9e8030`, `0f1022c` | CSS architecture checks/document | Pass | Fixed | Legacy CSS remains transitional |
| R-6.3 template/CSS validation | 2 | Medium | `0f1022c` (review) | inline-style, legacy CSS, DOM-ID gates | Pass | Fixed | None |
| R-7.1 key redaction ordering | 3 | Critical | `9b926bc`, `a1bf847` | complete/long/incomplete/multiple PEM vectors | Pass | Fixed | None |
| R-7.2 deterministic diagnostics | 3 | High | `9b926bc`, `895834e` | foreground history vs background refresh browser test | Pass | Fixed | Twenty-record bounded history |
| R-7.3 physical iOS Safari | 3 | High | `485a3d0` (automated evidence only) | final Chromium portrait/landscape suite | Chromium pass | Pending external | Physical iPhone/Safari unavailable; not claimed |
| R-7.4 response compatibility | 3 | Medium | `b690a5a` | minimized delete-response caller tests and note | Pass | Fixed | None |
| R-8.1 one-time WAL initialization | 4 | Medium | `e38a8e9` | WAL persistence/restart tests | Pass | Fixed | None |
| R-8.2 configurable busy timeout | 4 | Medium | `e38a8e9` | default/override connection tests | Pass | Fixed | None |
| R-8.3 downgrade/recovery guidance | 4 | Low | `e38a8e9`, `dd2d722` | unknown-version/recovery contract tests | Pass | Fixed | Schema downgrade remains intentionally unsupported |
| R-9.1 server audit redaction | 5 | Critical | `0bef52a` | shared JS/Python key/token vectors | Pass | Fixed | None |
| R-9.2 audit pagination/filtering | 5 | High | `0bef52a`, `8b3c73a` | 550-record stable cursor/filter tests | Pass | Fixed | Page size remains bounded |
| R-9.3 JSONL mirror semantics | 5 | Medium | `0bef52a` | injected mirror failure | Pass | Fixed | JSONL remains best-effort compatibility output |
| R-9.4 shared-reference redaction | 5 | Medium | `0bef52a` | repeated references and real cycles | Pass | Fixed | None |
| R-10.1 worker exception boundaries | 6 | Critical | `c142738`, `05886ba` | finish failure then second-job success | Pass | Fixed | Cooperative rather than forced subprocess interruption |
| R-10.2 lease-loss semantics | 6 | Critical | `c142738` | renewal/checkpoint/event/finalization loss tests | Pass | Fixed | Running handler stops at safe checkpoint |
| R-10.3 replay policy | 6 | High | `c142738` | unsafe/safe/forced retry tests | Pass | Fixed | All migrated public jobs conservatively non-replay-safe by default |
| R-10.4 lease duration consistency | 6 | Medium | `c142738` | configured-duration checkpoint test | Pass | Fixed | None |
| R-10.5 selected/global Workshop scope | 6 | High | `32859dd` | local selected vs all-node route tests | Pass | Fixed | Remote work still requires signed member execution |
| R-10.6 cancellation semantics | 6 | Medium | `c142738` | queued/running cancellation response/UI tests | Pass | Fixed | No unsafe force-kill |
| R-10.7 result/event safety | 6 | High | `c142738`, `a88987e` | JSON result, bounds, lease disclosure tests | Pass | Fixed | Lease details diagnostics-only |
| R-10.8 worker startup model | 6 | Medium | `c142738` | duplicate worker/atomic claim test | Pass | Fixed | Multiple workers supported through SQLite leases |
| R-11.1 pre-write baselines | 7 | High | `25fb96e` | first/no-op write tests for managed resources | Pass | Fixed | Only campaign-managed resources versioned |
| R-11.2 filesystem compensation | 7 | Critical | `25fb96e` | replace, metadata, rollback failure injection | Pass | Fixed | Partial rollback failure is surfaced, not concealed |
| R-11.3 exact startup restore | 7 | High | `25fb96e` | present-to-absent BAT/config/metadata restore | Pass | Fixed | Unrelated BAT arguments preserved |
| R-11.4 multi-file restore | 7 | High | `25fb96e` | three-file version-save failure rollback | Pass | Fixed | None |
| R-11.5 remote history errors | 7 | Medium | `25fb96e` | remote-unavailable rendering test | Pass | Fixed | None |
| R-11.6 concurrent version numbering | 7 | High | `25fb96e` | six concurrent saves/unique constraint | Pass | Fixed | None |
| R-12.1 non-mutating Workshop preview | 8 | High | `82c4f14`, `af3358b` | full/conflict preview no-side-effect tests | Pass | Fixed | None |
| R-12.2 validate before copy | 8 | High | `82c4f14` | placement/count/conflict rejection tests | Pass | Fixed | None |
| R-12.3 staged compensated mutation | 8 | Critical | `82c4f14` | audit/copy/config failure compensation tests | Pass | Fixed | Atomicity is per-file plus compensation |
| R-12.4 explicit conflict policy | 8 | High | `82c4f14` | identical/stop/skip/replace/rename tests | Pass | Fixed | Replacement retains recoverable backup |
| R-12.5 mission signature | 8 | Medium | `82c4f14` | arbitrary JSON rejection test | Pass | Fixed | Minimal signature follows public mission examples |
| R-12.6 bounded cached index | 8 | Medium | `82c4f14` | scan bounds/cache reuse/refresh timestamp tests | Pass | Fixed | Cache requires explicit durable refresh for immediate rescan |
| R-12.7 incomplete collections | 8 | High | `82c4f14` | missing-child acknowledgement/audit tests | Pass | Fixed | No external Steam collection lookup invented |
| R-12.8 remote Workshop behavior | 8 | Medium | `f5d5c19`, `abeabf5` | remote page/API non-misleading tests | Pass | Fixed | Coordinator-local content is intentionally unavailable for remote mutation |
| R-13.1 moderation actor identity | 9 | Critical | `f671b82` | payload-spoof/session and signed-actor tests | Pass | Fixed | None |
| R-13.2 signature status semantics | 9 | High | `f671b82` | 400/401/403/404 route matrix | Pass | Fixed | None |
| R-13.3 DLL URL audit safety | 9 | Critical | `f671b82` | userinfo/query/fragment persistence tests | Pass | Fixed | Only sanitized host/path remains |
| R-13.4 PR description accuracy | 9 | Medium | `8f234af` (review record) | durable fork PR artifact | Pass | Fixed | None |
| R-14.1 shared limits | 10 | High | `495c605`, `e1549f0` | contract/HTML/JS/backend bound tests | Pass | Fixed | Public MaxPlayers maximum is 256 |
| R-14.2 tolerant persisted rows | 10 | High | `a89b574`, `495c605` | corrupt-row API/page warning tests | Pass | Fixed | Invalid rows are diagnostic placeholders and never dispatched |
| R-14.3 public/internal job models | 10 | Medium | `495c605` | normal vs explicit lease diagnostics tests | Pass | Fixed | None |
| R-14.4 explicit job-type map | 10 | High | `495c605` | known handler coverage/unknown rejection tests | Pass | Fixed | Provider-only jobs excluded |
| R-14.5 mixed-version clusters | 10 | Medium | `e0c7747`, `495c605` | missing/additive-field and error-shape tests | Pass | Fixed | Unknown operations remain rejected |
| R-14.6 safe non-JSON results | 10 | High | `a89b574`, `495c605` | invalid result then next-job success test | Pass | Fixed | Safe generic error intentionally omits object representation |

All source-remediation findings are fixed and green. `R-7.3` is the only pending external validation item.
