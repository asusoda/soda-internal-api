import { useMutation, useQuery } from '@tanstack/react-query';
import { Database, Pencil, Play, Plus, ScrollText, SlidersHorizontal, Upload } from 'lucide-react';
import { type ReactNode, useDeferredValue, useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  Button,
  Card,
  CardHeader,
  cx,
  DeleteButton,
  Dialog,
  EmptyState,
  ErrorNote,
  Mono,
  Notice,
  PageHeader,
  Select,
  SearchInput,
  ShowMore,
  SkeletonRows,
  Stat,
  StatGrid,
  Switch,
  useShowMore,
} from '../../components/ui';
import { api, send } from '../../lib/api';
import { compact, count, keyPath } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import type { KnowledgeSource } from '../../lib/types';
import { crawlBody, CrawlForm, RunCrawl } from './crawl';
import { TestSearch } from './search';
import { KnowledgeSettingsForm } from './settings';
import { useInvalidate } from './shared';
import { countBy, DomainFilter, domainOf, SourceTable } from './sources';
import { UploadForm } from './upload';

// How long the sources list refetches every 5 seconds after a crawl or sync starts.
const WATCH_MS = 90_000;

export function KnowledgePage() {
  const { prefix } = useCurrentOrg();
  const invalidate = useInvalidate(prefix);
  const [editing, setEditing] = useState<KnowledgeSource | 'new' | null>(null);
  const [running, setRunning] = useState<KnowledgeSource | null>(null);
  const [uploading, setUploading] = useState(false);
  const [tuning, setTuning] = useState(false);
  const [filter, setFilter] = useState('');
  const [domain, setDomain] = useState('');
  const [watchUntil, setWatchUntil] = useState(0);
  const [notice, setNotice] = useState<ReactNode>(null);
  const list = useQuery({
    queryKey: ['knowledge', prefix, 'sources'],
    queryFn: () => api<{ sources: KnowledgeSource[]; can_publish: boolean }>(`/api/dashboard/${prefix}/knowledge/sources`),
    enabled: Boolean(prefix),
    refetchInterval: () => (Date.now() < watchUntil ? 5_000 : false),
  });
  const toggle = useMutation({
    mutationFn: (s: KnowledgeSource) =>
      send(`/api/dashboard/${prefix}/knowledge/crawls/${keyPath(s.key)}`, 'PUT', crawlBody(s, { enabled: !s.crawl?.enabled })),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (key: string) => send(`/api/dashboard/${prefix}/knowledge/sources/${keyPath(key)}`, 'DELETE'),
    onSuccess: invalidate,
  });

  const [query, setQuery] = useState('');
  const q = useDeferredValue(query.trim().toLowerCase());
  const data = list.data?.sources;
  const sources = useMemo(() => data ?? [], [data]);
  const { categories, domains, crawled, failing, chunks } = useMemo(() => {
    const crawled = sources.filter((s) => s.crawl);
    return {
      categories: [...new Set(sources.map((s) => s.category))].sort(),
      domains: countBy(sources.map((s) => domainOf(s.key))),
      crawled,
      failing: crawled.filter((s) => s.crawl?.last_error),
      chunks: sources.reduce((n, s) => n + s.chunk_count, 0),
    };
  }, [sources]);
  const shown = useMemo(
    () =>
      sources.filter(
        (s) =>
          (!filter || s.category === filter) &&
          (!domain || domainOf(s.key) === domain) &&
          (!q || s.key.toLowerCase().includes(q) || s.title?.toLowerCase().includes(q) || s.url?.toLowerCase().includes(q)),
      ),
    [sources, filter, domain, q],
  );
  const page = useShowMore(shown, `${filter}|${domain}|${q}`);
  const actionError = toggle.error ?? remove.error;
  // Row actions: crawled sources get schedule, run and edit controls; every source can be deleted.
  const actions = (s: KnowledgeSource, className?: string) => (
    <div className={cx('flex items-center gap-1', className)}>
      {s.crawl ? (
        <>
          <Switch
            checked={s.crawl.enabled}
            onChange={() => toggle.mutate(s)}
            disabled={toggle.isPending && toggle.variables?.key === s.key}
            label={`Crawl ${s.key} on schedule`}
          />
          <Button variant="ghost" size="icon" title="Run now" aria-label={`Run crawl of ${s.key} now`} onClick={() => setRunning(s)}>
            <Play className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" title="Edit" aria-label={`Edit ${s.key}`} onClick={() => setEditing(s)}>
            <Pencil className="size-4" />
          </Button>
        </>
      ) : null}
      <DeleteButton
        label={`Delete ${s.key}`}
        question={`Delete ${s.key} and its ${s.chunk_count} passages? Agents stop finding it at once.`}
        onDelete={() => remove.mutate(s.key)}
        className={cx(remove.isPending && remove.variables === s.key && 'opacity-50')}
      />
    </div>
  );

  const addCrawl = (
    <Button variant="primary" onClick={() => setEditing('new')}>
      <Plus className="size-4" /> Add crawl
    </Button>
  );
  const upload = (
    <Button onClick={() => setUploading(true)}>
      <Upload className="size-4" /> Upload
    </Button>
  );
  const headerActions = (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="ghost" onClick={() => setTuning(true)} aria-label="Search settings" title="Search settings">
        <SlidersHorizontal className="size-4" /> <span className="hidden sm:inline">Search settings</span>
      </Button>
      {upload}
      {addCrawl}
    </div>
  );

  return (
    <>
      <PageHeader
        title="Knowledge"
        description="Pages and documents that agents search."
        docs="modules/knowledge"
        action={headerActions}
      />
      <StatGrid className="mb-6">
        <Stat label="Sources" value={list.data ? count(sources.length) : '-'} />
        <Stat label="Crawled on a schedule" value={list.data ? count(crawled.length) : '-'} />
        <Stat
          label="Failing crawls"
          value={<span className={failing.length ? 'text-bad' : undefined}>{list.data ? failing.length : '-'}</span>}
        />
        <Stat label="Indexed passages" value={list.data ? compact(chunks) : '-'} />
      </StatGrid>
      {notice ? <Notice onDismiss={() => setNotice(null)}>{notice}</Notice> : null}
      {list.error || actionError ? (
        <div className="mb-4">
          <ErrorNote error={list.error ?? actionError} />
        </div>
      ) : null}
      {domains.length > 1 ? <DomainFilter total={sources.length} domains={domains} value={domain} onChange={setDomain} /> : null}
      <Card>
        <CardHeader
          title="Sources"
          hint={list.data ? `${count(shown.length)} of ${count(sources.length)} sources` : undefined}
          action={
            <div className="flex items-center gap-2">
              <Link
                to={`/${prefix}/activity?tab=knowledge`}
                className="flex h-8 items-center gap-1.5 rounded-md px-2 text-xs whitespace-nowrap text-muted hover:bg-panel-2 hover:text-fg"
              >
                <ScrollText className="size-3.5" /> Run log
              </Link>
              {categories.length > 1 ? (
              <Select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by category" className="h-8 w-auto text-xs">
                <option value="">All categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
              ) : null}
            </div>
          }
        />
        {sources.length > 10 ? (
          <div className="border-b border-line p-3">
            <SearchInput
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Find a source by key, title or URL"
              aria-label="Find a source"
            />
          </div>
        ) : null}
        {list.isLoading ? (
          <SkeletonRows />
        ) : shown.length ? (
          <>
            <SourceTable prefix={prefix} sources={page.shown} actions={actions} />
            <ShowMore list={page} noun="sources" />
          </>
        ) : sources.length ? (
          <EmptyState icon={Database} title="No source matches">
            Try another word, domain or category.
          </EmptyState>
        ) : (
          <EmptyState
            icon={Database}
            title="No sources yet"
            action={
              <div className="flex gap-2">
                {upload}
                {addCrawl}
              </div>
            }
          >
            Upload documents, add a page to crawl, or subscribe to shared content on Explore.
          </EmptyState>
        )}
      </Card>

      <TestSearch prefix={prefix} categories={categories} />

      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing && editing !== 'new' ? `Edit ${editing.key}` : 'Add crawl'}
        wide
      >
        {editing ? (
          <CrawlForm
            prefix={prefix}
            source={editing === 'new' ? null : editing}
            categories={categories}
            canPublish={list.data?.can_publish ?? false}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </Dialog>

      <Dialog
        open={uploading}
        onClose={() => setUploading(false)}
        title="Upload documents"
        wide
      >
        {uploading ? (
          <UploadForm
            prefix={prefix}
            categories={categories}
            canPublish={list.data?.can_publish ?? false}
            onUploaded={invalidate}
            onCancel={() => setUploading(false)}
          />
        ) : null}
      </Dialog>

      <Dialog
        open={tuning}
        onClose={() => setTuning(false)}
        title="Search settings"
        wide
      >
        {tuning ? (
          <KnowledgeSettingsForm
            prefix={prefix}
            onDone={(message) => {
              setTuning(false);
              if (message) {
                setNotice(message);
                setWatchUntil(Date.now() + WATCH_MS);
              }
            }}
          />
        ) : null}
      </Dialog>

      <Dialog open={running !== null} onClose={() => setRunning(null)} title={running ? `Run ${running.key}` : 'Run crawl'}>
        {running ? (
          <RunCrawl
            prefix={prefix}
            source={running}
            onDone={(queued) => {
              if (queued) {
                setNotice(
                  <>
                    Queued a crawl of <Mono className="text-fg">{running.key}</Mono>. The row updates when it ends.
                  </>,
                );
                setWatchUntil(Date.now() + WATCH_MS);
                invalidate();
              }
              setRunning(null);
            }}
          />
        ) : null}
      </Dialog>
    </>
  );
}
