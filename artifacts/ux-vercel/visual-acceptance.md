# Visual acceptance

## Automated matrix

- Viewports: 1200×800, 1600×1000, 390×844, and 844×390 compact landscape.
- Baseline: 44 uncropped route captures from remote review commit `66c8bbd`.
- Redesigned: 90 uncropped captures covering 11 major routes plus sidebar, Find, filters, menus, sheets, drawers, restore confirmation, and Workshop review.
- Redesigned result: zero horizontal overflow, zero console errors, zero page errors, focus returned after sheets/drawers, and zero Workshop mutation requests before final confirmation.
- Baseline result: 12 console errors from routes/resources absent in the old stack; preserved as source-state evidence rather than hidden.

## Material-difference gate

Pass. Servers is a dense resource table; Overview is summary-first; Operations and Settings own their respective workflows; Activity resembles a log stream; Jobs resembles a deployment list; Workshop uses contextual detail; Players and Moderation share a domain; Recordings is grouped; desktop navigation is prioritized and collapsible; mobile uses a bottom bar and More drawer.

## Acceptance defects found and corrected

- Activity and Jobs overflow beside an expanded sidebar at 1200px.
- Activity detail sheet was initially placed beneath its backdrop.
- Long server identities overflowed 390px cards.
- Settings subnavigation exceeded the mobile content width.
- Activity and Jobs horizontal filter rails expanded the mobile layout viewport.
- Delayed Moderation filesystem paths overflowed after async status load.

## Physical iPhone Safari

A paired iPhone 17 Pro Max was detected as available. Device-native interaction remained pending because the Mac was locked and the mirroring/control surface could not be opened. Chromium mobile evidence is not represented as physical Safari evidence.
