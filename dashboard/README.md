# Dashboard

Officer dashboard for Platform: the pages officers use to see and control one org, and a Superadmin page for the superadmin. Vite, React, Tailwind and TanStack Query.

```bash
npm install
npm run dev
npm test
npm run build          # tsc, then vite build to dist/
npm run screenshots    # images for the landing page, see docs/frontends.md
npm run demo-video     # the demo video for the landing page, see docs/frontends.md
npm run perf           # long lists: time of each step and long tasks
```

## Layout

```
src/
  main.tsx, app.tsx        start the app; app.tsx makes the routes from pages/registry.tsx
  index.css                theme tokens
  components/
    ui/                    shared parts, imported from components/ui: layout (page header, cards, stats),
                           data (tables, badges), controls (buttons, fields), feedback (states, notes,
                           long lists), overlays (dialogs, form footers)
    tabs.tsx               TabBar and useTabParam
    tooltip.tsx            Tooltip and Kbd
    module-gate.tsx        the note for a module that is off
    shell.tsx              sidebar, top bar and page frame; the sidebar comes from pages/registry.tsx
    auth-frame.tsx         the frame of the sign-in, sign-in return and org list pages
    built-by.tsx           the marks of the orgs that build Platform
    activity-list.tsx, org-mark.tsx, logo.tsx, brand-icons.tsx
  lib/
    api.ts, auth.ts        API client and sign-in tokens
    runtime-config.ts      the settings in /config.js, which the container writes when it starts
    queries.ts             queries that two or more pages use
    links.ts               repo, docs and landing page links, and the orgs that build Platform
    sidebar.ts             the collapsed state of the sidebar and its shortcut
    format.ts, branding.ts, theme.ts, org.ts
    types/                 API response shapes, one file for each domain
  pages/
    registry.tsx           every org page: path, label, icon, section, module, component
    <page>.tsx             a small page
    <page>/index.tsx       a large page; the other files in the folder are its parts
public/orgs/               logos for the org marks
scripts/
  fixtures.ts             API responses for a fictional org, and largeFixtures() with long lists
  screenshots.ts          screenshots for the landing page
  demo-video.ts           the demo video for the landing page
  perf.ts                 timing and long tasks of the long lists
```

Node runs the TypeScript in `scripts/` directly, so those files use only types that Node can remove. `npm run typecheck` checks them with `scripts/tsconfig.json`.

To add a page, write the page file and add one entry to `PAGES` in `src/pages/registry.tsx`. See [docs/frontends.md](../docs/frontends.md) for all the steps, the routes, sign-in and deployment.
