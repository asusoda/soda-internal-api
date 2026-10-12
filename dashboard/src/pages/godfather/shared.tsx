import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MoreHorizontal } from 'lucide-react';
import { type ComponentType, type ReactNode, useId, useRef } from 'react';
import { Button, cx } from '../../components/ui';
import { ApiError, api, send } from '../../lib/api';
import type { Tone } from '../../lib/format';
import type { Pod } from '../../lib/types';

export const godfatherPath = (prefix: string) => `/api/compute/${prefix}`;
export const podPath = (prefix: string, podId: string) => `${godfatherPath(prefix)}/pods/${encodeURIComponent(podId)}`;
export const podsKey = (prefix: string) => ['godfather', prefix, 'pods'];

export function usePods(prefix: string) {
  return useQuery({
    queryKey: podsKey(prefix),
    queryFn: () => api<{ pods: Pod[] }>(`${godfatherPath(prefix)}/pods`).then((body) => body.pods),
    enabled: Boolean(prefix),
    refetchInterval: 15_000,
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
  });
}

// Refetches the pod list and the overview after a change.
export function useRefreshGodfather(prefix: string) {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: ['godfather', prefix] });
    client.invalidateQueries({ queryKey: ['overview', prefix] });
  };
}

export type PodAction = 'start' | 'stop' | 'restart' | 'terminate';

export function usePodAction(prefix: string, podId: string) {
  const refresh = useRefreshGodfather(prefix);
  return useMutation({
    mutationFn: (action: PodAction) => send(`${podPath(prefix, podId)}/action`, 'POST', { action }),
    onSuccess: refresh,
  });
}

// True when the pod list failed because the org has no key for a pod's provider.
export function isMissingKey(error: unknown): boolean {
  return error instanceof ApiError && error.status === 400 && error.message.includes('runpod_api_key');
}

export function statusTone(status: string | null): Tone {
  if (status === 'RUNNING') return 'ok';
  if (status === 'EXITED' || status === 'STOPPED') return 'muted';
  if (status === 'GONE' || status === 'TERMINATED' || status === 'FAILED') return 'bad';
  if (status === 'UNKNOWN' || !status) return 'warn';
  return 'active';
}

export function statusLabel(status: string | null): string {
  if (!status) return 'Unknown';
  if (status === 'EXITED') return 'Stopped';
  return status.charAt(0) + status.slice(1).toLowerCase();
}

const text = (value: unknown) => (typeof value === 'string' && value ? value : null);

// A short name for the hardware the provider placed the pod on.
export function machineLabel(machine: Record<string, unknown> | null): string | null {
  if (!machine) return null;
  const gpuType = machine.gpuType as Record<string, unknown> | undefined;
  return (
    text(gpuType?.displayName) ??
    text(machine.gpuDisplayName) ??
    text(machine.gpuTypeId) ??
    text(machine.cpuTypeId) ??
    text(machine.location) ??
    text(machine.dataCenterId)
  );
}

export function costLabel(cost: number | string | null): string | null {
  const value = typeof cost === 'string' ? Number(cost) : cost;
  if (value === null || !Number.isFinite(value)) return null;
  return `$${value.toFixed(value > 0 && value < 0.1 ? 3 : 2)}/hr`;
}

export const isDiscordId = (value: string) => /^\d{5,25}$/.test(value);

// A dropdown of row actions on the popover API, so table and card overflow do not clip it.
export function RowMenu({ label, children }: { label: string; children: (close: () => void) => ReactNode }) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const close = () => menu.current?.hidePopover();
  return (
    <>
      <Button ref={button} variant="ghost" size="icon" aria-label={label} title="More" popoverTarget={id}>
        <MoreHorizontal className="size-4" />
      </Button>
      <div
        ref={menu}
        id={id}
        popover="auto"
        onToggle={(e) => {
          if (e.newState !== 'open' || !button.current || !menu.current) return;
          const rect = button.current.getBoundingClientRect();
          const below = window.innerHeight - rect.bottom > menu.current.offsetHeight + 8;
          menu.current.style.top = below ? `${rect.bottom + 4}px` : `${rect.top - menu.current.offsetHeight - 4}px`;
          menu.current.style.left = `${Math.max(8, rect.right - menu.current.offsetWidth)}px`;
          window.addEventListener('scroll', close, { once: true, capture: true });
          menu.current.querySelector('button')?.focus();
        }}
        className="m-0 min-w-44 rounded-lg border border-line bg-panel p-1 text-fg shadow-lg"
      >
        {children(close)}
      </div>
    </>
  );
}

export function MenuItem({
  icon: Icon,
  danger,
  className,
  children,
  onClick,
  disabled,
}: {
  icon: ComponentType<{ className?: string }>;
  danger?: boolean;
  className?: string;
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cx(
        'flex h-8 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-left text-sm transition-colors outline-none focus-visible:bg-panel-2 disabled:pointer-events-none disabled:opacity-50',
        danger ? 'text-bad hover:bg-bad/10 focus-visible:bg-bad/10' : 'hover:bg-panel-2',
        className,
      )}
    >
      <Icon className="size-4 shrink-0 opacity-80" />
      {children}
    </button>
  );
}

export function MenuSeparator() {
  return <div role="separator" className="my-1 h-px bg-line" />;
}

export type GodfatherSettings = { pod_image: string | null; deployment_pod_image: string };

export function useGodfatherSettings(prefix: string) {
  return useQuery({
    queryKey: ['godfather', prefix, 'settings'],
    queryFn: () => api<{ settings: GodfatherSettings }>(`${godfatherPath(prefix)}/settings`).then((body) => body.settings),
    enabled: Boolean(prefix),
  });
}
