# SQLite storage upgrades and recovery

The panel initializes its campaign-owned SQLite database during process startup, before it accepts requests. Startup
enables persistent write-ahead logging (WAL), verifies that WAL is active, and then applies every known migration in
order. Request connections keep foreign-key enforcement enabled and use the configured busy timeout, but do not
renegotiate journal mode.

The database defaults to `data/panel.sqlite3` relative to the panel directory. `NO_PANEL_DATABASE_PATH` overrides that
path. `NO_PANEL_DATABASE_BUSY_TIMEOUT_MS` overrides the 5000 ms lock-wait default and accepts values from 0 through
600000 ms; `DATABASE_PATH` and `DATABASE_BUSY_TIMEOUT_MS` in `config.py` provide the corresponding static settings.

## Downgrades and rollback

Schema downgrade is unsupported. If an older panel opens a database containing later migration versions, startup
stops with an actionable `Database schema is newer than this panel version` error. It will not serve requests or try to
delete, reinterpret, or downgrade those records.

Before rolling back panel code:

1. Stop the panel so the database, `panel.sqlite3-wal`, and `panel.sqlite3-shm` are no longer changing.
2. Copy the database and any `-wal` and `-shm` companions to a dated backup directory on the same durable volume.
3. Keep that copy with the panel revision that created it.
4. Restore a database copy made by the target older revision, or upgrade the panel again. Do not point the older panel
   at a database created by a later schema.

## Intentional metadata reset

Stop the panel, then move `panel.sqlite3` and any `panel.sqlite3-wal` and `panel.sqlite3-shm` companions together into a
dated backup directory. Start the panel to create a new database and replay the migrations known to that revision.

This reset discards campaign-owned metadata added to SQLite, including later audit, job, configuration-history,
Workshop, and moderation records. It does not require deleting authoritative public-main configuration files such as
`servers.json`, `ports.json`, `panel_users.json`, dedicated-server JSON, startup scripts, or mission files. Keep the
moved database set until the reset has been reviewed and accepted.

## Startup failures

WAL, path, and migration failures are raised during application import. They appear in the foreground console or in
the service manager/container logs connected to standard error. A WAL error also identifies writability and file-locking
support as checks. Fix the storage condition or restore/upgrade the database, then restart; do not bypass the migration
guard.
