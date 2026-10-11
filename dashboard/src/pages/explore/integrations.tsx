import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BookOpen, LogIn, PlugZap, SearchX } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { IntegrationIcon } from '../../components/integration-icons';
import {
  Badge,
  Button,
  Card,
  cx,
  Dialog,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  PageSkeleton,
  Spinner,
  Textarea,
} from '../../components/ui';
import { send } from '../../lib/api';
import { timeAgo } from '../../lib/format';
import { docsPage } from '../../lib/links';
import { useCurrentOrg } from '../../lib/org';
import { useIntegrations } from '../../lib/queries';
import type { Integration, IntegrationList, IntegrationTest, OAuthState } from '../../lib/types';

// The module names the API sends, with their label and dashboard page.
const MODULES: Record<string, { label: string; path?: string }> = {
  agents: { label: 'Agent memory' },
  mcp: { label: 'MCP', path: 'tokens' },
  auth: { label: 'Sign-in' },
  calendar: { label: 'Calendar sync', path: 'calendar' },
  godfather: { label: 'Godfather', path: 'godfather' },
  dashboard: { label: 'Activity', path: 'activity' },
  games: { label: 'Games' },
  knowledge: { label: 'Knowledge', path: 'knowledge' },
  leetcode: { label: 'LeetCode', path: 'leetcode' },
  submodules: { label: 'Knowledge', path: 'knowledge' },
  runpod: { label: 'Hosting', path: 'hosting' },
};

// The groups of cards, in order. An integration with a key in no group goes in the last group.
const GROUPS: { title: string; keys: string[] }[] = [
  { title: 'Accounts', keys: ['discord', 'github', 'google', 'notion', 'runpod'] },
  { title: 'Services', keys: [] },
];

function StateBadge({ i }: { i: Integration }) {
  if (i.source === 'org') return <Badge tone="ok">Connected</Badge>;
  if (i.source === 'deployment') return <Badge tone="active">Platform's key</Badge>;
  return <Badge tone="warn">Not connected</Badge>;
}

function KeysForm({ prefix, i, onDone }: { prefix: string; i: Integration; onDone: () => void }) {
  const client = useQueryClient();
  // Fields that are not secret start with their saved value; secret ones start empty.
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(i.fields.filter((f) => !f.secret && f.value).map((f) => [f.name, f.value as string])),
  );
  const save = useMutation({
    mutationFn: (fields: Record<string, string | null>) =>
      send<IntegrationList>(`/api/dashboard/${prefix}/integrations/${i.key}`, 'PUT', { fields }),
    onSuccess: (list) => {
      client.setQueryData(['integrations', prefix], list);
      onDone();
    },
  });
  // Changed fields only. An emptied field that is not secret clears its saved value.
  const filled: Record<string, string | null> = {};
  for (const f of i.fields) {
    const v = (values[f.name] ?? '').trim();
    if (!f.secret && f.set && !v) filled[f.name] = null;
    else if (v && (f.secret || v !== f.value)) filled[f.name] = v;
  }
  const anySet = i.fields.some((f) => f.set);
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (Object.keys(filled).length) save.mutate(filled);
      }}
    >
      {i.fields.map((f) => (
        <Field
          key={f.name}
          label={f.optional ? `${f.label} (optional)` : f.label}
          hint={f.set && f.secret ? `Saved ${timeAgo(f.updated_at)}. Leave empty to keep it. ${f.hint}` : f.hint}
        >
          {f.kind === 'json' ? (
            <div className="space-y-2">
              <Textarea
                rows={5}
                className="font-mono text-xs"
                value={values[f.name] ?? ''}
                placeholder={f.set ? 'Saved' : '{ "type": "service_account", ... }'}
                onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
              />
              <input
                type="file"
                accept="application/json,.json"
                aria-label={`${f.label} file`}
                className="text-xs text-muted file:mr-2 file:cursor-pointer file:rounded-md file:border file:border-line file:bg-panel file:px-2 file:py-1 file:text-xs"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (file) setValues({ ...values, [f.name]: await file.text() });
                }}
              />
            </div>
          ) : (
            <Input
              type={f.secret ? 'password' : f.kind === 'url' ? 'url' : 'text'}
              autoComplete="off"
              className={f.secret ? undefined : 'font-mono text-xs'}
              value={values[f.name] ?? ''}
              placeholder={f.set && f.secret ? 'Saved' : f.kind === 'url' ? 'https://' : ''}
              onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
            />
          )}
        </Field>
      ))}
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!Object.keys(filled).length || save.isPending}>
          {save.isPending ? <Spinner className="size-3.5" /> : null}
          Save
        </Button>
        {anySet ? (
          <Button
            type="button"
            variant="danger"
            disabled={save.isPending}
            onClick={() => save.mutate(Object.fromEntries(i.fields.map((f) => [f.name, null])))}
          >
            Disconnect
          </Button>
        ) : null}
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function signedIn(state: OAuthState): string {
  const who = state.connected_by ? ` (${state.connected_by})` : '';
  const when = state.connected_at ? `, ${timeAgo(state.connected_at)}` : '';
  return `Agents use ${state.title}'s own MCP tools as the person who signed in${who}${when}.`;
}

