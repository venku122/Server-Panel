## Summary

- add a bounded, cached local Workshop index with explicit mission-file signatures and last-refresh state;
- preview rotation placement, incomplete collections, and file hashes without mutating files;
- make identical copies idempotent and require an explicit stop/replace-with-backup/skip/rename conflict policy;
- commit mission files, server configuration, encrypted server metadata, config-version metadata, and audit through one compensated mutation;
- keep remote-member surfaces honest by withholding coordinator-local library data and disabling unsupported mutation.

## Public-source boundary

Public `upstream/main` remains behavioral authority. This uses its local Steam cache, local mission directory, existing durable Workshop sync, and current two-slot rotation only. Hosted screenshots are visual references; no provider catalog/search, named playlists, remote file mutation, or invented metadata is included.

## Validation

- full local fork gate: pass;
- 108 cumulative tests, including non-mutating preview, full-rotation refusal, arbitrary-JSON rejection, bounded/cache behavior, conflict/idempotence policies, incomplete collection acknowledgement, successful atomic apply, and injected later-audit rollback: pass;
- four hashed before/after captures and 16 Chromium assertions across desktop/mobile: pass;
- physical iOS Safari: pending, unavailable in this environment and not claimed.

This is a fork-review PR only. It does not authorize or open an upstream PR.
