import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BellRing, History, Play, Plus } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DeleteButton,
  Dialog,
  Dot,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  PageHeader,
  Select,
  SkeletonRows,
  Switch,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { Feed, FeedRuns, FeedPreset, FeedRun, WebhookList } from '../lib/types';

type Kind = Feed['kind'];
type Draft = { key: string; repo: string; label: string; destination: string; every: string };
const EMPTY: Draft = { key: '', repo: '', label: 'Internship', destination: '', every: '3' };

// The new feed form of one kind. initial is the submodule/key of a feed to start from, from the Add of a submodule on Explore.
function NewFeed({ prefix, kind, initial, onDone }: { prefix: string; kind: Kind; initial?: string | null; onDone: () => void }) {
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [preset, setPreset] = useState<FeedPreset | null>(null);
  const client = useQueryClient();
  const presets = useQuery({
    queryKey: ['feeds', prefix, 'presets'],
    queryFn: () => api<{ presets: FeedPreset[] }>(`/api/feeds/${prefix}/presets`),
  });
  // A feed posts to a Discord destination of Alerts
  const alerts = useQuery({ queryKey: ['webhooks', prefix], queryFn: () => api<WebhookList>(`/api/dashboard/${prefix}/webhooks`) });
  const destinations = (alerts.data?.webhooks ?? []).filter((h) => h.kind === 'discord');
  const choices = (presets.data?.presets ?? []).filter((p) => !p.added && p.kind === kind);
  const pick = (id: string) => {
    const chosen = choices.find((p) => `${p.submodule}/${p.key}` === id) ?? null;
    setPreset(chosen);
    if (!chosen) return setDraft({ ...EMPTY, destination: draft.destination });
    setDraft({
      key: chosen.key,
      repo: String(chosen.config.repo ?? ''),
      label: String(chosen.config.label ?? 'Job'),
      destination: draft.destination,
      every: String(chosen.every_hours),
    });
  };
  // The feed from Explore fills the form once, when the feeds of the submodules load.
  const applied = useRef(false);
  useEffect(() => {
    if (!presets.data || !initial || applied.current) return;
    applied.current = true;
    pick(initial);
  });
  const config = () => {
    const base = preset ? preset.config : {};
    return kind === 'github_jobs' ? { ...base, repo: draft.repo, label: draft.label } : base;
  };
  const create = useMutation({
    mutationFn: () =>
      send(`/api/feeds/${prefix}/feeds/${draft.key}`, 'PUT', {
        kind,
        destination_id: Number(draft.destination),
        every_hours: Number(draft.every),
        config: config(),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['feeds', prefix] });
      onDone();
    },
  });
  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  return (
    <form
        className="grid gap-5 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        {choices.length ? (
          <div className="sm:col-span-2">
            <Field label="Start from">
              <Select value={preset ? `${preset.submodule}/${preset.key}` : ''} onChange={(e) => pick(e.target.value)}>
              <option value="">A blank feed</option>
              {choices.map((p) => (
                <option key={`${p.submodule}/${p.key}`} value={`${p.submodule}/${p.key}`}>
                  {p.title} ({p.submodule_title})
                </option>
              ))}
              </Select>
            </Field>
          </div>
        ) : null}
        <Field label="Key" hint="Lowercase letters, digits and dashes">
          <Input value={draft.key} onChange={set('key')} placeholder={kind === 'github_jobs' ? 'internships' : 'hackathons'} required />
        </Field>
        {kind === 'github_jobs' ? (
          <>
            <Field label="Repository" hint="owner/name">
              <Input value={draft.repo} onChange={set('repo')} placeholder="vanshb03/Summer2026-Internships" required />
            </Field>
            <Field label="Label" hint="Word in each post title">
              <Input value={draft.label} onChange={set('label')} />
            </Field>
          </>
        ) : null}
        <Field label="Destination">
          {alerts.data && !destinations.length ? (
            <Link to={`/${prefix}/alerts`} className="flex h-9 items-center text-sm text-accent hover:underline">
              Add a Discord destination on Alerts
            </Link>
          ) : (
            <Select value={draft.destination} onChange={set('destination')} required>
              <option value="">Pick a channel</option>
              {destinations.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Every (hours)">
          <Input type="number" min={1} max={168} value={draft.every} onChange={set('every')} />
        </Field>
        <div className="sm:col-span-2">
          <FormActions error={create.error}>
            <Button variant="primary" disabled={create.isPending || !draft.destination}>
              Create feed
            </Button>
            <Button type="button" variant="ghost" onClick={onDone}>
              Cancel
            </Button>
          </FormActions>
        </div>
      </form>
  );
}

function runSummary(r: FeedRun): string {
  if (r.found === null) return 'source not read';
  if (r.recorded) return `${r.found} listed, ${r.new} recorded without posting`;
  return `${r.found} listed, ${r.new} new, ${r.posted} posted`;
}

function FeedHistory({ prefix, feed, onClose }: { prefix: string; feed: string | null; onClose: () => void }) {
  const history = useQuery({
    queryKey: ['feeds', prefix, 'history', feed],
    queryFn: () => api<FeedRuns>(`/api/feeds/${prefix}/feeds/${feed}/history`),
    enabled: Boolean(feed),
    refetchInterval: 10_000,
  });
  const runs = history.data?.runs ?? [];
  const items = history.data?.items ?? [];
  return (
    <Dialog
      open={Boolean(feed)}
      onClose={onClose}
      title={`History of ${feed ?? ''}`}
      description="The last 50 runs and items."
      wide
    >
      {history.error ? <ErrorNote error={history.error} /> : null}
      {history.isLoading ? (
        <SkeletonRows />
      ) : (
        <>
          <h3 className="mb-2 text-sm font-medium">Runs</h3>
          {runs.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>When</Th>
                  <Th>Result</Th>
                  <Th className="hidden sm:table-cell">Took</Th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r, i) => (
                  <Tr key={`${r.started_at}-${i}`}>
                    <Td className="whitespace-nowrap">
                      <span className="flex items-center gap-2">
                        <Dot tone={r.error ? 'bad' : 'ok'} />
                        {timeAgo(r.started_at)}
                      </span>
                    </Td>
                    <Td className="text-sm">
                      {runSummary(r)}
                      {r.error ? <div className="text-xs text-bad">{r.error}</div> : null}
                    </Td>
                    <Td className="hidden whitespace-nowrap text-muted sm:table-cell">{(r.duration_ms / 1000).toFixed(1)}s</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p className="text-sm text-muted">No runs yet.</p>
          )}
          <h3 className="mb-2 mt-6 text-sm font-medium">Items</h3>
          {items.length ? (
            <ul className="divide-y divide-line text-sm">
              {items.map((item, i) => (
                <li key={`${item.created_at}-${i}`} className="flex items-center gap-3 py-2">
                  <span className="min-w-0 flex-1 truncate">{item.title}</span>
                  <Badge>{item.posted ? 'posted' : 'recorded'}</Badge>
                  <span className="whitespace-nowrap text-xs text-muted">{timeAgo(item.created_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No items yet.</p>
          )}
        </>
      )}
    </Dialog>
  );
}

// The feeds of one webhook module, which runs one kind of feed.
function FeedsPage({ kind, title }: { kind: Kind; title: string }) {
  const { prefix } = useCurrentOrg();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const initial = params.get('new');
  const [adding, setAdding] = useState(Boolean(initial));
  const closeNew = () => {
    setAdding(false);
    if (initial) setParams({}, { replace: true });
  };
  const [viewing, setViewing] = useState<string | null>(null);
  const feeds = useQuery({
    queryKey: ['feeds', prefix],
    queryFn: () => api<{ feeds: Feed[] }>(`/api/feeds/${prefix}/feeds`),
    select: (body) => ({ feeds: body.feeds.filter((f) => f.kind === kind) }),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['feeds', prefix] });
  const toggle = useMutation({
    mutationFn: (f: Feed) => send(`/api/feeds/${prefix}/feeds/${f.key}`, 'PUT', { enabled: !f.enabled }),
    onSuccess: refresh,
  });
  const run = useMutation({ mutationFn: (key: string) => send(`/api/feeds/${prefix}/feeds/${key}/run`, 'POST', {}), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (key: string) => send(`/api/feeds/${prefix}/feeds/${key}`, 'DELETE'), onSuccess: refresh });
  const newFeed = (
    <Button variant="primary" onClick={() => setAdding(true)}>
      <Plus className="size-4" /> New feed
    </Button>
  );

  return (
    <>
      <PageHeader
        title={title}
        docs="modules/feeds"
        action={newFeed}
      />
      <Dialog open={adding} onClose={closeNew} title="New feed" description="The first run posts nothing; later runs post new listings." wide>
        {adding ? <NewFeed prefix={prefix} kind={kind} initial={initial} onDone={closeNew} /> : null}
      </Dialog>
      {feeds.error ? (
        <div className="mb-4">
          <ErrorNote error={feeds.error} />
        </div>
      ) : null}
      <Card>
        <CardHeader title="Feeds" hint={feeds.data ? `${feeds.data.feeds.length} feeds` : undefined} />
        {feeds.isLoading ? (
          <SkeletonRows />
        ) : feeds.data?.feeds.length ? (
          feeds.data.feeds.map((f) => (
            <div key={f.key} className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3 last:border-0">
              <Dot tone={!f.enabled ? 'muted' : f.last_error ? 'bad' : f.seeded_at ? 'ok' : 'warn'} />
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
                  <span className="truncate">{f.key}</span>
                  <Badge className="font-mono font-normal">
                    {f.kind === 'github_jobs' ? String(f.config.repo ?? '') : 'hackathons'}
                  </Badge>
                </div>
                <div className="mt-0.5 truncate text-xs text-muted">
                  {f.last_error ? (
                    <span className="text-bad">{f.last_error}</span>
                  ) : (
                    `every ${f.every_hours}h · last run ${timeAgo(f.last_run_at)} · ${f.posted} posted`
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Switch checked={f.enabled} onChange={() => toggle.mutate(f)} label={`Feed ${f.key} on`} />
                <Button variant="ghost" size="icon" title="History" aria-label={`History of ${f.key}`} onClick={() => setViewing(f.key)}>
                  <History className="size-4" />
                </Button>
                <Button variant="ghost" size="icon" title="Run now" aria-label={`Run ${f.key} now`} onClick={() => run.mutate(f.key)}>
                  <Play className="size-4" />
                </Button>
                <DeleteButton
                  label={`Delete ${f.key}`}
                  question={`Delete feed ${f.key}?`}
                  onDelete={() => remove.mutate(f.key)}
                />
              </div>
            </div>
          ))
        ) : (
          <EmptyState icon={BellRing} title="No feeds yet" action={adding ? null : newFeed} />
        )}
      </Card>
      <FeedHistory prefix={prefix} feed={viewing} onClose={() => setViewing(null)} />
    </>
  );
}

export const JobWebhookPage = () => <FeedsPage kind="github_jobs" title="Job alerts" />;
export const HackathonWebhookPage = () => <FeedsPage kind="hackathons" title="Hackathons" />;
