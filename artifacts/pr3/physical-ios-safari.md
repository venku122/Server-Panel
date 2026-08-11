# Physical iOS Safari validation status

Status: **required and not yet completed**.

The automated evidence uses Chromium with 390x844 and 844x390 mobile viewports. It validates layout and interaction
in a repeatable browser harness, but it is not physical iOS Safari evidence and is not represented as such.

Before PR 3 can receive final campaign approval, a real iPhone or iPad running Safari must verify the scoped server
overview and settings routes, navigation drawer focus/scroll behavior, 16px form-input zoom behavior, destructive
confirmation guards, diagnostics redaction, and stability of foreground diagnostics during background refreshes.
