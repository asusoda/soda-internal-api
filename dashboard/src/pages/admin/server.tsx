import { useQuery } from '@tanstack/react-query';
import { Activity, Bot, Cpu, Database, HardDrive, MemoryStick } from 'lucide-react';
import { Badge, Card, CardHeader, ErrorNote, SkeletonRows, Stat, StatGrid } from '../../components/ui';
import { api } from '../../lib/api';
import { bytes, elapsed } from '../../lib/format';
import type { ServerHealth } from '../../lib/types';

const used = (part: number | null | undefined, total: number | null | undefined) =>
  part != null && total ? `${Math.round((part / total) * 100)}%` : '-';

// The server's load, memory and disk, the database, the API container, the bot and the job queue.
export function ServerCard() {
  const server = useQuery({
    queryKey: ['superadmin-server'],
    queryFn: () => api<ServerHealth>('/api/superadmin/server'),
    refetchInterval: 30_000,
  });
  const s = server.data;
  const memoryUsed = s?.memory ? s.memory.total - s.memory.available : null;
  const queue = s?.jobs.queue;
  return (
    <Card>
      <CardHeader
        title="Server"
        hint="The host, and the API container."
      />
      {server.error ? (
        <div className="p-4">
          <ErrorNote error={server.error} />
        </div>
      ) : null}
      {server.isLoading ? <SkeletonRows rows={2} /> : null}
      {s ? (
        <div className="space-y-4 p-4">
          <StatGrid>
            <Stat
              label="Load (1 min)"
              value={s.load ? s.load[0].toFixed(2) : '-'}
              sub={s.cpus ? `${s.cpus} CPUs, ${s.load ? s.load.map((l) => l.toFixed(2)).join(' / ') : '-'}` : undefined}
              icon={<Cpu className="size-4" />}
            />
            <Stat
              label="Memory"
              value={used(memoryUsed, s.memory?.total)}
              sub={s.memory ? `${bytes(memoryUsed ?? 0)} of ${bytes(s.memory.total)}` : undefined}
              icon={<MemoryStick className="size-4" />}
            />
            <Stat
              label="Disk"
              value={used(s.disk?.used, s.disk?.total)}
              sub={s.disk ? `${bytes(s.disk.free)} free of ${bytes(s.disk.total)}` : undefined}
              icon={<HardDrive className="size-4" />}
            />
            <Stat
              label="Database"
              value={s.database_bytes != null ? bytes(s.database_bytes) : '-'}
              sub={s.database}
              icon={<Database className="size-4" />}
            />
          </StatGrid>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            <div className="flex items-center justify-between gap-3">
              <dt className="flex items-center gap-2 text-muted">
                <Activity className="size-4" />
                API container
              </dt>
              <dd className="text-right tabular-nums">
                {s.container.memory_used != null ? bytes(s.container.memory_used) : '-'}
                {s.container.memory_limit != null ? ` of ${bytes(s.container.memory_limit)}` : ', no memory cap'}
                {s.container.cpu_limit != null ? `, ${s.container.cpu_limit} CPUs` : ''}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">Up</dt>
              <dd className="text-right tabular-nums">
                API {elapsed(s.container.process_uptime_seconds)}
                {s.uptime_seconds != null ? `, server ${elapsed(s.uptime_seconds)}` : ''}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="flex items-center gap-2 text-muted">
                <Bot className="size-4" />
                Discord bot
              </dt>
              <dd>
                {s.bot_ready === null ? (
                  <Badge>Not set up</Badge>
                ) : (
                  <Badge tone={s.bot_ready ? 'ok' : 'bad'}>{s.bot_ready ? 'Answers' : 'Not available'}</Badge>
                )}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">Jobs</dt>
              <dd className="text-right tabular-nums">
                {queue
                  ? Object.entries(queue)
                      .map(([status, n]) => `${n} ${status}`)
                      .join(', ') || 'Queue empty'
                  : `${s.jobs.backend}, in each process`}
              </dd>
            </div>
          </dl>
        </div>
      ) : null}
    </Card>
  );
}
