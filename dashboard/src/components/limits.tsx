import { Badge, cx, Mono, Table, Td, Th, Tr } from './ui';
import { count } from '../lib/format';
import { limitText, limitTone, per, share } from '../lib/limits';
import type { LimitRow } from '../lib/types';

const barTone = { ok: 'bg-ok', warn: 'bg-warn', bad: 'bg-bad', muted: 'bg-line', active: 'bg-info' } as const;

// A bar of what the org uses of one limit, with the numbers under it.
export function UseBar({ row, className }: { row: LimitRow; className?: string }) {
  const part = share(row);
  const tone = limitTone(row);
  return (
    <div className={cx('min-w-0', className)}>
      <div className="h-1.5 overflow-hidden rounded-full bg-panel-2" aria-hidden>
        <div className={cx('h-full rounded-full', barTone[tone])} style={{ width: `${Math.round((part ?? 0) * 100)}%` }} />
      </div>
      <div className="mt-1 text-xs text-muted tabular-nums">
        {row.value === null
          ? `${[count(row.used), row.unit, per(row.window)].filter(Boolean).join(' ')}, no limit`
          : `${count(row.used)} of ${limitText(row.value, row.unit, row.window)}`}
      </div>
    </div>
  );
}

// Each limit of an org and what the org uses of it.
export function LimitTable({ rows }: { rows: LimitRow[] }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Limit</Th>
          <Th className="w-1/2">Use</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <Tr key={row.key}>
            <Td className="max-w-0">
              <div className="truncate font-medium">{row.label}</div>
              <div className="flex items-center gap-2">
                <Mono className="truncate">{row.key}</Mono>
                {row.override ? <Badge tone="active">Set for this org</Badge> : null}
              </div>
            </Td>
            <Td>
              <UseBar row={row} />
            </Td>
          </Tr>
        ))}
      </tbody>
    </Table>
  );
}
