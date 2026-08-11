# Vercel UX research

Reviewed 2026-08-11. The redesign borrows interaction and information-architecture patterns, not Vercel branding, assets, or proprietary implementation.

## Official references and applied patterns

- [Dashboard navigation redesign rollout](https://vercel.com/changelog/dashboard-navigation-redesign-rollout) and [new dashboard navigation](https://vercel.com/changelog/new-dashboard-navigation-available): persistent scope, consistent global/project navigation, collapsible desktop sidebar, and one-handed mobile navigation became Panel/server scope, grouped navigation, a resizable sidebar, and a bottom bar.
- [Redesigned Deployments List](https://vercel.com/changelog/redesigned-deployments-list): higher scan density, compact status, relative time, progress, and contextual actions informed Servers and Jobs.
- [Dashboard universal search](https://vercel.com/changelog/dashboard-universal-search): Cmd/Ctrl+K Find groups Servers, Pages, and Settings and contains no mutation actions.
- [Runtime Logs search and filtering](https://vercel.com/changelog/redesigned-search-and-filtering-for-runtime-logs) and [Runtime Logs](https://vercel.com/docs/logs/runtime): structured filters, active chips, compact events, and contextual detail informed Activity.
- [Projects](https://vercel.com/docs/projects) and [Project Settings](https://vercel.com/docs/project-configuration/project-settings): summary-first Overview and separation of operations from settings informed the selected-server IA.
- [Geist](https://vercel.com/geist/introduction), [Tabs](https://vercel.com/geist/tabs), [Table](https://vercel.com/geist/table), [Entity](https://vercel.com/geist/entity), [Description](https://vercel.com/geist/description), [Sheet](https://vercel.com/geist/sheet), [Drawer](https://vercel.com/geist/drawer), [Empty State](https://vercel.com/geist/empty-state), [Input](https://vercel.com/geist/input), [Menu](https://vercel.com/geist/menu), [Note](https://vercel.com/geist/note), [Progress](https://vercel.com/geist/progress), [Typography](https://vercel.com/geist/typography), and [Materials](https://vercel.com/geist/materials): shared semantic primitives, restrained surfaces, tight typography, status meaning, focus behavior, and progressive disclosure.

## Intentionally not copied

- No React, Next.js, Vercel icons, screenshots, logos, terminology, telemetry, deployment graph, domains, analytics, or invented observability.
- Initial HTML remains Flask/Jinja server-rendered and vanilla JavaScript progressively enhances navigation, details, polling, and confirmation.
- Server mutations retain the public source's explicit APIs, role checks, signatures, durable jobs, and blocking confirmation flows.

## Source limitations

The public source does not expose reliable health percentages, deployment URLs, CPU/memory charts, complete build/version metadata, or always-available player counts. Those values remain absent or use an em dash. Remote Workshop behavior remains bounded by cached/local source data.
