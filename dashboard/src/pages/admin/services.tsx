import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Container } from 'lucide-react';
import { Badge, Card, CardHeader, DocsLink, EmptyState, ErrorNote, Mono, Select, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { api, send } from '../../lib/api';
import { bytes } from '../../lib/format';
import type { ServerService, ServerServices } from '../../lib/types';

const KEY = ['superadmin-services'];
const OWNERS: Record<string, string> = { platform: 'Platform', infrastructure: 'Infrastructure' };

// The select value of an owner: auto (from labels), platform, infrastructure or org:<id>.
const ownerValue = (s: ServerService) => (!s.set ? 'auto' : s.owner === 'org' ? `org:${s.org?.id}` : (s.owner ?? 'auto'));
const ownerName = (s: ServerService) => (s.owner === 'org' ? (s.org?.name ?? 'Org') : s.owner ? OWNERS[s.owner] : 'Unassigned');

// Each container and host process on the server, from the host agent, and who owns it.
export function ServicesCard({ orgs }: { orgs: { id: number; name: string }[] }) {
  const client = useQueryClient();
  const list = useQuery({ queryKey: KEY, queryFn: () => api<ServerServices>('/api/superadmin/server/services'), refetchInterval: 30_000 });
  const owner = useMutation({
    mutationFn: ({ name, value }: { name: string; value: string }) =>
      send(`/api/superadmin/server/services/${encodeURIComponent(name)}`, 'PUT', {
        owner: value === 'auto' ? null : value.startsWith('org:') ? 'org' : value,
        organization_id: value.startsWith('org:') ? Number(value.slice(4)) : null,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
  const agent = list.data?.agent;
  const services = list.data?.services ?? [];
  return (
    <Card>
      <CardHeader
        title="Services"
        hint={agent ? (agent.stale ? undefined : `${services.length} on the server`) : undefined}
        action={
          <div className="flex items-center gap-2">
            {agent?.stale ? <Badge tone="warn">Agent stopped</Badge> : null}
            <DocsLink page="codebase/operations#host-agent" />
          </div>
        }
      />
      {list.error || owner.error ? (
        <div className="p-4">
          <ErrorNote error={list.error ?? owner.error} />
        </div>
      ) : null}
      {list.isLoading ? <SkeletonRows rows={3} /> : null}
      {list.data && !agent ? (
        <EmptyState icon={Container} title="No host agent">
          Install the host agent to list the containers and processes on the server.
        </EmptyState>
      ) : null}
      {services.length ? (
        <Table>
          <thead>
            <tr>
              <Th>Service</Th>
              <Th className="hidden md:table-cell">Memory</Th>
              <Th className="hidden sm:table-cell">State</Th>
              <Th>Owner</Th>
            </tr>
          </thead>
          <tbody>
            {services.map((s) => (
              <Tr key={s.name}>
                <Td className="w-full max-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{s.name}</span>
                    {s.kind === 'process' ? <Badge>process</Badge> : null}
                  </div>
                  <Mono className="block truncate">{s.domains.join(', ') || (s.ports.length ? `port ${s.ports.join(', ')}` : (s.project ?? '-'))}</Mono>
                </Td>
                <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums md:table-cell">
                  {s.memory_used != null ? bytes(s.memory_used) : '-'}
                  {s.memory_limit != null ? ` of ${bytes(s.memory_limit)}` : ''}
                </Td>
                <Td className="hidden sm:table-cell">
                  <Badge tone={s.state === 'running' ? 'ok' : 'warn'}>{s.state ?? 'unknown'}</Badge>
                </Td>
                <Td>
                  <Select
                    aria-label={`Owner of ${s.name}`}
                    className="w-36 min-w-36 sm:w-44"
                    value={ownerValue(s)}
                    disabled={owner.isPending}
                    onChange={(e) => owner.mutate({ name: s.name, value: e.target.value })}
                  >
                    <option value="auto">{s.set ? 'Auto' : s.owner ? `${ownerName(s)} (auto)` : 'Unassigned'}</option>
                    <option value="platform">Platform</option>
                    <option value="infrastructure">Infrastructure</option>
                    {orgs.map((o) => (
                      <option key={o.id} value={`org:${o.id}`}>
                        {o.name}
                      </option>
                    ))}
                  </Select>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      ) : null}
    </Card>
  );
}