// The sign-in that lets agents use the service's own MCP server as the person who signs in.
function OAuthRow({ prefix, k, state }: { prefix: string; k: string; state: OAuthState }) {
  const client = useQueryClient();
  const start = useMutation({
    mutationFn: () => send<{ url: string }>(`/api/dashboard/${prefix}/integrations/${k}/oauth`, 'POST'),
    onSuccess: (body) => window.location.assign(body.url),
  });
  const stop = useMutation({
    mutationFn: () => send<IntegrationList>(`/api/dashboard/${prefix}/integrations/${k}/oauth`, 'DELETE'),
    onSuccess: (list) => client.setQueryData(['integrations', prefix], list),
  });
  return (
    <div className="mx-4 mb-3 rounded-md border border-line px-3 py-2.5 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-fg">Agent sign-in</span>
        {state.connected ? <Badge tone="ok">Signed in</Badge> : null}
        <span className="ml-auto flex gap-2">
          {state.connected ? (
            <Button variant="ghost" disabled={stop.isPending} onClick={() => stop.mutate()}>
              Sign out
            </Button>
          ) : (
            <Button variant="secondary" disabled={Boolean(state.blocked) || start.isPending} onClick={() => start.mutate()}>
              {start.isPending ? <Spinner className="size-3.5" /> : <LogIn className="size-3.5" />} Sign in with {state.title}
            </Button>
          )}
        </span>
      </div>
      <p className="mt-1 text-muted">
        {state.connected ? signedIn(state) : (state.blocked ?? `Sign in to give agents the tools of ${state.title}'s own MCP server, acting as you.`)}
      </p>
      {start.error ? <ErrorNote error={start.error} /> : null}
      {stop.error ? <ErrorNote error={stop.error} /> : null}
    </div>
  );
}

