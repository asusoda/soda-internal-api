import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { ArrowUpRight, Plus, SearchX } from 'lucide-react';
import { Link } from 'react-router';
import { Tooltip } from '../../components/tooltip';
import { Badge, Button, Card, EmptyState, ErrorNote, Spinner } from '../../components/ui';
import { api } from '../../lib/api';
import { useSubmodules, useSubscription } from './submodules';
import { matches } from '../../lib/modules';
import type { FeedPreset, CatalogModule } from '../../lib/types';

// The dashboard page of each module that has one.
const MODULE_PAGES: Record<string, string> = {
  points: 'points',
  storefront: 'store',
  calendar: 'calendar',
  leetcode: 'leetcode',
  godfather: 'godfather',
  runpod: 'hosting',
  event_webhook: 'webhooks',
  feeds: 'job-alerts',
  knowledge: 'knowledge',
  agents: 'agents',
  uptime: 'uptime',
};

// The page of each kind of feed
const KIND_PAGES: Record<string, string> = { github_jobs: 'job-alerts', hackathons: 'hackathons' };

// The modules whose submodules give feeds
const FEED_MODULES = { feeds: true };

// One submodule row inside a module card: a submodule or a feed the module can add.
function SubRow({ title, meta, action }: { title: string; meta?: string; action?: ReactNode }) {
  return (
    <div className="flex min-h-9 items-center gap-2 border-t border-line px-4 py-1.5 text-sm">
      <span className="min-w-0 flex-1 truncate">{title}</span>
      {meta ? <span className="shrink-0 text-xs text-muted tabular-nums">{meta}</span> : null}
      {action}
    </div>
  );
}

const subButton = 'h-7 px-2 text-xs';

// The submodules with pages or live queries. Subscribe makes knowledge search read the submodule's shared pages.
function KnowledgeSubmodules({ prefix }: { prefix: string }) {
  const submodules = useSubmodules(prefix);
  const change = useSubscription(prefix);
  const list = (submodules.data?.submodules ?? []).filter((s) => s.pages || s.queries.length);
  return (
    <>
      {list.map((s) => (
        <SubRow
          key={s.name}
          title={s.title}
          meta={s.subscribed && s.sources ? `${s.sources} pages shared` : `${s.pages} pages`}
          action={
            s.subscribed ? (
              <Badge tone="ok">Subscribed</Badge>
            ) : (
              <Button className={subButton} disabled={change.isPending} onClick={() => change.mutate({ name: s.name, on: true })}>
                {change.isPending && change.variables?.name === s.name ? <Spinner className="size-3.5" /> : <Plus className="size-3.5" />}
                Subscribe
              </Button>
            )
          }
        />
      ))}
      {change.error ? (
        <div className="px-4 pb-3">
          <ErrorNote error={change.error} />
        </div>
      ) : null}
    </>
  );
}

// The feeds a webhook module offers from the subscribed submodules. Add opens the new feed form on the module's page,
// which asks for the webhook. A submodule of the module that the org does not subscribe to links to the Submodules tab.
function ModuleFeeds({ m, prefix }: { m: CatalogModule; prefix: string }) {
  const presets = useQuery({
    queryKey: ['feeds', prefix, 'presets'],
    queryFn: () => api<{ presets: FeedPreset[] }>(`/api/feeds/${prefix}/presets`),
  });
  const submodules = useSubmodules(prefix);
  const subscribed = new Set((submodules.data?.submodules ?? []).filter((s) => s.subscribed).map((s) => s.name));
  return (
    <>
      {(presets.data?.presets ?? [])
        .filter((p) => p.module === m.name)
        .map((p) => (
          <SubRow
            key={`${p.submodule}/${p.key}`}
            title={p.title}
            meta={`every ${p.every_hours}h`}
            action={
              p.added ? (
                <Badge tone="ok">Added</Badge>
              ) : (
                <Link
                  to={`/${prefix}/${KIND_PAGES[p.kind] ?? MODULE_PAGES[m.name]}?new=${encodeURIComponent(`${p.submodule}/${p.key}`)}`}
                  className="inline-flex h-7 items-center gap-1 rounded-md border border-line bg-panel px-2 text-xs font-medium shadow-xs hover:bg-panel-2"
                >
                  <Plus className="size-3.5" /> Add
                </Link>
              )
            }
          />
        ))}
      {submodules.data
        ? m.submodules
            .filter((s) => !subscribed.has(s.name))
            .map((s) => (
              <SubRow
                key={s.name}
                title={s.title}
                action={
                  <Link to={`/${prefix}/explore?tab=submodules`} className="text-xs text-muted hover:text-fg hover:underline">
                    Subscribe for its feeds
                  </Link>
                }
              />
            ))
        : null}
    </>
  );
}

