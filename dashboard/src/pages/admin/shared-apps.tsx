import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Boxes, KeyRound, Plus, Rocket, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Card, CardHeader, Dialog, DocsLink, EmptyState, ErrorNote, Field, FormActions, Input, Mono, SkeletonRows, Table, Td, Textarea, Th, Tr } from '../../components/ui';
import { api, send } from '../../lib/api';
import { deployTone } from '../../lib/format';
import type { SharedAppAdmin } from '../../lib/types';

const KEY = ['superadmin-shared-apps'];
const BASE = '/api/superadmin/shared-apps';
type Open = { kind: 'register' } | { kind: 'deploy' | 'secrets'; app: SharedAppAdmin } | null;

function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: KEY });
}

function Register({ onDone }: { onDone: () => void }) {
  const refresh = useRefresh();
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  const save = useMutation({
    mutationFn: () => send(`${BASE}/${name}`, 'PUT', { manifest: JSON.parse(text) }),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <Field label="Name" hint="Lowercase letters, digits and dashes. The container is shared-<name>.">
        <Input value={name} onChange={(e) => setName(e.target.value.trim())} placeholder="vault" required autoFocus />
      </Field>
      <Field label="Manifest (JSON)" hint="A This server manifest. access: {kind: vaultwarden} invites people when an org subscribes.">
        <Textarea rows={10} className="font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} required />
      </Field>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!name || !text || save.isPending}>
          Save
        </Button>
      </FormActions>
    </form>
  );
}

function Deploy({ app, onDone }: { app: SharedAppAdmin; onDone: () => void }) {
  const refresh = useRefresh();
  const [tag, setTag] = useState(app.current_tag ?? '');
  const deploy = useMutation({
    mutationFn: () => send(`${BASE}/${app.name}/deploy`, 'POST', { tag }),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        deploy.mutate();
      }}
    >
      <Field label="Tag" hint={`Of ${app.manifest.image}`}>
        <Input value={tag} onChange={(e) => setTag(e.target.value.trim())} className="font-mono" required autoFocus />
      </Field>
      <FormActions error={deploy.error}>
        <Button variant="primary" disabled={!tag || deploy.isPending}>
          <Rocket className="size-4" /> Deploy
        </Button>
      </FormActions>
    </form>
  );
}

function Secrets({ app, onDone }: { app: SharedAppAdmin; onDone: () => void }) {
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const save = useMutation({
    mutationFn: () => send(`${BASE}/${app.name}/secrets`, 'PUT', { secrets: { [key]: value } }),
    onSuccess: onDone,
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <Field label="Env name" hint="Such as ADMIN_TOKEN. The manifest's secret_env names it.">
        <Input value={key} onChange={(e) => setKey(e.target.value.trim().toUpperCase())} className="font-mono" required autoFocus />
      </Field>
      <Field label="Value" hint="Encrypted. Never shown again.">
        <Input type="password" value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" required />
      </Field>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!key || !value || save.isPending}>
          Save
        </Button>
      </FormActions>
    </form>
  );
}

// Apps the deployment owns on This server. Orgs subscribe to them on the Shared tab of Explore.
export function SharedAppsCard() {
  const refresh = useRefresh();
  const [open, setOpen] = useState<Open>(null);
  const list = useQuery({ queryKey: KEY, queryFn: () => api<{ apps: SharedAppAdmin[] }>(BASE), refetchInterval: 30_000 });
  const rollback = useMutation({ mutationFn: (name: string) => send(`${BASE}/${name}/rollback`, 'POST', {}), onSuccess: refresh });
  const apps = list.data?.apps ?? [];
  const close = () => setOpen(null);
  return (
    <Card>
      <CardHeader
        title="Shared apps"
        hint="Owned by the deployment, used by orgs."
        action={
          <div className="flex items-center gap-2">
            <DocsLink page="modules/runpod-apps#shared-apps" />
            <Button onClick={() => setOpen({ kind: 'register' })} aria-label="Register shared app">
              <Plus className="size-4" /> <span className="hidden sm:inline">Register</span>
            </Button>
          </div>
        }
      />
      {list.error || rollback.error ? (
        <div className="p-4">
          <ErrorNote error={list.error ?? rollback.error} />
        </div>
      ) : null}
      {list.isLoading ? <SkeletonRows rows={2} /> : null}
      {list.data && !apps.length ? <EmptyState icon={Boxes} title="No shared apps" /> : null}
      {apps.length ? (
        <Table>
          <thead>
            <tr>
              <Th>App</Th>
              <Th className="hidden sm:table-cell">Tag</Th>
              <Th>Status</Th>
              <Th className="hidden md:table-cell">Orgs</Th>
              <Th>
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {apps.map((a) => (
              <Tr key={a.name}>
                <Td className="w-full max-w-0">
                  <div className="truncate font-medium">{a.name}</div>
                  <Mono className="block truncate">{a.url ?? `shared-${a.name}`}</Mono>
                </Td>
                <Td className="hidden sm:table-cell">
                  <Mono className="text-fg">{a.current_tag ?? '-'}</Mono>
                </Td>
                <Td>
                  <Badge tone={a.latest_deployment ? deployTone(a.latest_deployment.status) : 'muted'}>{a.latest_deployment?.status ?? 'not deployed'}</Badge>
                </Td>
                <Td className="hidden text-muted tabular-nums md:table-cell">{a.subscribers}</Td>
                <Td>
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="icon" title="Deploy" aria-label={`Deploy ${a.name}`} onClick={() => setOpen({ kind: 'deploy', app: a })}>
                      <Rocket className="size-4" />
                    </Button>
                    <Button variant="ghost" size="icon" title="Roll back" aria-label={`Roll back ${a.name}`} disabled={rollback.isPending} onClick={() => rollback.mutate(a.name)}>
                      <RotateCcw className="size-4" />
                    </Button>
                    <Button variant="ghost" size="icon" title="Secrets" aria-label={`Secrets of ${a.name}`} onClick={() => setOpen({ kind: 'secrets', app: a })}>
                      <KeyRound className="size-4" />
                    </Button>
                  </div>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      ) : null}
      <Dialog open={open?.kind === 'register'} onClose={close} title="Register shared app" wide>
        {open?.kind === 'register' ? <Register onDone={close} /> : null}
      </Dialog>
      <Dialog open={open?.kind === 'deploy'} onClose={close} title={open?.kind === 'deploy' ? `Deploy ${open.app.name}` : ''}>
        {open?.kind === 'deploy' ? <Deploy app={open.app} onDone={close} /> : null}
      </Dialog>
      <Dialog open={open?.kind === 'secrets'} onClose={close} title={open?.kind === 'secrets' ? `Secret of ${open.app.name}` : ''}>
        {open?.kind === 'secrets' ? <Secrets app={open.app} onDone={close} /> : null}
      </Dialog>
    </Card>
  );
}
