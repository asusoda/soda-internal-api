import { describe, expect, it } from 'vitest';
import { byUse, limitText, limitTone, share } from './limits';
import type { LimitRow } from './types';

const row = (over: Partial<LimitRow>): LimitRow => ({
  key: 'knowledge.sources',
  module: 'knowledge',
  label: 'Sources',
  unit: 'sources',
  window: null,
  default: 1000,
  paid_by: 'org',
  integrations: [],
  value: 1000,
  override: false,
  used: 0,
  enabled: true,
  ...over,
});

describe('limits', () => {
  it('writes a limit as text', () => {
    expect(limitText(1000, 'sources', null)).toBe('1,000 sources');
    expect(limitText(500, 'files', 'day')).toBe('500 files a day');
    expect(limitText(null, 'files', 'day')).toBe('No limit');
    expect(limitText(0, '', null)).toBe('0');
  });

  it('gives the share used and its tone', () => {
    expect(share(row({ used: 250 }))).toBe(0.25);
    expect(share(row({ value: null }))).toBeNull();
    expect(share(row({ value: 0, used: 0 }))).toBe(0);
    expect(share(row({ value: 0, used: 3 }))).toBe(1);
    expect(share(row({ used: 5000 }))).toBe(1);
    expect(limitTone(row({ used: 100 }))).toBe('ok');
    expect(limitTone(row({ used: 800 }))).toBe('warn');
    expect(limitTone(row({ used: 1000 }))).toBe('bad');
    expect(limitTone(row({ value: null }))).toBe('muted');
  });

  it('puts the most used first', () => {
    const rows = [row({ key: 'a', label: 'A', used: 10 }), row({ key: 'b', label: 'B', value: null }), row({ key: 'c', label: 'C', used: 900 })];
    expect(byUse(rows).map((r) => r.key)).toEqual(['c', 'a', 'b']);
  });
});
