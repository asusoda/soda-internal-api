# web

The old officer app, kept for SoDA at admin.thesoda.io. It is a React app built with Vite and TypeScript 7. The [dashboard](../dashboard/README.md) has the same pages; add new pages there.

## Commands

Run these in `web/`. pnpm runs the version in `packageManager` in `package.json`.

```bash
pnpm install --frozen-lockfile   # install dependencies
pnpm dev                         # start the dev server on port 5000
pnpm test                        # run the Vitest tests
pnpm run typecheck               # run tsc
pnpm run build                   # type check, then build to build/
```

## Settings

The build reads `REACT_APP_API_URL`, the URL of the API. If it is not set, the app calls https://api.thesoda.io. `Dockerfile.web` takes it as a build argument and serves `build/` on port 5000.

## Files

| Path | Holds |
| --- | --- |
| `index.html` | The page that loads `src/index.tsx` |
| `src/App.tsx` | The routes |
| `src/types.ts` | API response types that more than one page uses |
| `src/components/auth/` | Sign-in state (`AuthContext.tsx`) and the route guard |
| `src/pages/` | One file for each page |
| `vite.config.ts` | The build, the dev server, PostCSS with Tailwind 3, and the Vitest settings |
