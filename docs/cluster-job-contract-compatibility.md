# Cluster job contract compatibility

Cluster peers exchange versioned JSON job requests. Version 1 requires `job_type` and `server_id`; `parameters`, `created_by`, `correlation_id`, and `contract_version` are optional. An omitted `contract_version` is treated as version 1 so older public-main peers continue to work.

Newer peers may send additive top-level fields. A version 1 receiver ignores fields it does not understand, while still validating every supported field. Existing response envelopes remain unchanged: successful submissions include `success` and `job`, and validation failures include `success`, `error`, and field-scoped `diagnostics`.

Supported job types are explicit:

- `server_update`
- `workshop_sync`
- `noblackbox_install`
- `moderation_install`

An unknown job type is rejected before persistence or dispatch. Additive compatibility is not permission to execute an unknown operation.

## Persisted records and diagnostics

Rows written by an older or newer build can contain a job type, status, scope, or JSON value that the current build cannot validate. The Jobs API and page render a bounded warning placeholder for that row instead of failing the whole list. Invalid rows are never added to the runtime handler map and cannot be dispatched.

Worker lease identifiers are operational diagnostics, not part of the stable browser contract. Normal job responses omit them. An administrator may request a single job with `?diagnostics=lease` when investigating worker ownership.
