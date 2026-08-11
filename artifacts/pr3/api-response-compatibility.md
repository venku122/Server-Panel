# PR 3 API response compatibility

PR 3 deliberately narrows only response fields that exposed internal server records or filesystem paths. Public-main
callers consume the retained fields below:

| Route or helper | Retained caller fields | Removed fields | Compatibility result |
| --- | --- | --- | --- |
| local server deletion | `success`, `removed.id`, `removed.name`, `deleted_files` | full server record and secret/path-bearing fields | Active callers use success and safe identity only. |
| remote server deletion proxy | `success`, `removed.id`, `removed.name`, `deleted_files` | proxied server list and secret/path-bearing fields | Response is normalized to the local safe contract. |
| startup settings | `success`, `settings` | batch/config paths and full server record | Settings UI reads only `settings`; existing saves remain unchanged. |

The response-minimization tests exercise local deletion, remote deletion, and startup settings and fail if a password,
install path, complete server record, or removed compatibility field reappears.
