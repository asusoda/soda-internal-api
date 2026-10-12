# Platform site

The landing page and documentation for Platform, built with Next.js and Fumadocs.

```bash
npm install
npm run dev      # http://localhost:3000
npm run build
```

`scripts/sync-docs.ts` copies the pages it lists from the repo's `docs/` into `content/docs/` as MDX before every dev run and build, so `docs/` stays the only source for those pages. Pages written only for the site (introduction, quickstart, concepts) live in `content/docs/` directly. The landing page is `app/(home)/page.tsx`. The orgs that build Platform are listed in `lib/orgs.ts`, with their logos in `public/orgs/`. To add an org, add one entry and its logo.

Deploy on Vercel with the root directory set to `site`, or with the `site` compose service (`Dockerfile.site`), as in `docs/operations.md`, "Host the docs site".
