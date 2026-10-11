// How the dashboard shows a limit and what an org uses of it.

import { count, type Tone } from './format';
import type { LimitRow, LimitWindow, PaidBy } from './types';

// The share of a limit at which the dashboard marks it, as NEAR in modules/superadmin/service.py.
export const NEAR = 0.8;

// "a day" for a rate limit, "" for a count limit.
export function per(window: LimitWindow): string {
  return window ? `a ${window}` : '';
}

// A limit value as text, such as "1,000 sources a day" or "No limit".
export function limitText(value: number | null, unit: string, window: LimitWindow): string {
  if (value === null) return 'No limit';
  return [count(value), unit, per(window)].filter(Boolean).join(' ');
}

// What the org uses of the limit, from 0 to 1, or null when there is no limit.
export function share(row: Pick<LimitRow, 'used' | 'value'>): number | null {
  if (row.value === null) return null;
  if (row.value === 0) return row.used > 0 ? 1 : 0;
  return Math.min(row.used / row.value, 1);
}

export function limitTone(row: Pick<LimitRow, 'used' | 'value'>): Tone {
  const part = share(row);
  if (part === null) return 'muted';
  if (row.value !== null && row.used >= row.value) return 'bad';
  return part >= NEAR ? 'warn' : 'ok';
}

// The rows to show first: the most used share, then by label.
export function byUse(rows: LimitRow[]): LimitRow[] {
  return [...rows].sort((a, b) => (share(b) ?? -1) - (share(a) ?? -1) || a.label.localeCompare(b.label));
}

// How the dashboard names who pays.
export const PAID_BY: Record<PaidBy, { title: string; text: string }> = {
  org: { title: 'Your own', text: "Your org's own data and apps." },
  shared: { title: 'Shared', text: 'Made once by Platform for every org. Uses none of your limits.' },
  metered: { title: 'Shared, metered', text: 'A shared service your org uses. Counts against your limits as a rate.' },
};
