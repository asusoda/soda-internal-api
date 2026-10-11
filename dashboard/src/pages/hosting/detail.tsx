import { useQuery } from '@tanstack/react-query';
import { GitBranch, History, Rocket, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Card, Dot, EmptyState, ErrorNote, Mono, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { api } from '../../lib/api';
import { deployTone, duration, podTone, timeAgo } from '../../lib/format';
import type { App, AppDetail, RunPodPod } from '../../lib/types';
import { providerTitle, useProviders } from './providers';
import { DeletePanel, DeployPanel, RollbackPanel } from './actions';
import { ManifestSection } from './manifest';
import { actorLabel, Fact, Label } from './shared';

function PodStatus({ prefix, app }: { prefix: string; app: App }) {
  const host = providerTitle(useProviders(prefix).data, app.provider);
  const pod = useQuery({
    queryKey: ['app-pod', prefix, app.name],
    queryFn: () => api<{ pod: RunPodPod | null }>(`/api/dashboard/${prefix}/apps/${app.name}/pod`),
    enabled: Boolean(app.pod_id),
    retry: false,
    refetchInterval: 30_000,
  });
  if (!app.pod_id) {
    return <p className="text-sm text-muted">No pod yet. The first deploy creates it.</p>;
  }
  if (pod.isLoading) return <SkeletonRows rows={1} />;
  if (pod.error) return <ErrorNote error={pod.error} />;
  const p = pod.data?.pod;
  if (!p) {
    return (
      <p className="text-sm text-muted">
        {host} has no pod <Mono>{app.pod_id}</Mono>. It was terminated; the next deploy creates a new one.
      </p>
    );
  }
  const status = p.desiredStatus ?? 'UNKNOWN';
  const machine = p.gpu?.displayName
    ? `${p.gpu.count && p.gpu.count > 1 ? `${p.gpu.count} x ` : ''}${p.gpu.displayName}`
    : (p.machine?.gpuDisplayName ?? p.machine?.cpuTypeId ?? null);
  const cost = p.costPerHr !== undefined && p.costPerHr !== null ? Number(p.costPerHr) : null;
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Fact label="Status">
        <span className="inline-flex items-center gap-2">
          <Dot tone={podTone(status)} />
          {status.toLowerCase()}
        </span>
      </Fact>
      <Fact label="Machine">{machine ?? '-'}</Fact>
      <Fact label="Cost">{cost !== null && Number.isFinite(cost) ? `$${cost.toFixed(2)}/hr` : '-'}</Fact>
      <Fact label="Pod ID">
        <Mono className="text-fg">{app.pod_id}</Mono>
      </Fact>
      {p.image ? (
        <div className="col-span-2 sm:col-span-4">
          <Fact label="Image">
            <Mono className="text-fg" title={p.image}>
              {p.image}
            </Mono>
          </Fact>
        </div>
      ) : null}
    </div>
  );
}

