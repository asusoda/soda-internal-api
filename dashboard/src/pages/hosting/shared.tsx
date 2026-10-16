import { useQueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { cx } from '../../components/ui';

export const DEFAULT_MANIFEST_PATH = 'platform.app.yaml';
// No two dashes in a row: they separate the org and the app in a container name on This server
export const NAME_PATTERN = /^(?!.*--)[a-z0-9][a-z0-9-]{0,62}$/;
export const TAG_PATTERN = /^([A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|sha256:[a-f0-9]{64})$/;
export const REPO_PATTERN = /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/;

export const pretty = (value: unknown) => JSON.stringify(value, null, 2);

// officer:<discord id> reads as officer; tokens keep their name.
export const actorLabel = (actor: string | null) => (actor ? actor.replace(/^officer:\d+$/, 'officer') : '-');

export function JsonBlock({ value, className }: { value: unknown; className?: string }) {
  return (
    <pre
      className={cx(
        'max-h-80 overflow-auto rounded-lg border border-line bg-panel-2/50 p-3 font-mono text-xs leading-relaxed',
        className,
      )}
    >
      {pretty(value)}
    </pre>
  );
}

export function Label({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-2 flex min-h-8 items-center justify-between gap-2">
      <h3 className="font-mono text-[11px] tracking-wider text-muted uppercase">{children}</h3>
      {action}
    </div>
  );
}

export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 truncate text-sm">{children}</div>
    </div>
  );
}

export function useInvalidate(prefix: string) {
  const client = useQueryClient();
  return (name?: string) => {
    client.invalidateQueries({ queryKey: ['apps', prefix] });
    client.invalidateQueries({ queryKey: ['overview', prefix] });
    if (name) client.invalidateQueries({ queryKey: ['app', prefix, name] });
  };
}
