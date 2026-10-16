import { describe, expect, it } from 'vitest';
import { memberChanges } from './shared';

describe('memberChanges', () => {
  const member = { name: 'Ada', asu_id: null, academic_standing: 'Junior', major: null };

  it('sends no field that did not change', () => {
    expect(memberChanges(member, { name: 'Ada', asu_id: '', academic_standing: 'Junior', major: '' })).toEqual({});
  });

  it('sends a changed field, and null for a field made empty', () => {
    expect(memberChanges(member, { name: 'Ada', asu_id: '1234', academic_standing: '', major: '' })).toEqual({
      asu_id: '1234',
      academic_standing: null,
    });
  });

  it('treats whitespace as empty and ignores padding', () => {
    expect(memberChanges(member, { name: ' Ada ', asu_id: '', academic_standing: '   ', major: '' })).toEqual({
      academic_standing: null,
    });
  });
});
