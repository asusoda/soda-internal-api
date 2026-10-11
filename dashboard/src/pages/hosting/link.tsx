import { useMutation } from '@tanstack/react-query';
import { ExternalLink, Link2, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Button, Field, FormActions, Input, Mono, Select, Spinner } from '../../components/ui';
import { send } from '../../lib/api';
import type { App, AppKind } from '../../lib/types';
import { DeletePanel } from './actions';
import { Fact, Label, NAME_PATTERN, useInvalidate } from './shared';

export const LINK_KINDS: { kind: AppKind; title: string }[] = [
  { kind: 'site', title: 'Site' },
  { kind: 'service', title: 'Service' },
  { kind: 'bot', title: 'Bot' },
  { kind: 'agent', title: 'Agent' },
  { kind: 'database', title: 'Database' },
];

const csv = (text: string) =>
  text
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);

// Link a service that runs outside Platform. Platform lists it and Uptime checks its URL; it never deploys it.
export function LinkApp({ prefix, onDone }: { prefix: string; onDone: (name: string | null) => void }) {
  const invalidate = useInvalidate(prefix);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [kind, setKind] = useState<AppKind>('service');
  const [description, setDescription] = useState('');
  const [runsAs, setRunsAs] = useState('');
  const urlOk = !url || /^https:\/\/\S+$/.test(url);
  const ready = NAME_PATTERN.test(name) && urlOk;
  const save = useMutation({
    mutationFn: () =>
      send<App>(`/api/dashboard/${prefix}/apps/${name}/link`, 'PUT', {
        url: url.trim() || null,
        kind,
        description: description.trim() || null,
        runs_as: csv(runsAs),
      }),
    onSuccess: (app) => {
      invalidate();
      onDone(app.name);
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) save.mutate();
      }}
    >
      <p className="text-sm text-muted">A service that runs outside Platform. Uptime checks its URL; Platform never deploys it.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" hint="Lowercase letters, digits and dashes.">
          <Input value={name} onChange={(e) => setName(e.target.value.trim())} aria-invalid={!NAME_PATTERN.test(name) && name !== ''} placeholder="vault" />
        </Field>
        <Field label="Kind">
          <Select value={kind} onChange={(e) => setKind(e.target.value as AppKind)}>
            {LINK_KINDS.map((k) => (
              <option key={k.kind} value={k.kind}>
                {k.title}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="URL" hint="Public https. Optional.">
        <Input value={url} onChange={(e) => setUrl(e.target.value.trim())} aria-invalid={!urlOk} placeholder="https://vault.thesoda.io" />
      </Field>
      <Field label="Description">
        <Input value={description} maxLength={200} onChange={(e) => setDescription(e.target.value)} placeholder="Password manager" />
      </Field>
      <Field label="Runs as" hint="Containers or processes, comma-separated.">
        <Input value={runsAs} onChange={(e) => setRunsAs(e.target.value)} placeholder="vaultwarden" />
      </Field>
      <FormActions error={save.error ?? undefined}>
        <Button variant="primary" disabled={!ready || save.isPending}>
          {save.isPending ? <Spinner className="size-3.5" /> : <Link2 className="size-4" />} Link service
        </Button>
        <Button type="button" variant="ghost" onClick={() => onDone(null)}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

// The panel of a linked app: what it is and what runs it. It has no deploys or pod.
export function LinkedPanel({
  prefix,
  app,
  onDeleted,
}: {
  prefix: string;
  app: App;
  onDeleted: (name: string, podId: string | null) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Fact label="Kind">{LINK_KINDS.find((k) => k.kind === app.kind)?.title ?? app.kind}</Fact>
        <div className="col-span-2">
          <Fact label="URL">
            {app.url ? (
              <a href={app.url} target="_blank" rel="noreferrer" className="inline-flex max-w-full items-center gap-1 truncate hover:underline">
                {app.url}
                <ExternalLink className="size-3.5 shrink-0" />
              </a>
            ) : (
              <span className="text-muted">none</span>
            )}
          </Fact>
        </div>
      </div>
      {app.description ? <p className="text-sm">{app.description}</p> : null}
      <section>
        <Label>Runs as</Label>
        {app.runs_as.length ? (
          <div className="flex flex-wrap gap-1.5">
            {app.runs_as.map((r) => (
              <Mono key={r} className="rounded-md border border-line bg-panel-2 px-1.5 py-0.5 text-fg">
                {r}
              </Mono>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">Not given.</p>
        )}
      </section>
      <div className="flex">
        <Button variant="danger" className="ml-auto" onClick={() => setDeleting(!deleting)}>
          <Trash2 className="size-4" /> Unlink
        </Button>
      </div>
      {deleting ? <DeletePanel prefix={prefix} app={app} onDone={() => setDeleting(false)} onDeleted={onDeleted} /> : null}
    </div>
  );
}
