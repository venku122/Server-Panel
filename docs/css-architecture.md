# CSS ownership and migration

The panel's styles are being moved from a single legacy file into an explicit
layered system. Keep ownership clear when changing the interface:

- `static/style.css` is transitional legacy CSS. Existing rules remain there
  until they are migrated, but new page or component rules do not belong there.
- Reusable component rules belong in the matching file under
  `static/css/components/`.
- Page-specific rules belong in `static/css/pages.css`. A dedicated page
  stylesheet is appropriate when a page grows beyond a small cohesive section.
- Design tokens such as colors, spacing, radii, and shadows belong in
  `static/css/tokens.css`.
- New inline `style=` attributes are prohibited. An exceptional inline value
  must be documented with a narrow source-backed reason and added to the
  validation allowlist before review.

The cascade order is defined in `templates/base.html`: tokens, transitional
legacy rules, base/layout layers, component layers, then page rules. Do not
change that order incidentally when adding a stylesheet.
