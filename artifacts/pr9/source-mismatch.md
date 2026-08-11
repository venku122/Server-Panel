# PR 9 moderation source boundary

Public `upstream/main` provides local moderation configuration, ticket actions, the public DLL installer, Discord notifications, and signed cluster transport. It does not provide a hosted moderation provider, external identity service, proprietary enforcement backend, or provider-managed installation system.

The extraction keeps those public behaviors and routes behind typed repository/service/installer/blueprint boundaries. Browser mutation identity comes only from the authenticated session. A cluster-supplied actor is trusted only after HMAC request verification.

No upstream PR was opened or updated.
