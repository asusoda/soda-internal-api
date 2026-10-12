import { useMutation, useQuery } from '@tanstack/react-query';
import { CalendarClock, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useConfirm } from '../../components/confirm';
import { Badge, Button, Dialog, EmptyState, ErrorNote, Field, FormActions, Input, SkeletonRows } from '../../components/ui';
import { api, send } from '../../lib/api';
import { duration, localToIso, toLocalInput, when } from '../../lib/format';
import type { Pod, PodSession } from '../../lib/types';
import { podPath, useRefreshGodfather } from './shared';

const MAX_HOURS = 24;

// The next full hour and two hours after it, as datetime-local values.
function defaultWindow(): [string, string] {
  const start = new Date();
  start.setHours(start.getHours() + 1, 0, 0, 0);
  const stop = new Date(start.getTime() + 2 * 3_600_000);
  return [toLocalInput(start), toLocalInput(stop)];
}

function windowProblem(start: string, stop: string): string | null {
  if (!start || !stop) return 'Pick a start and a stop time.';
  const a = new Date(start).getTime();
  const b = new Date(stop).getTime();
  if (b <= a) return 'The stop time must be after the start time.';
  if (b - a > MAX_HOURS * 3_600_000) return `A session can be at most ${MAX_HOURS} hours long.`;
  if (b <= Date.now()) return 'The stop time is in the past.';
  return null;
}

function SessionState({ s }: { s: PodSession }) {
  if (s.finished) return <Badge>Done</Badge>;
  if (s.started) return <Badge tone="active">Running</Badge>;
  return <Badge tone="ok">Scheduled</Badge>;
}

function SessionRow({ prefix, pod, s }: { prefix: string; pod: Pod; s: PodSession }) {
  const refresh = useRefreshGodfather(prefix);
  const confirm = useConfirm();
  const remove = useMutation({
    mutationFn: () => send(`${podPath(prefix, pod.id)}/sessions/${s.id}`, 'DELETE'),
    onSuccess: refresh,
  });
  return (
    <li className="flex items-center gap-3 border-b border-line px-4 py-2.5 last:border-0">
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-medium">{s.title || 'Session'}</span>
          <SessionState s={s} />
        </div>
        <div className="mt-0.5 truncate text-xs text-muted tabular-nums">
          {when(s.start_at)} · {duration(s.start_at, s.stop_at)}
        </div>
        {remove.error ? <div className="mt-1 text-xs text-bad">{(remove.error as Error).message}</div> : null}
      </div>
      {s.finished ? null : (
        <Button
          variant="ghost"
          size="icon"
          className="hover:text-bad"
          aria-label={`Delete ${s.title || 'session'}`}
          title="Delete"
          disabled={remove.isPending}
          onClick={() => {
            const note = s.started ? ' The pod stops at the next schedule run.' : '';
            void confirm(`Delete ${s.title || 'this session'}?${note}`, 'Delete').then((yes) => {
              if (yes) remove.mutate();
            });
          }}
        >
          <Trash2 className="size-4" />
        </Button>
      )}
    </li>
  );
}

function SessionList({ title, prefix, pod, sessions }: { title: string; prefix: string; pod: Pod; sessions: PodSession[] }) {
  if (!sessions.length) return null;
  return (
    <section>
      <h3 className="mb-2 text-xs font-medium text-muted">{title}</h3>
      <ul className="rounded-lg border border-line">
        {sessions.map((s) => (
          <SessionRow key={s.id} prefix={prefix} pod={pod} s={s} />
        ))}
      </ul>
    </section>
  );
}

export function SessionsDialog({ prefix, pod, onClose }: { prefix: string; pod: Pod; onClose: () => void }) {
  const [initialStart, initialStop] = defaultWindow();
  const [title, setTitle] = useState('');
  const [start, setStart] = useState(initialStart);
  const [stop, setStop] = useState(initialStop);
  const refresh = useRefreshGodfather(prefix);
  const list = useQuery({
    queryKey: ['godfather', prefix, 'sessions', pod.id],
    queryFn: () => api<{ sessions: PodSession[] }>(`${podPath(prefix, pod.id)}/sessions`).then((b) => b.sessions),
  });
  const problem = windowProblem(start, stop);
  const add = useMutation({
    mutationFn: () =>
      send(`${podPath(prefix, pod.id)}/sessions`, 'POST', {
        title: title.trim() || undefined,
        start_at: localToIso(start),
        stop_at: localToIso(stop),
      }),
    onSuccess: () => {
      refresh();
      setTitle('');
    },
  });
  const sessions = list.data ?? [];
  const upcoming = sessions.filter((s) => !s.finished);
  const past = sessions.filter((s) => s.finished).reverse();
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Sessions on ${pod.name}`}
      description="The pod starts 10 minutes before a session and stops after it."
    >
      <div className="space-y-6">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!problem) add.mutate();
          }}
        >
          <Field label="Title" hint="Optional, such as the workshop name">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Intro to PyTorch" maxLength={200} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Starts">
              <Input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required />
            </Field>
            <Field label="Stops">
              <Input type="datetime-local" value={stop} onChange={(e) => setStop(e.target.value)} required />
            </Field>
          </div>
          <p className={problem ? 'text-xs text-bad' : 'text-xs text-muted'}>
            {problem ?? `Times are in ${zone}. ${duration(localToIso(start), localToIso(stop))} long, at most ${MAX_HOURS} hours.`}
          </p>
          <FormActions error={add.error}>
            <Button variant="primary" disabled={add.isPending || Boolean(problem)}>
              Add session
            </Button>
          </FormActions>
        </form>

        {list.isLoading ? (
          <div className="rounded-lg border border-line">
            <SkeletonRows rows={2} />
          </div>
        ) : list.error ? (
          <ErrorNote error={list.error} />
        ) : sessions.length ? (
          <div className="space-y-5">
            <SessionList title="Upcoming" prefix={prefix} pod={pod} sessions={upcoming} />
            <SessionList title="Past" prefix={prefix} pod={pod} sessions={past} />
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-line">
            <EmptyState icon={CalendarClock}>No sessions yet. A pod with no sessions is never started or stopped by the schedule.</EmptyState>
          </div>
        )}
      </div>
    </Dialog>
  );
}
