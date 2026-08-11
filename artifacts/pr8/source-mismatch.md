# PR 8 Workshop source boundary

Public `upstream/main` provides a local Steam Workshop cache, local mission directories, a two-slot current rotation, and an existing Workshop synchronization operation. It does not provide a Steam Web API credential, remote catalog/search implementation, named-playlist store, provider collection service, or coordinator-side authority over a remote member's filesystem.

The implementation therefore indexes only bounded local files with a mission signature, expands only locally described collection children, and reports missing children. It does not invent hosted metadata or named playlists. Remote-member pages never display coordinator-local content as though it belonged to the member.

Hosted screenshots remain visual references only. No upstream PR was opened or updated.
