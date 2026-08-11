# PR 10 contract source boundary

Public `upstream/main` provides the configuration editors, server creation and port updates, durable job routes, Workshop operations, moderation installation, and signed cluster transport covered by these contracts. It does not provide a private provider schema, hosted control-plane contract, provider-only job type, or proprietary compatibility promise.

The Pydantic layer therefore stabilizes only public-main request, persistence, and browser response boundaries. Supported job types are explicit. Additive fields from a newer cluster peer are ignored for version 1 compatibility, but unknown operations are rejected before persistence or dispatch. Invalid historical rows render safe warning placeholders and are never treated as executable jobs.

The hosted screenshots remain visual references only. They do not authorize provider-specific fields or behavior.

No upstream PR was opened or updated.
