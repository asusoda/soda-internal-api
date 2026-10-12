import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, RotateCw, Square } from 'lucide-react';
import { Button, ErrorNote, Spinner } from '../../components/ui';
import { api, send } from '../../lib/api';
import type { App, RunPodPod, ServerPod } from '../../lib/types';

type Action = 'start' | 'stop' | 'restart';

// Restart, and Stop or Start, for a deployed app. The pod query is the one the panel already reads.
export function RunControls({ prefix, app }: { prefix: string; app: App }) {
  const client = useQueryClient();
  const key = ['app-pod', prefix, app.name];
  const pod = useQuery({
    queryKey: key,
    queryFn: () => api<{ pod: RunPodPod | ServerPod | null }>(`/api/dashboard/${prefix}/apps/${app.name}/pod`),
    enabled: Boolean(app.pod_id),
    retry: false,
  });
  const act = useMutation({
    mutationFn: (action: Action) => send(`/api/dashboard/${prefix}/apps/${app.name}/action`, 'POST', { action }),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  if (!app.pod_id) return null;
  const found = pod.data?.pod as (RunPodPod & ServerPod) | null | undefined;
  const state = String(found?.state ?? found?.desiredStatus ?? '').toLowerCase();
  const running = state === 'running';
  const busy = act.isPending ? act.variables : null;
  return (
    <>
      <Button onClick={() => act.mutate('restart')} disabled={act.isPending} title="Stop and start the app">
        {busy === 'restart' ? <Spinner className="size-3.5" /> : <RotateCw className="size-4" />} Restart
      </Button>
      <Button onClick={() => act.mutate(running ? 'stop' : 'start')} disabled={act.isPending || !found}>
        {busy === 'stop' || busy === 'start' ? <Spinner className="size-3.5" /> : running ? <Square className="size-4" /> : <Play className="size-4" />}{' '}
        {running ? 'Stop' : 'Start'}
      </Button>
      {act.error ? (
        <div className="basis-full">
          <ErrorNote error={act.error} />
        </div>
      ) : null}
    </>
  );
}
