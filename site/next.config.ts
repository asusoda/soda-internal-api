import { createMDX } from 'fumadocs-mdx/next';
import type { NextConfig } from 'next';

const withMDX = createMDX();

// Docs pages that were merged into other pages keep their old URLs.
const movedDocs: Record<string, string> = {
  '/docs/codebase/backend-modules': '/docs/codebase/architecture',
  '/docs/codebase/api-reference': '/docs/codebase/api-contract',
  '/docs/codebase/discord-bot': '/docs/codebase/architecture',
  '/docs/codebase/frontend': '/docs/codebase/frontends',
  '/docs/codebase/deployment-and-operations': '/docs/codebase/operations',
  '/docs/codebase/gotchas': '/docs/project/roadmap',
  '/docs/modules/dashboard': '/docs/codebase/frontends',
  '/docs/modules/tools-and-mcp': '/docs/codebase/architecture',
  '/docs/project/runpod-deploy': '/docs/codebase/getting-started',
  '/docs/modules/alerts': '/docs/modules/feeds',
  '/docs/modules/compute': '/docs/modules/godfather',
  '/docs/modules/packs': '/docs/modules/submodules',
};

const config: NextConfig = {
  reactStrictMode: true,
  // A self-contained server in .next/standalone, for Dockerfile.site. Vercel ignores it.
  output: 'standalone',
  // Contributor avatars on the landing page
  images: { remotePatterns: [{ protocol: 'https', hostname: 'avatars.githubusercontent.com' }] },
  async redirects() {
    return Object.entries(movedDocs).map(([source, destination]) => ({ source, destination, permanent: true }));
  },
};

export default withMDX(config);
