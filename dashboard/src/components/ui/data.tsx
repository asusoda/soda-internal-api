// Tables, badges and monospace text.
import { type ComponentProps, type ReactNode } from 'react';
import { type Tone } from '../../lib/format';
import { cx } from './cx';

const toneBadge: Record<Tone, string> = {
  ok: 'border-ok/25 bg-ok/10 text-ok',
  warn: 'border-warn/25 bg-warn/10 text-warn',
  bad: 'border-bad/25 bg-bad/10 text-bad',
  muted: 'border-line bg-panel-2 text-muted',
  active: 'border-info/25 bg-info/10 text-info',
};

const toneDot: Record<Tone, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  bad: 'bg-bad',
  muted: 'bg-muted/50',
  active: 'bg-info animate-pulse',
};

// Tables

export function Table({ className, ...props }: ComponentProps<'table'>) {
  return (
    <div className="overflow-x-auto">
      <table className={cx('w-full border-collapse text-left text-sm', className)} {...props} />
    </div>
  );
}

export function Th({ className, ...props }: ComponentProps<'th'>) {
  return (
    <th
      className={cx(
        'h-9 border-b border-line bg-panel-2/50 px-4 text-xs font-medium whitespace-nowrap text-muted',
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: ComponentProps<'td'>) {
  return <td className={cx('h-12 border-b border-line px-4 align-middle', className)} {...props} />;
}

export function Tr({ className, ...props }: ComponentProps<'tr'>) {
  return <tr className={cx('transition-colors hover:bg-panel-2/40 [&:last-child>td]:border-0', className)} {...props} />;
}

// Text and status

export function Mono({ className, ...props }: ComponentProps<'span'>) {
  return <span className={cx('font-mono text-xs text-muted', className)} {...props} />;
}

export function Code({ className, ...props }: ComponentProps<'code'>) {
  return (
    <code
      className={cx('rounded border border-line bg-panel-2 px-1.5 py-0.5 font-mono text-[11px] whitespace-nowrap', className)}
      {...props}
    />
  );
}

export function Dot({ tone }: { tone: Tone }) {
  return <span className={cx('inline-block size-2 shrink-0 rounded-full', toneDot[tone])} />;
}

export function Badge({
  tone = 'muted',
  children,
  className,
  ...props
}: { tone?: Tone; children: ReactNode } & Omit<ComponentProps<'span'>, 'children'>) {
  return (
    <span
      {...props}
      className={cx(
        'inline-flex h-5 shrink-0 items-center gap-1 rounded-md border px-1.5 text-xs font-medium whitespace-nowrap',
        toneBadge[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
