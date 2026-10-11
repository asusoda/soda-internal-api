import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Megaphone, Pencil, Plus, Send } from 'lucide-react';
import { useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  CheckOption,
  cx,
  DeleteButton,
  Dialog,
  Dot,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  Mono,
  PageHeader,
  Select,
  SkeletonRows,
  Spinner,
  Switch,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { Webhook, WebhookList, WebhookTest } from '../lib/types';

type Draft = { name: string; kind: string; url: string; events: string[] };

// The form to add a destination, or to change one. When it changes one, an empty URL keeps the saved URL.
function WebhookForm({ prefix, list, hook, onDone }: { prefix: string; list: WebhookList; hook: Webhook | null; onDone: () => void }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<Draft>({
    name: hook?.name ?? '',
    kind: hook?.kind ?? list.kinds[0]?.key ?? 'discord',
    url: '',
    events: hook?.events ?? ['errors'],
  });
  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: draft.name,
        events: draft.events,
        ...(draft.url.trim() ? { url: draft.url.trim() } : {}),
      };
      return hook
        ? send(`/api/dashboard/${prefix}/webhooks/${hook.id}`, 'PUT', body)
        : send(`/api/dashboard/${prefix}/webhooks`, 'POST', {
            ...body,
            kind: draft.kind,
          });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['webhooks', prefix] });
      onDone();
    },
  });
  const kind = list.kinds.find((k) => k.key === draft.kind);
  const toggle = (key: string, on: boolean) =>
    setDraft({
      ...draft,
      events: on ? [...draft.events, key] : draft.events.filter((e) => e !== key),
    });
  return (
    <form
      className="grid gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Name">
          <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Officer channel" required />
        </Field>
        <Field label="Service">
          <Select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })} disabled={Boolean(hook)}>
            {list.kinds.map((k) => (
              <option key={k.key} value={k.key}>
                {k.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field
        label={`${kind?.label ?? 'Webhook'} webhook URL`}
        hint="Never shown again after you save."
      >
        <Input
          type="url"
          value={draft.url}
          onChange={(e) => setDraft({ ...draft, url: e.target.value })}
          placeholder={hook ? 'Saved. Paste a new URL to replace it.' : kind?.example}
          required={!hook}
        />
      </Field>
      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Events</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {list.events.map((e) => (
            <CheckOption key={e.key} checked={draft.events.includes(e.key)} onChange={(on) => toggle(e.key, on)} title={e.label}>
              {e.description}
            </CheckOption>
          ))}
        </div>
      </fieldset>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={save.isPending || !draft.events.length}>
          {hook ? 'Save' : 'Add destination'}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function WebhookRow({ prefix, hook, labels, onEdit }: { prefix: string; hook: Webhook; labels: Map<string, string>; onEdit: () => void }) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ['webhooks', prefix] });
  const toggle = useMutation({
    mutationFn: () =>
      send(`/api/dashboard/${prefix}/webhooks/${hook.id}`, 'PUT', {
        enabled: !hook.enabled,
      }),
    onSuccess: refresh,
  });
  const test = useMutation({
    mutationFn: () => send<WebhookTest>(`/api/dashboard/${prefix}/webhooks/${hook.id}/test`, 'POST'),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => send(`/api/dashboard/${prefix}/webhooks/${hook.id}`, 'DELETE'),
    onSuccess: refresh,
  });
  const error = toggle.error ?? test.error ?? remove.error;
  return (
    <div className="border-b border-line px-4 py-3 last:border-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Dot tone={!hook.enabled ? 'muted' : hook.last_error ? 'bad' : 'ok'} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm font-medium">
            <span className="truncate">{hook.name}</span>
            <Badge>{hook.kind === 'discord' ? 'Discord' : hook.kind}</Badge>
            <Mono className="hidden text-xs font-normal text-muted sm:inline">{hook.url_hint}</Mono>
          </div>
          <div className="mt-1 truncate text-xs text-muted" title={hook.events.map((key) => labels.get(key) ?? key).join(', ')}>
            {hook.events.length} {hook.events.length === 1 ? 'event' : 'events'} ·{' '}
            {hook.last_error ? (
              <span className="text-bad">{hook.last_error}</span>
            ) : hook.last_sent_at ? (
              `last message ${timeAgo(hook.last_sent_at)}`
            ) : (
              'no messages yet'
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Switch checked={hook.enabled} onChange={() => toggle.mutate()} label={`Destination ${hook.name} on`} disabled={toggle.isPending} />
          <Button variant="ghost" size="icon" title="Send test" aria-label={`Send a test to ${hook.name}`} disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? <Spinner className="size-3.5" /> : <Send className="size-4" />}
          </Button>
          <Button variant="ghost" size="icon" title="Edit" aria-label={`Edit ${hook.name}`} onClick={onEdit}>
            <Pencil className="size-4" />
          </Button>
          <DeleteButton label={`Delete ${hook.name}`} question={`Delete destination ${hook.name}?`} onDelete={() => remove.mutate()} />
        </div>
      </div>
      {test.data ? (
        <div
          className={cx('mt-2 animate-in rounded-md px-3 py-2 text-xs', test.data.ok ? 'bg-ok/10 text-ok' : 'bg-bad/10 text-bad')}
          role="status"
        >
          {test.data.message}
        </div>
      ) : null}
      {error ? (
        <div className="mt-2">
          <ErrorNote error={error} />
        </div>
      ) : null}
    </div>
  );
}

// Each event and feed, and the destinations it goes to. Events with no destination show only in Activity.
function RoutesCard({ list }: { list: WebhookList }) {
  const on = list.webhooks.filter((h) => h.enabled);
  const names = new Map(list.webhooks.map((h) => [h.id, h.name]));
  const rows = [
    ...list.events.map((e) => ({ key: `event:${e.key}`, label: e.label, to: on.filter((h) => h.events.includes(e.key)).map((h) => h.name) })),
    ...list.feeds.map((f) => ({
      key: `feed:${f.key}`,
      label: `Feed ${f.key}`,
      to: f.destination_id != null ? [names.get(f.destination_id) ?? '-'] : f.webhook_set ? ['Own webhook'] : [],
    })),
  ];
  return (
    <Card>
      <CardHeader title="Routes" />
      <Table>
        <thead>
          <tr>
            <Th>Event</Th>
            <Th>Goes to</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <Tr key={r.key}>
              <Td className="w-1/2 max-w-0 truncate">{r.label}</Td>
              <Td className="max-w-0">
                <div className="flex flex-wrap gap-1">
                  {r.to.length ? r.to.map((name) => <Badge key={name}>{name}</Badge>) : <span className="text-xs text-muted">Activity only</span>}
                </div>
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

export function AlertsPage() {
  const { prefix } = useCurrentOrg();
  const [editing, setEditing] = useState<Webhook | 'new' | null>(null);
  const list = useQuery({
    queryKey: ['webhooks', prefix],
    queryFn: () => api<WebhookList>(`/api/dashboard/${prefix}/webhooks`),
  });
  const data = list.data;
  const labels = new Map((data?.events ?? []).map((e) => [e.key, e.label]));
  const hooks = data?.webhooks ?? [];

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Where the org's events and feeds go."
        docs="codebase/webhooks"
        action={
          <Button variant="primary" disabled={!data?.secrets_key} onClick={() => setEditing('new')}>
            <Plus className="size-4" /> New destination
          </Button>
        }
      />
      {list.error ? (
        <div className="mb-4">
          <ErrorNote error={list.error} />
        </div>
      ) : null}
      {data && !data.secrets_key ? (
        <div className="mb-4 rounded-md bg-warn/10 px-3 py-2 text-sm text-warn" role="status">
          SECRETS_KEY is not set on the API, so destination URLs cannot be saved.
        </div>
      ) : null}
      <div className="grid gap-6">
        <Card>
          <CardHeader title="Destinations" hint={data ? `${hooks.length} ${hooks.length === 1 ? 'destination' : 'destinations'}` : undefined} />
          {list.isLoading ? (
            <SkeletonRows />
          ) : hooks.length ? (
            hooks.map((h) => <WebhookRow key={h.id} prefix={prefix} hook={h} labels={labels} onEdit={() => setEditing(h)} />)
          ) : (
            <EmptyState icon={Megaphone} title="No destinations">
              Add a Discord channel webhook. Events still show in Activity.
            </EmptyState>
          )}
        </Card>
        {data && (hooks.length || data.feeds.length) ? <RoutesCard list={data} /> : null}
      </div>
      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'New destination' : `Edit ${editing?.name ?? ''}`}
        wide
      >
        {data && editing !== null ? (
          <WebhookForm
            key={editing === 'new' ? 'new' : editing.id}
            prefix={prefix}
            list={data}
            hook={editing === 'new' ? null : editing}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </Dialog>
    </>
  );
}
