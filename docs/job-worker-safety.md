# Durable job worker safety

The panel may run more than one worker thread or process. SQLite `BEGIN IMMEDIATE` claims, per-job server/global exclusion, and expiring ownership leases prevent two workers from claiming the same queued job. This supports Flask's debug reloader, repeated imports, and multi-process WSGI deployments without relying on a process-local singleton. Each process still starts at most one thread per `JobWorker` instance.

A heartbeat renewal failure immediately invalidates the handler context. Checkpoints, worker events, and terminal writes all verify the current lease owner. A worker that loses ownership records only a system diagnostic and discards the handler result; it cannot append ordinary handler events or mark the job successful. An iteration or finalization failure is logged and exposed on the Jobs page while the worker loop continues with backoff.

Cancellation is cooperative. A queued job cancels immediately. A running job is displayed as `cancel_requested` and stops at its next checkpoint. The panel does not claim that a long-running subprocess stopped immediately and does not force-kill it outside a type-specific safe boundary.

## Replay policy

Public main does not provide a transaction or rollback boundary for the migrated mutation jobs, so their default policy is conservative:

| Job type | Normal retry | Reason |
| --- | --- | --- |
| `server_update` | No | Process stop, SteamCMD update, and restart can have partial side effects. |
| `noblackbox_install` | No | Download, extraction, and configuration writes are not transactional. |
| `moderation_install` | No | Download and plugin replacement are not transactional. |
| `workshop_sync` | No | Workshop and mission-directory filesystem writes are not staged atomically in this revision. |

The Jobs API rejects a normal retry for these types. An administrator may force a linked retry only by submitting the exact `FORCE RETRY <job-id>` acknowledgement and a reason. The new job records the actor, reason, source job, and last completed step in its parameters; the source job records the same provenance in its event history. No job is silently cloned.

Handler results must already be finite JSON-compatible data before they are redacted and persisted. Event messages are capped at 2,000 characters, event payloads at a compact 16 KB diagnostic summary, and each job retains at most 1,000 events.

## Workshop scope

`POST /local/sync-workshop-missions` affects only the selected local server's `MissionDirectory` when a `server_id` is supplied. With no selection it imports the local cache without rewriting server configurations. `POST /api/sync-workshop-missions` is the explicit all-nodes operation and updates every local server once per participating node.

Lease-owner identifiers are omitted from normal job list/detail responses. An administrator can request a single job's lease details explicitly with `?diagnostics=lease`.
