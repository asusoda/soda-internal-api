// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemberStorePage } from './index';
import { MemberLoginPage } from './login';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const store = { organization: { name: 'SoDA', prefix: 'soda', description: null }, products: [] };
const profile = { user: { name: 'Alice', email: 'alice@asu.edu' }, current_organization: { points: 50 } };

function renderAt(path: string, element: ReactNode, route: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// Answers the store routes as the API does, with the Discord session in signedIn.
function stubApi(state: { signedIn: boolean }) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (url.endsWith('/api/auth/logout') && init?.method === 'POST') {
      state.signedIn = false;
      return json({ message: 'Logged out successfully' });
    }
    if (url.endsWith('/members/orders')) return state.signedIn ? json([]) : json({ error: 'Discord authentication required' }, 401);
    if (url.endsWith('/member_profile')) return state.signedIn ? json(profile) : json({ error: 'Member not logged in' }, 401);
    if (url.endsWith('/members/store')) return state.signedIn ? json(store) : json({ error: 'Discord authentication required' }, 401);
    return json(store);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('member store sign-in', () => {
  it('signs in with Discord through the API', () => {
    renderAt('/store/soda/login', <MemberLoginPage />, '/store/:prefix/login');
    const link = screen.getByRole('link', { name: 'Sign in with Discord' });
    expect(link.getAttribute('href')).toMatch(/\/api\/auth\/store_login\?org=soda&client=dashboard$/);
  });

  it('shows a signed-in member and signs them out', async () => {
    const user = userEvent.setup();
    const fetchMock = stubApi({ signedIn: true });
    renderAt('/store/soda', <MemberStorePage />, '/store/:prefix');

    expect(await screen.findByText('Alice')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Sign out' }));

    expect(await screen.findByRole('link', { name: 'Member sign-in' })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/api\/auth\/logout$/), expect.objectContaining({ method: 'POST', credentials: 'include' }));
  });

  it('shows the error of a failed sign-in', async () => {
    stubApi({ signedIn: false });
    renderAt('/store/soda?error=Sign-in%20expired', <MemberStorePage />, '/store/:prefix');
    expect((await screen.findByRole('alert')).textContent).toBe('Sign-in expired');
  });
});
