# PR 10 validation

Production base: `f671b8262a68199fd9e2f15784ba3aaa799b9452` (`feature/09-moderation-module`)

Production feature: `e1549f0352daf927947103e1a0c8423c3697eddd` (`feature/10-pydantic-contracts`)

The complete local fork gate passed on 2026-08-05:

- 145 cumulative unit/integration tests: pass;
- strict Pydantic configuration, Workshop, moderation, job submission, parameter, result, and response contracts: pass;
- the public maximum-player boundary is consistently 256 and port/FPS bounds are shared by backend contracts, rendered inputs, and JavaScript: pass;
- unknown job types are rejected before persistence and every supported public-main runtime handler has an explicit contract: pass;
- omitted version-1 fields and additive newer-peer fields remain compatible without accepting unknown operations: pass;
- invalid persisted rows render bounded warning placeholders without breaking the Jobs API/page or entering dispatch: pass;
- non-JSON objects and credential-bearing DLL URLs cannot leak into persisted job/audit payloads: pass;
- worker lease ownership is absent from normal browser responses and available only through explicit administrator diagnostics: pass;
- strict fork-code Ruff/Mypy, Python compile, JavaScript syntax/type, route/template architecture, secret, stack ancestry, and production/review identity gates: pass.

The mixed-version contract is recorded in `docs/cluster-job-contract-compatibility.md`. No new screenshot evidence is required for this boundary-focused PR.
