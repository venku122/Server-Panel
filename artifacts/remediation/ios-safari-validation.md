# Physical iOS Safari validation

Status: **pending — not performed**

No physical iPhone or real Safari/iOS execution environment was available during remediation. Chromium 149 mobile emulation passed the final PR10 production tree at 390x844 and 844x390, but that evidence is not represented as Safari validation.

The owner/device reviewer must still record exact device, iOS version, and Safari version while checking portrait/landscape drawer behavior, focus open/return, dialog trap/cancel, software keyboard, input zoom, safe areas, sticky server context, long errors, exact-text confirmation, and rotation with dialogs open and closed.

This is the sole external acceptance item. It blocks claiming complete PR3 campaign acceptance, but it does not invalidate the completed source, automated, or Chromium gates.
