# PR 4 persistence source boundary

The hosted/provider branch source is unavailable, so its database ownership and migration model cannot be inspected.
Public `upstream/main`, the production authority for this campaign, contains no database dependency, schema, migration
runner, or persistence abstraction. PR 4 therefore follows the directive's no-existing-database path and introduces
one embedded file-backed SQLite database at `data/panel.sqlite3`.

This increment contains only connection lifecycle, required pragmas, explicit transactions, schema migration records,
and a repository base. It does not add audit, job, job-event, configuration-version, or provider-specific tables; it
does not migrate or modify existing JSON/file-backed state.
