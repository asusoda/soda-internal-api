import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import { Button, ErrorNote, Spinner } from './ui';

// The last lines of a service's output, from a route that answers {"logs": "..."}.
export function LogsView({ url }: { url: string }) {
  const logs = useQuery({ queryKey: ['logs', url], queryFn: () => api<{ logs: string }>(url), retry: false });
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-muted">Last 200 lines</span>
        <Button variant="ghost" className="h-7 px-2 text-xs" disabled={logs.isFetching} onClick={() => logs.refetch()}>
          {logs.isFetching ? <Spinner className="size-3.5" /> : <RefreshCw className="size-3.5" />} Refresh
        </Button>
      </div>
      {logs.error ? <ErrorNote error={logs.error} /> : null}
      <pre className="max-h-80 overflow-auto rounded-md border border-line bg-panel-2/60 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
        {logs.isLoading ? 'Loading...' : logs.data?.logs || 'No output yet.'}
      </pre>
    </div>
  );
}
