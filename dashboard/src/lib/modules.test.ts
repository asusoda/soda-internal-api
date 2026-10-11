import { describe, expect, it } from 'vitest';
import { matches } from './modules';
import type { CatalogModule } from './types';

const hosting: CatalogModule = {
  name: 'runpod',
  title: 'Hosting',
  description: "Deploys the org's own apps.",
  category: 'Infrastructure',
  switchable: false,
  enabled: true,
  ready: false,
  needs: [{ key: 'runpod', label: 'RunPod', kind: 'integration', optional: false, connected: false }],
  submodules: [{ name: 'asu', title: 'ASU', description: 'Campus pages' }],
  limits: [{ key: 'runpod.apps', label: 'Hosting apps', window: null, paid_by: 'org' }],
};

describe('matches', () => {
  it('matches every module when the search is empty', () => {
    expect(matches(hosting, '  ')).toBe(true);
  });

  it('matches the title, the category, a need and a submodule, with no case', () => {
    expect(matches(hosting, 'host')).toBe(true);
    expect(matches(hosting, 'INFRA')).toBe(true);
    expect(matches(hosting, 'runpod')).toBe(true);
    expect(matches(hosting, 'asu')).toBe(true);
  });

  it('does not match other text', () => {
    expect(matches(hosting, 'leetcode')).toBe(false);
  });
});