function Deployments({ app }: { app: AppDetail }) {
  if (!app.deployments.length) {
    return (
      <Card>
        <EmptyState icon={Rocket} title="No deployments">
          Deploy a tag here, or from CI with an apps:deploy token.
        </EmptyState>
      </Card>
    );
  }
  return (
    <Card>
      <Table>
        <thead>
          <tr>
            <Th>Tag</Th>
            <Th>Status</Th>
            <Th className="hidden md:table-cell">Actor</Th>
            <Th className="hidden sm:table-cell">Started</Th>
            <Th className="hidden lg:table-cell">Took</Th>
          </tr>
        </thead>
        <tbody>
          {app.deployments.map((d) => (
            <Tr key={d.id}>
              <Td className="w-full max-w-0 py-2.5">
                <div className="flex min-w-0 items-center gap-2">
                  <Mono className="truncate text-fg" title={d.tag}>
                    {d.tag}
                  </Mono>
                  {d.tag === app.current_tag && d.id === app.deployments.find((x) => x.tag === app.current_tag)?.id ? (
                    <Badge>current</Badge>
                  ) : null}
                </div>
                {d.error ? (
                  <div className="mt-0.5 truncate text-xs text-bad" title={d.error}>
                    {d.error}
                  </div>
                ) : d.manifest_ref ? (
                  <div className="mt-0.5 flex items-center gap-1 truncate text-xs text-muted">
                    <GitBranch className="size-3 shrink-0" />
                    <span className="truncate font-mono">{d.manifest_ref}</span>
                  </div>
                ) : null}
              </Td>
              <Td>
                <Badge tone={deployTone(d.status)}>{d.status}</Badge>
              </Td>
              <Td className="hidden max-w-40 md:table-cell">
                <Mono className="block truncate" title={d.actor ?? undefined}>
                  {actorLabel(d.actor)}
                </Mono>
              </Td>
              <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums sm:table-cell">{timeAgo(d.started_at)}</Td>
              <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums lg:table-cell">
                {d.started_at && d.finished_at ? duration(d.started_at, d.finished_at) : d.status === 'deploying' ? 'running' : '-'}
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

type Panel = 'deploy' | 'rollback' | 'delete' | null;

// deployTag, when set, opens the deploy form with that tag.
export function AppPanel({
  prefix,
  name,
  deployTag = null,
  onDeleted,
}: {
  prefix: string;
  name: string;
  deployTag?: string | null;
  onDeleted: (name: string, podId: string | null) => void;
}) {
  const [panel, setPanel] = useState<Panel>(deployTag === null ? null : 'deploy');
  const detail = useQuery({
    queryKey: ['app', prefix, name],
    queryFn: () => api<AppDetail>(`/api/dashboard/${prefix}/apps/${name}`),
    refetchInterval: (q) => (q.state.data?.deployments.some((d) => d.status === 'deploying') ? 10_000 : false),
  });
  if (detail.isLoading) return <SkeletonRows rows={5} />;
  if (detail.error || !detail.data) return <ErrorNote error={detail.error ?? 'No data'} />;
  const app = detail.data;
  const latest = app.latest_deployment;
  const close = () => setPanel(null);
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Fact label="Status">
          <Badge tone={deployTone(latest?.status ?? null)}>{latest?.status ?? 'not deployed'}</Badge>
        </Fact>
        <Fact label="Current tag">
          <Mono className="text-fg">{app.current_tag ?? '-'}</Mono>
        </Fact>
        <Fact label="Last deploy">
          <span className="text-muted tabular-nums">{timeAgo(latest?.started_at)}</span>
        </Fact>
        <Fact label="Source">
          {app.repo ? (
            <span className="inline-flex max-w-full items-center gap-1.5">
              <GitBranch className="size-3.5 shrink-0 text-muted" />
              <span className="truncate">{app.repo}</span>
            </span>
          ) : (
            <span className="text-muted">inline manifest</span>
          )}
        </Fact>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant={panel === 'deploy' ? 'primary' : 'secondary'} onClick={() => setPanel(panel === 'deploy' ? null : 'deploy')}>
          <Rocket className="size-4" /> Deploy
        </Button>
        <Button onClick={() => setPanel(panel === 'rollback' ? null : 'rollback')} title="Deploy the last healthy tag again">
          <History className="size-4" /> Roll back
        </Button>
        <Button variant="danger" className="sm:ml-auto" onClick={() => setPanel(panel === 'delete' ? null : 'delete')}>
          <Trash2 className="size-4" /> Delete
        </Button>
      </div>
      {panel === 'deploy' ? <DeployPanel prefix={prefix} app={app} initialTag={deployTag ?? ''} onDone={close} /> : null}
      {panel === 'rollback' ? <RollbackPanel prefix={prefix} app={app} onDone={close} /> : null}
      {panel === 'delete' ? <DeletePanel prefix={prefix} app={app} onDone={close} onDeleted={onDeleted} /> : null}

      <section>
        <Label>Pod</Label>
        <PodStatus prefix={prefix} app={app} />
      </section>

      <section>
        <Label>Deployments</Label>
        <Deployments app={app} />
      </section>

      <ManifestSection key={app.updated_at} prefix={prefix} app={app} />
    </div>
  );
}
