// Copies the repo's docs/*.md into content/docs as MDX, so docs/ stays the only source. A mermaid block becomes
// a Mermaid component.
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoDocs = path.resolve(here, '../../docs');
const out = path.resolve(here, '../content/docs');

interface Section {
  title: string;
  // Each page is its file in docs/ and its slug on the site.
  pages: [file: string, slug: string][];
}

const sections: Record<string, Section> = {
  modules: {
    title: 'Modules',
    pages: [
      ['modules/accounts.md', 'accounts'],
      ['modules/agents.md', 'agents'],
      ['modules/calendar.md', 'calendar'],
      ['modules/discord-bot.md', 'discord-bot'],
      ['modules/feeds.md', 'feeds'],
      ['modules/godfather.md', 'godfather'],
      ['modules/knowledge.md', 'knowledge'],
      ['modules/leetcode.md', 'leetcode'],
      ['modules/points.md', 'points'],
      ['modules/runpod-apps.md', 'runpod-apps'],
      ['modules/storefront.md', 'storefront'],
      ['modules/submodules.md', 'submodules'],
      ['modules/uptime.md', 'uptime'],
    ],
  },
  codebase: {
    title: 'Codebase',
    pages: [
      ['getting-started.md', 'getting-started'],
      ['architecture.md', 'architecture'],
      ['data-model.md', 'data-model'],
      ['authentication.md', 'authentication'],
      ['integrations.md', 'integrations'],
      ['writing-a-module.md', 'writing-a-module'],
      ['api-contract.md', 'api-contract'],
      ['operations.md', 'operations'],
      ['frontends.md', 'frontends'],
      ['webhooks.md', 'webhooks'],
      ['limits.md', 'limits'],
    ],
  },
  project: {
    title: 'Project',
    pages: [['roadmap.md', 'roadmap']],
  },
};

const routes = new Map<string, string>();
for (const [section, { pages }] of Object.entries(sections)) {
  for (const [file, slug] of pages) routes.set(file, `/docs/${section}/${slug}`);
}
routes.set('README.md', '/docs');

// A link relative to the page's file in docs/: its site route if the target is synced, else its GitHub URL.
function rewriteLink(target: string, from: string): string {
  if (/^[a-z]+:/i.test(target) || target.startsWith('#')) return target;
  const [rel, hash] = target.split('#');
  const file = path.posix.normalize(path.posix.join(path.posix.dirname(from), rel));
  const route = routes.get(file);
  if (route) return hash ? `${route}#${hash}` : route;
  const url = `https://github.com/asusoda/platform/blob/main/${path.posix.join('docs', file)}`;
  return hash ? `${url}#${hash}` : url;
}

function escapeText(text: string): string {
  return text
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\{/g, '&#123;')
    .replace(/\}/g, '&#125;');
}

function convertLine(line: string, from: string): string {
  const parts = line.split(/(`+[^`]*`+)/);
  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part;
      const links: string[] = [];
      const withTokens = part.replace(/\]\(([^)\s]+)\)/g, (_, target) => {
        links.push(rewriteLink(target, from));
        return `](\u0000${links.length - 1}\u0000)`;
      });
      return escapeText(withTokens).replace(/\u0000(\d+)\u0000/g, (_, n) => links[Number(n)]);
    })
    .join('');
}

function toMdx(markdown: string, from: string): string {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  let title = '';
  let fence: string | null = null;
  let chart: { fence: string; lines: string[] } | null = null;
  const body: string[] = [];
  for (const line of lines) {
    const opener = line.match(/^\s*(```+|~~~+)/);
    if (chart) {
      if (opener && opener[1].startsWith(chart.fence)) {
        body.push(`<Mermaid chart={${JSON.stringify(chart.lines.join('\n'))}} />`);
        chart = null;
      } else chart.lines.push(line);
      continue;
    }
    if (opener && /^\s*(```+|~~~+)mermaid\s*$/.test(line)) {
      chart = { fence: opener[1], lines: [] };
      continue;
    }
    if (fence) {
      body.push(line);
      if (opener && opener[1].startsWith(fence)) fence = null;
      continue;
    }
    if (opener) {
      fence = opener[1];
      body.push(line);
      continue;
    }
    if (!title && line.startsWith('# ')) {
      title = line.slice(2).replace(/^\d+\.\s*/, '').trim();
      continue;
    }
    body.push(line.startsWith('    ') ? line : convertLine(line, from));
  }
  const front = `---\ntitle: ${JSON.stringify(title)}\n---\n`;
  return `${front}\n${body.join('\n').trim()}\n`;
}

const sourcesMap: Record<string, string> = {};
for (const [section, { title, pages }] of Object.entries(sections)) {
  for (const [file, slug] of pages) sourcesMap[`${section}/${slug}.mdx`] = `docs/${file}`;
  const dir = path.join(out, section);
  await rm(dir, { recursive: true, force: true });
  await mkdir(dir, { recursive: true });
  for (const [file, slug] of pages) {
    const source = await readFile(path.join(repoDocs, file), 'utf8');
    await writeFile(path.join(dir, `${slug}.mdx`), toMdx(source, file));
  }
  await writeFile(
    path.join(dir, 'meta.json'),
    `${JSON.stringify({ title, pages: pages.map(([, slug]) => slug) }, null, 2)}\n`,
  );
}

await writeFile(
  path.resolve(here, '../lib/doc-sources.generated.json'),
  `${JSON.stringify(sourcesMap, null, 2)}\n`,
);
