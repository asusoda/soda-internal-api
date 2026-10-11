// Takes screenshots of the built dashboard for the site, with every API call answered from fixtures.mjs.
// Run with npm run screenshots. Needs Playwright with Chromium: a global install, or npm i --no-save playwright.
// PLAYWRIGHT_CHROMIUM sets the Chromium binary when the installed browser does not match the Playwright version.
// SCREENS takes a comma-separated list of screen names to take only those.

import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import { mkdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { preview } from 'vite';
import { asuDuoFixtures, fixtures, ORG } from './fixtures.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const out = resolve(root, process.env.SCREENSHOT_DIR ?? '../site/public/screenshots');
const WIDTH = 1440;
const HEIGHT = 900;
const QUALITY = 0.86;
const SCALE = 2;

// Each screen is a dashboard path and, optionally, a step that runs before the screenshot and its own fixtures.
const SCREENS = [
  { name: 'overview', path: '' },
  { name: 'hosting', path: 'godfather' },
  {
    name: 'tokens-scopes',
    path: 'tokens',
    before: async (page) => {
      await page.getByRole('button', { name: 'New token' }).click();
      await page.getByLabel('knowledge:read').check();
    },
  },
  {
    name: 'tokens-integrations',
    path: 'tokens',
    before: async (page) => {
      await page.getByRole('button', { name: 'New token' }).click();
      await page.getByLabel('google:read').check();
      await page.locator('legend', { hasText: /^Google$/ }).scrollIntoViewIfNeeded();
      await page.mouse.wheel(0, 260);
    },
  },
  {
    name: 'tokens',
    path: 'tokens',
    before: async (page) => {
      await page.getByRole('button', { name: 'New token' }).click();
      await page.getByPlaceholder('club-agent').fill('events-agent');
      await page.getByLabel('knowledge:read').check();
      await page.getByLabel('calendar:read').check();
      await page.getByLabel('github:read').check();
      await page.getByPlaceholder('my-org/website, my-org/*').fill('my-org/*');
    },
  },
  {
    name: 'integrations-sign-in',
    path: 'explore?tab=integrations',
    before: async (page) => {
      await page.getByRole('button', { name: 'Sign in with Google' }).scrollIntoViewIfNeeded();
      await page.mouse.wheel(0, -200);
    },
  },
  {
    name: 'asu-signed-out',
    path: 'explore?tab=integrations',
    before: async (page) => {
      await page.getByRole('button', { name: 'Sign in to ASU' }).scrollIntoViewIfNeeded();
      await page.mouse.wheel(0, 200);
    },
  },
  {
    name: 'asu-duo',
    path: 'explore?tab=integrations',
    fixtures: asuDuoFixtures,
    before: async (page) => {
      await page.getByLabel('Duo code').scrollIntoViewIfNeeded();
      await page.mouse.wheel(0, 200);
    },
  },
  { name: 'activity', path: 'activity' },
  { name: 'explore', path: 'explore' },
  { name: 'explore-submodules', path: 'explore?tab=submodules' },
  {
    name: 'explore-feeds',
    path: 'explore',
    before: async (page) => {
      await page.getByRole('heading', { name: 'Feeds', exact: true }).scrollIntoViewIfNeeded();
    },
  },
  { name: 'hosting-apps', path: 'hosting' },
  {
    name: 'hosting-linked',
    path: 'hosting',
    before: async (page) => {
      await page.getByRole('button', { name: 'vault', exact: true }).click();
    },
  },
  { name: 'settings', path: 'settings' },
  {
    name: 'settings-limits',
    path: 'settings#limits',
    before: async (page) => {
      await page.getByRole('heading', { name: 'Limits' }).scrollIntoViewIfNeeded();
    },
  },
  { name: 'superadmin', path: 'admin' },
  {
    name: 'superadmin-limits',
    path: 'admin',
    before: async (page) => {
      await page.getByRole('button', { name: 'Limits of Data Science Club' }).click();
    },
  },
  { name: 'webhooks', path: 'webhooks' },
  { name: 'uptime', path: 'uptime' },
  {
    name: 'uptime-edit',
    path: 'uptime',
    before: async (page) => {
      await page.getByRole('button', { name: 'Edit Parts inventory API' }).click();
    },
  },
  {
    name: 'knowledge-search',
    path: 'knowledge',
    before: async (page) => {
      await page.getByLabel('Search query').fill('When are build nights?');
      await page.getByRole('button', { name: 'Search', exact: true }).click();
      await page.getByText('Full text').first().scrollIntoViewIfNeeded();
    },
  },
  { name: 'knowledge-source', path: 'knowledge/sources/club/build-nights?chunk=c1' },
];

const only = process.env.SCREENS?.split(',').filter(Boolean);

async function loadPlaywright() {
  try {
    return await import('playwright');
  } catch {
    const globalRoot = execSync('npm root -g', { encoding: 'utf8' }).trim();
    return createRequire(join(globalRoot, 'noop.js'))('playwright');
  }
}

async function main() {
  const { chromium } = await loadPlaywright();
  const server = await preview({ root, preview: { port: 4179, strictPort: true }, logLevel: 'warn' });
  const base = 'http://localhost:4179';
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined });
  mkdirSync(out, { recursive: true });
  try {
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({
        viewport: { width: WIDTH, height: HEIGHT },
        deviceScaleFactor: SCALE,
        colorScheme: theme,
        reducedMotion: 'reduce',
      });
      await context.addInitScript((t) => {
        localStorage.setItem('platform.access_token', 'screenshot-placeholder');
        localStorage.setItem('platform.theme', t);
      }, theme);
      let data = fixtures();
      await context.route('**/api/**', (route) => {
        const url = new URL(route.request().url());
        if (url.origin === base) return route.fallback();
        const body = data[url.pathname];
        if (body === undefined) return route.fulfill({ status: 404, json: { error: `No fixture for ${url.pathname}` } });
        return route.fulfill({ status: 200, json: body });
      });
      const page = await context.newPage();
      for (const screen of SCREENS.filter((s) => !only?.length || only.includes(s.name))) {
        data = (screen.fixtures ?? fixtures)();
        await page.goto(`${base}/${ORG.prefix}${screen.path ? `/${screen.path}` : ''}`);
        await page.waitForLoadState('networkidle');
        if (screen.before) await screen.before(page);
        await page.evaluate(() => document.fonts.ready);
        await page.mouse.move(0, HEIGHT - 1);
        const png = await page.screenshot({ type: 'png' });
        const webp = await page.evaluate(
          async ({ b64, quality }) => {
            const image = new Image();
            image.src = `data:image/png;base64,${b64}`;
            await image.decode();
            const canvas = document.createElement('canvas');
            canvas.width = image.width;
            canvas.height = image.height;
            canvas.getContext('2d').drawImage(image, 0, 0);
            return canvas.toDataURL('image/webp', quality).split(',')[1];
          },
          { b64: png.toString('base64'), quality: QUALITY },
        );
        const file = join(out, `${screen.name}-${theme}.webp`);
        writeFileSync(file, Buffer.from(webp, 'base64'));
        console.log(`${file} ${Math.round(statSync(file).size / 1024)} KB`);
      }
      await context.close();
    }
  } finally {
    await browser.close();
    await new Promise((done) => server.httpServer.close(done));
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
