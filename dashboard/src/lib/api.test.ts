import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import { tokens } from './auth';

function storage(): Storage {
  const items = new Map<string, string>();
  return {
    get length() {
      return items.size;
    },
    clear: () => items.clear(),
    getItem: (key) => items.get(key) ?? null,
    key: (index) => [...items.keys()][index] ?? null,
    removeItem: (key) => void items.delete(key),
    setItem: (key, value) => void items.set(key, value),
  };
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('api', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', storage());
    tokens.set('old-access', 'refresh-token');
  });
  afterEach(() => vi.unstubAllGlobals());

  it('refreshes the access token once for requests that fail together', async () => {
    const fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/auth/refresh')) return json(200, { access_token: 'new-access' });
      const auth = new Headers(init?.headers).get('Authorization');
      return auth === 'Bearer new-access' ? json(200, { ok: true }) : json(401, { message: 'Token is invalid!' });
    });
    vi.stubGlobal('fetch', fetch);
    const answers = await Promise.all([api('/api/a'), api('/api/b'), api('/api/c')]);
    expect(answers).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(fetch.mock.calls.filter(([url]) => url.endsWith('/api/auth/refresh'))).toHaveLength(1);
  });

  it('refreshes on the 403 that officer routes send for an expired token', async () => {
    const fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/auth/refresh')) return json(200, { access_token: 'new-access' });
      const auth = new Headers(init?.headers).get('Authorization');
      return auth === 'Bearer new-access' ? json(200, { ok: true }) : json(403, { message: 'Token is expired!' });
    });
    vi.stubGlobal('fetch', fetch);
    await expect(api('/api/points/soda/users')).resolves.toEqual({ ok: true });
  });

  it('does not refresh on other 403 answers', async () => {
    const fetch = vi.fn(async () => json(403, { message: 'You are not an officer of this organization' }));
    vi.stubGlobal('fetch', fetch);
    await expect(api('/api/points/soda/users')).rejects.toMatchObject({ status: 403 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('clears the tokens when the refresh token is refused', async () => {
    const fetch = vi.fn(async (url: string) =>
      url.endsWith('/api/auth/refresh') ? json(401, { error: 'Invalid refresh token' }) : json(401, { message: 'Token is invalid!' }),
    );
    vi.stubGlobal('fetch', fetch);
    await expect(api('/api/points/soda/users')).rejects.toMatchObject({ status: 401 });
    expect(tokens.access()).toBeNull();
    expect(tokens.refresh()).toBeNull();
  });
});
