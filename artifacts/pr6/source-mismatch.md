# PR 6 durable-jobs source boundary

Public `upstream/main` provides the server update, Workshop mission sync, NOBlackBox install, and moderation install operations, but no hosted/provider worker source. PR 6 moves only those public-main operations into the fork's durable SQLite job model.

The hosted screenshots are visual references only. They do not establish provider orchestration, queue ownership, hosted health, plan state, or retry guarantees, so none are inferred. Public main's selected-server Workshop endpoint remains distinct from the explicit global/all-node endpoint: a selected sync cannot rewrite every local server configuration.

Public main does not provide transactional rollback or proven idempotence for any migrated mutation job. `server_update`, `noblackbox_install`, `moderation_install`, and `workshop_sync` therefore default to non-replay-safe. A normal retry is rejected; a forced linked retry requires exact typed acknowledgement and a reason, and records the actor, source job, reason, and last completed step.

No upstream PR was opened or updated.
