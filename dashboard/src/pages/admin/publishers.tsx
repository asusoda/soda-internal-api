import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Card, CardHeader, ErrorNote, Mono, SkeletonRows, Switch, Table, Td, Th, Tr } from '../../components/ui';
import { api, send } from '../../lib/api';
import type { OrganizationDetail } from '../../lib/types';

type Publisher = { org_id: number; prefix: string; source: 'env' | 'superadmin' };
type Publishers = { publishers: Publisher[] };

const KEY = ['superadmin-publishers'];

// Orgs that may write knowledge every org can search. KNOWLEDGE_PUBLISHERS in Doppler adds orgs the page cannot remove.
export function PublishersCard({ orgs }: { orgs: OrganizationDetail[] }) {
  const client = useQueryClient();
  const list = useQuery({ queryKey: KEY, queryFn: () => api<Publishers>('/api/superadmin/publishers') });
  const change = useMutation({
    mutationFn: ({ id, on }: { id: number; on: boolean }) => send<Publishers>(`/api/superadmin/publishers/${id}`, 'PUT', { publisher: on }),
    onSuccess: (body) => client.setQueryData(KEY, body),
  });
  const byId = new Map((list.data?.publishers ?? []).map((p) => [p.org_id, p]));
  return (
    <Card>
      <CardHeader title="Knowledge publishers" />
      {list.error ? (
        <div className="p-4">
          <ErrorNote error={list.error} />
        </div>
      ) : null}
      {change.error ? (
        <div className="p-4">
          <ErrorNote error={change.error} />
        </div>
      ) : null}
      {list.isLoading ? (
        <SkeletonRows rows={3} />
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Organization</Th>
              <Th className="text-right">Publisher</Th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((o) => {
              const p = byId.get(o.id);
              return (
                <Tr key={o.id}>
                  <Td className="w-full max-w-0">
                    <div className="truncate font-medium">{o.name}</div>
                    <Mono className="truncate">{o.prefix}</Mono>
                  </Td>
                  <Td>
                    <div className="flex items-center justify-end gap-2">
                      {p?.source === 'env' ? <Badge>Set in Doppler</Badge> : null}
                      <Switch
                        checked={Boolean(p)}
                        disabled={p?.source === 'env' || change.isPending}
                        onChange={(on) => change.mutate({ id: o.id, on })}
                        label={`${o.name} is a publisher`}
                      />
                    </div>
                  </Td>
                </Tr>
              );
            })}
          </tbody>
        </Table>
      )}
    </Card>
  );
}