function IntegrationCard({ prefix, i, canSave, oauth }: { prefix: string; i: Integration; canSave: boolean; oauth?: OAuthState }) {
  const [editing, setEditing] = useState(false);
  const test = useMutation({
    mutationFn: () => send<IntegrationTest>(`/api/dashboard/${prefix}/integrations/${i.key}/test`, 'POST'),
  });
  const saved = i.fields.filter((f) => f.set && f.updated_at).map((f) => f.updated_at as string);
  // The modules that use the integration and the ones it unlocks, in one list. Explore opens a module that is off.
  const users = [
    ...i.used_by.map((m) => ({ label: MODULES[m]?.label ?? m, path: MODULES[m]?.path ?? 'explore' })),
    ...(i.unlocks ?? []).map((title) => ({ label: title, path: 'explore' })),
  ].filter((u, n, all) => all.findIndex((o) => o.label === u.label) === n);
  const note = [
    i.source === 'deployment' && i.editable ? "Platform's shared key is in use. Save your own to replace it." : '',
    i.source === 'deployment' && i.metered_by.length
      ? `Counts against: ${i.metered_by.map((l) => l.label.toLowerCase()).join(', ')}.`
      : '',
    saved.length ? `Saved ${timeAgo(saved.sort().at(-1) as string)}.` : '',
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <Card className="flex flex-col">
      <div className="flex items-start gap-3 p-4">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-line bg-panel-2/60">
          <IntegrationIcon name={i.key} className="size-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">{i.title}</h3>
            <span title={note || undefined}>
              <StateBadge i={i} />
            </span>
          </div>
          <p className="mt-1 line-clamp-2 text-sm text-pretty text-muted">{i.description}</p>
        </div>
      </div>
      {users.length ? (
        <div className="flex flex-wrap items-center gap-1.5 px-4 pb-3 text-xs text-muted">
          Used by
          {users.map((u) => (
            <Link
              key={u.label}
              to={`/${prefix}/${u.path}`}
              className="rounded-md border border-line px-1.5 py-0.5 text-fg transition-colors hover:bg-panel-2"
            >
              {u.label}
            </Link>
          ))}
        </div>
      ) : null}
      {oauth ? <OAuthRow prefix={prefix} k={i.key} state={oauth} /> : null}
      {test.data ? (
        <div
          className={cx('mx-4 mb-3 animate-in rounded-md px-3 py-2 text-xs', test.data.ok ? 'bg-ok/10 text-ok' : 'bg-bad/10 text-bad')}
          role="status"
        >
          {test.data.message}
        </div>
      ) : null}
      {test.error ? (
        <div className="mx-4 mb-3">
          <ErrorNote error={test.error} />
        </div>
      ) : null}
      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-line px-4 py-3">
        {i.editable ? (
          <Button variant={i.source === 'org' ? 'secondary' : 'primary'} disabled={!canSave} onClick={() => setEditing(true)}>
            <PlugZap className="size-4" /> {i.source === 'org' ? 'Edit keys' : 'Connect'}
          </Button>
        ) : null}
        {i.testable ? (
          <Button variant="ghost" disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? <Spinner className="size-3.5" /> : null} Test
          </Button>
        ) : null}
        {i.docs ? (
          <a
            href={docsPage(i.docs)}
            target="_blank"
            rel="noreferrer"
            className="ml-auto flex items-center gap-1 text-xs text-muted transition-colors hover:text-fg"
          >
            <BookOpen className="size-3.5" /> Docs
          </a>
        ) : null}
      </div>
      <Dialog
        open={editing}
        onClose={() => setEditing(false)}
        title={`Connect ${i.title}`}
        description="Secret keys are never shown again."
      >
        <KeysForm prefix={prefix} i={i} onDone={() => setEditing(false)} />
      </Dialog>
    </Card>
  );
}

// The outside services the org connects, filtered by the search text: their keys and the modules that use them.
export function IntegrationsTab({ query }: { query: string }) {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useIntegrations(prefix);
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const q = query.trim().toLowerCase();
  const found = data.integrations.filter((i) => !q || `${i.key} ${i.title} ${i.description}`.toLowerCase().includes(q));
  return (
    <>
      {!data.secrets_key ? (
        <div className="mb-4">
          <ErrorNote error="SECRETS_KEY is not set on the API, so keys cannot be saved." />
        </div>
      ) : null}
      {!found.length ? (
        <Card>
          <EmptyState icon={SearchX} title="No integration matches" />
        </Card>
      ) : null}
      <div className="space-y-8">
        {GROUPS.map((g, n) => {
          const last = n === GROUPS.length - 1;
          const items = found.filter((i) => g.keys.includes(i.key) || (last && !GROUPS.some((o) => o.keys.includes(i.key))));
          return items.length ? (
            <section key={g.title} aria-label={g.title}>
              <h2 className="mb-3 text-xs font-medium tracking-wide text-muted uppercase">{g.title}</h2>
              <div className="grid items-start gap-4 md:grid-cols-2">
                {items.map((i) => (
                  <IntegrationCard key={i.key} prefix={prefix} i={i} canSave={data.secrets_key} oauth={data.oauth?.[i.key]} />
                ))}
              </div>
            </section>
          ) : null;
        })}
      </div>
    </>
  );
}