// The submodules of a module that is on. A module that is off lists its submodules by title.
function SubModules({ m, prefix }: { m: CatalogModule; prefix: string }) {
  if (m.enabled && m.name === 'knowledge') return <KnowledgeSubmodules prefix={prefix} />;
  if (m.enabled && m.name in FEED_MODULES) return <ModuleFeeds m={m} prefix={prefix} />;
  if (m.enabled || !m.submodules.length) return null;
  return (
    <>
      {m.submodules.map((p) => (
        <SubRow key={p.name} title={p.title} meta="Add the module first" />
      ))}
    </>
  );
}

// One module: title, one line of what it does, what it still needs, its sub-modules and one action.
export function ModuleCard({
  m,
  prefix,
  busy,
  onAdd,
  onRemove,
}: {
  m: CatalogModule;
  prefix: string;
  busy: boolean;
  onAdd: () => void;
  onRemove: () => void;
}) {
  const page = MODULE_PAGES[m.name];
  const missing = m.needs.filter((n) => !n.connected && !n.optional);
  return (
    <Card className="flex flex-col" data-module={m.name}>
      <div className="flex min-h-32 flex-1 flex-col p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-sm font-semibold">{m.title}</h3>
          {m.enabled && page ? (
            <Link to={`/${prefix}/${page}`} aria-label={`Open ${m.title}`} className="text-muted transition-colors hover:text-fg">
              <ArrowUpRight className="size-4" />
            </Link>
          ) : null}
        </div>
        <p className="mt-1 line-clamp-2 text-sm text-pretty text-muted">{m.description}</p>
        {m.enabled && m.limits.length ? (
          <div className="mt-2">
            <Tooltip label={m.limits.map((l) => l.label).join(', ')} side="top">
              <Link to={`/${prefix}/settings#limits`} className="inline-flex">
                <Badge>
                  {m.limits.length} {m.limits.length === 1 ? 'limit' : 'limits'}
                </Badge>
              </Link>
            </Tooltip>
          </div>
        ) : null}
        <div className="mt-auto flex items-center justify-between gap-3 pt-4">
          {missing.length ? (
            <Link to={`/${prefix}/explore?tab=integrations`} className="truncate text-xs text-warn hover:underline">
              Needs {missing.map((n) => n.label).join(', ')}
            </Link>
          ) : (
            <span />
          )}
          {!m.switchable ? (
            <span className="shrink-0 text-xs text-muted">Included</span>
          ) : m.enabled ? (
            <Button variant="ghost" className={`${subButton} shrink-0`} disabled={busy} onClick={onRemove}>
              Remove
            </Button>
          ) : (
            <Button className={`${subButton} shrink-0`} disabled={busy || !m.ready} onClick={onAdd}>
              <Plus className="size-3.5" /> Add
            </Button>
          )}
        </div>
      </div>
      <SubModules m={m} prefix={prefix} />
    </Card>
  );
}

// The modules in category sections, filtered by the search text.
export function ModuleGrid({
  categories,
  modules,
  query,
  render,
}: {
  categories: string[];
  modules: CatalogModule[];
  query: string;
  render: (m: CatalogModule) => ReactNode;
}) {
  const shown = modules.filter((m) => matches(m, query));
  if (!shown.length) {
    return (
      <Card>
        <EmptyState icon={SearchX} title="No module matches" />
      </Card>
    );
  }
  return (
    <div className="space-y-8">
      {categories
        .map((c) => ({ c, items: shown.filter((m) => m.category === c) }))
        .filter((g) => g.items.length)
        .map(({ c, items }) => (
          <section key={c} aria-label={c}>
            <h2 className="mb-3 text-xs font-medium tracking-wide text-muted uppercase">{c}</h2>
            <div className="grid items-start gap-4 sm:grid-cols-2 xl:grid-cols-3">{items.map(render)}</div>
          </section>
        ))}
    </div>
  );
}
