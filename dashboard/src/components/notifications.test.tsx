// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import { NotificationsBell } from './notifications';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function json(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

describe('NotificationsBell', () => {
  it('opens the panel outside the bell so the page cannot clip it', async () => {
    vi.stubGlobal('fetch', (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/organizations/')) {
        return json([{ id: 1, name: 'SoDA', prefix: 'soda', guild_id: '1', icon_url: null }]);
      }
      if (url.endsWith('/api/dashboard/soda/notifications')) {
        return json({
          open: 1,
          notifications: [
            {
              id: 'n1',
              module: 'feeds',
              subject: 'feed failed',
              message: 'The last run failed.',
              link: 'feeds',
              kind: 'problem',
              level: 'error',
              at: null,
              resolved_at: null,
              resolved_by: null,
            },
          ],
        });
      }
      return json({ error: 'missing' }, 404);
    });
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/soda']}>
          <Routes>
            <Route path="/:org" element={<NotificationsBell />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const button = await screen.findByRole('button', { name: /Notifications/ });
    await user.hover(button);
    expect((await screen.findByRole('tooltip')).textContent).toContain('Notifications');
    await user.click(button);

    const panel = await screen.findByRole('dialog', { name: 'Notifications' });
    expect(panel.textContent).toContain('feed failed');
    expect(document.body.contains(panel)).toBe(true);
    expect(button.closest('div.relative')?.contains(panel) ?? false).toBe(false);

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Notifications' })).toBeNull();
  });
});
