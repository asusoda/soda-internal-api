import { IntegrationHint } from '../../components/integration-hint';
import { useQuery } from '@tanstack/react-query';
import { Boxes, LayoutTemplate, Plus } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router';
import { Button, Card, CardHeader, Dialog, EmptyState, ErrorNote, Mono, Notice, PageHeader, SkeletonRows } from '../../components/ui';
import { api } from '../../lib/api';
import { useCurrentOrg } from '../../lib/org';
import type { App, AppKind } from '../../lib/types';
import { AppPanel } from './detail';
import { RegisterApp } from './register';
import { TemplatePicker } from './templates';
import { providerTitle, useProviders } from './providers';
import { AppTable } from './table';

// Apps are grouped by what they are for; the host is a detail of each app.
const KINDS: { kind: AppKind; title: string }[] = [
  { kind: 'bot', title: 'Bots' },
  { kind: 'agent', title: 'Agents' },
  { kind: 'site', title: 'Sites' },
  { kind: 'service', title: 'Services' },
];

// The apps that the org deploys to its hosting providers.
export function HostingPage() {
  const [params] = useSearchParams();
  // Member pods moved to the Godfather page.
  return params.get('tab') === 'pods' ? <Navigate to="../godfather" replace /> : <Services />;
}

function Services() {
  const { prefix } = useCurrentOrg();
  const [registering, setRegistering] = useState(false);
  const [picking, setPicking] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  // The tag to put in the deploy form of an app just made from a template
  const [deployTag, setDeployTag] = useState<string | null>(null);
  const [notice, setNotice] = useState<ReactNode>(null);
  const list = useQuery({
    queryKey: ['apps', prefix],
    queryFn: () => api<{ apps: App[] }>(`/api/dashboard/${prefix}/apps`),
    enabled: Boolean(prefix),
    refetchInterval: (q) => (q.state.data?.apps.some((a) => a.latest_deployment?.status === 'deploying') ? 10_000 : false),
  });
  const apps = list.data?.apps ?? [];
  const providers = useProviders(prefix);
  const register = (
    <div className="flex gap-2">
      <Button onClick={() => setPicking(true)} aria-label="Templates">
        <LayoutTemplate className="size-4" /> <span className="hidden sm:inline">Templates</span>
      </Button>
      <Button variant="primary" onClick={() => setRegistering(true)} aria-label="Register app">
        <Plus className="size-4" /> <span className="hidden sm:inline">Register app</span>
      </Button>
    </div>
  );
  const current = apps.find((a) => a.name === open);
  return (
    <>
      <PageHeader title="Hosting" description="Bots, agents, sites and services the org deploys." docs="modules/runpod-apps" action={register} />
      {providers.data?.some((p) => p.configured) ? null : <IntegrationHint keys={providers.data?.map((p) => p.integration) ?? ['runpod']} />}
      {notice ? <Notice onDismiss={() => setNotice(null)}>{notice}</Notice> : null}
      {list.error ? (
        <div className="mb-4">
          <ErrorNote error={list.error} />
        </div>
      ) : null}
      {list.isLoading ? (
        <Card>
          <SkeletonRows />
        </Card>
      ) : apps.length ? (
        <div className="grid gap-6">
          {KINDS.filter((k) => apps.some((a) => a.kind === k.kind)).map((k) => {
            const group = apps.filter((a) => a.kind === k.kind);
            return (
              <Card key={k.kind}>
                <CardHeader title={k.title} hint={`${group.length} ${group.length === 1 ? 'app' : 'apps'}`} />
                <AppTable apps={group} providers={providers.data} onOpen={setOpen} />
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState icon={Boxes} title="No apps" action={register}>
            Start from a template, or register a manifest.
          </EmptyState>
        </Card>
      )}

      <Dialog
        open={registering}
        onClose={() => setRegistering(false)}
        title="Register app"
        wide
      >
        <RegisterApp
          prefix={prefix}
          existing={apps.map((a) => a.name)}
          onDone={(name) => {
            setRegistering(false);
            if (name) setOpen(name);
          }}
        />
      </Dialog>

      <Dialog open={picking} onClose={() => setPicking(false)} title="Templates" wide>
        {picking ? (
          <TemplatePicker
            prefix={prefix}
            onDone={(name, tag) => {
              setPicking(false);
              if (name) {
                setDeployTag(tag ?? '');
                setOpen(name);
              }
            }}
          />
        ) : null}
      </Dialog>

      <Dialog
        open={open !== null}
        onClose={() => {
          setOpen(null);
          setDeployTag(null);
        }}
        title={open ?? ''}
        description={current ? (current.repo ? `From ${current.repo}` : 'Inline manifest') : undefined}
        wide
      >
        {open ? (
          <AppPanel
            key={open}
            prefix={prefix}
            name={open}
            deployTag={deployTag}
            onDeleted={(name, podId) => {
              setOpen(null);
              setNotice(
                podId ? (
                  <>
                    Deleted {name}. The pod <Mono className="text-fg">{podId}</Mono> still runs and bills; terminate it on {providerTitle(providers.data, current?.provider)}.
                  </>
                ) : (
                  `Deleted ${name}.`
                ),
              );
            }}
          />
        ) : null}
      </Dialog>
    </>
  );
}
