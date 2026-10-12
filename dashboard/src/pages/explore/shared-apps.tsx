import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, Plus, UserPlus } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Card, Dialog, ErrorNote, Field, FormActions, Spinner, Textarea } from '../../components/ui';
import { api, send } from '../../lib/api';
import type { SharedApp, SharedAppSubscribe } from '../../lib/types';

const key = (prefix: string) => ['shared-apps', prefix];
const title = (name: string) => name.charAt(0).toUpperCase() + name.slice(1);

// The emails in free text: one per line, or split by commas or spaces.
const parse = (text: string) => [...new Set(text.split(/[\s,;]+/).map((e) => e.trim()).filter(Boolean))];

function Invite({ prefix, app, onDone }: { prefix: string; app: SharedApp; onDone: () => void }) {
  const client = useQueryClient();
  const [text, setText] = useState('');
  const invite = useMutation({
    mutationFn: () => send<SharedAppSubscribe>(`/api/dashboard/${prefix}/shared-apps/${app.name}/subscription`, 'PUT', { emails: parse(text) }),
    onSuccess: () => client.invalidateQueries({ queryKey: key(prefix) }),
  });
  if (invite.data) {
    return (
      <div className="space-y-4">
        <ul className="space-y-1 text-sm">
          {Object.entries(invite.data.results).map(([email, result]) => (
            <li key={email} className="flex items-center justify-between gap-3">
              <span className="truncate">{email}</span>
              <Badge tone={result.startsWith('not ') ? 'bad' : 'ok'}>{result}</Badge>
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">
          Each person opens {app.url ?? 'the vault'}, creates an account with that email and sets their own master password. The first one creates
          the org's organization in the vault and adds the others.
        </p>
        <FormActions>
          <Button variant="primary" onClick={onDone}>
            Done
          </Button>
        </FormActions>
      </div>
    );
  }
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        invite.mutate();
      }}
    >
      <Field label="Emails" hint="One per line. Platform never sees their master passwords.">
        <Textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder={'ada@example.org\ngrace@example.org'} />
      </Field>
      <FormActions error={invite.error}>
        <Button variant="primary" disabled={!parse(text).length || invite.isPending}>
          {invite.isPending ? <Spinner className="size-3.5" /> : <UserPlus className="size-4" />} Invite
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

// The shared apps an org can use: the deployment runs one copy, and each org gets its own space in it.
export function SharedApps({ prefix, query }: { prefix: string; query: string }) {
  const client = useQueryClient();
  const [inviting, setInviting] = useState<SharedApp | null>(null);
  const list = useQuery({ queryKey: key(prefix), queryFn: () => api<{ apps: SharedApp[] }>(`/api/dashboard/${prefix}/shared-apps`) });
  const leave = useMutation({
    mutationFn: (name: string) => send(`/api/dashboard/${prefix}/shared-apps/${name}/subscription`, 'DELETE'),
    onSuccess: () => client.invalidateQueries({ queryKey: key(prefix) }),
  });
  const q = query.trim().toLowerCase();
  const apps = (list.data?.apps ?? []).filter((a) => !q || `${a.name} ${a.description ?? ''}`.toLowerCase().includes(q));
  if (list.error) return <ErrorNote error={list.error} />;
  if (!apps.length) return null;
  return (
    <section aria-label="Shared apps" className="space-y-3">
      <h2 className="text-xs font-medium tracking-wide text-muted uppercase">Apps</h2>
      {leave.error ? <ErrorNote error={leave.error} /> : null}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {apps.map((a) => (
          <Card key={a.name} className="flex flex-col p-4" data-shared-app={a.name}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="flex items-center gap-1.5 text-sm font-semibold">
                  {title(a.name)}
                  {a.url ? (
                    <a href={a.url} target="_blank" rel="noreferrer" aria-label={`Open ${a.name}`} className="text-muted hover:text-fg">
                      <ArrowUpRight className="size-4" />
                    </a>
                  ) : null}
                </h3>
                <p className="mt-1 line-clamp-2 text-sm text-pretty text-muted">{a.description}</p>
              </div>
              {a.subscribed ? <Badge tone="ok">Subscribed</Badge> : null}
            </div>
            {a.subscribed && a.invited.length ? (
              <p className="mt-3 truncate text-xs text-muted" title={a.invited.join(', ')}>
                Invited: {a.invited.join(', ')}
              </p>
            ) : null}
            <div className="mt-auto flex items-center justify-between gap-3 pt-4">
              <span className="text-xs text-muted tabular-nums">{a.subscribers} {a.subscribers === 1 ? 'org' : 'orgs'}</span>
              <div className="flex gap-1">
                {a.subscribed ? (
                  <Button variant="ghost" className="h-7 shrink-0 px-2 text-xs" disabled={leave.isPending} onClick={() => leave.mutate(a.name)}>
                    Unsubscribe
                  </Button>
                ) : null}
                <Button className="h-7 shrink-0 px-2 text-xs" onClick={() => setInviting(a)}>
                  {a.subscribed ? <UserPlus className="size-3.5" /> : <Plus className="size-3.5" />} {a.subscribed ? 'Invite' : 'Subscribe'}
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
      <Dialog open={inviting !== null} onClose={() => setInviting(null)} title={inviting ? `${title(inviting.name)}: invite people` : ''} description="Each person gets an account in the shared app. Your org's items stay in your org's space.">
        {inviting ? <Invite key={inviting.name} prefix={prefix} app={inviting} onDone={() => setInviting(null)} /> : null}
      </Dialog>
    </section>
  );
}
