# Information architecture before

The baseline at fork review commit `66c8bbd` retained the original feature-inventory mental model.

- Server Overview exposed lifecycle, mission, password, configuration, Workshop, and tool controls together.
- Servers used sparse repeated cards with little cross-server comparison.
- Global navigation promoted Ports, Cluster, Users, Discord, and About alongside primary workflows.
- Selected-server navigation promoted Moderation, NoBlackBox, Gallery, and Configuration History as independent destinations.
- Activity, Jobs, and Workshop existed but read as separate feature pages with persistent cards rather than one operational narrative.
- Mobile primarily compressed desktop navigation and did not provide a one-handed primary destination model.
- Detail and secondary actions competed with primary tasks on the main canvas.

The captured baseline includes expected console errors for routes that did not yet exist at `66c8bbd`, including the canonical Moderation sibling route. See `screenshots/before/validation-results.json`.
