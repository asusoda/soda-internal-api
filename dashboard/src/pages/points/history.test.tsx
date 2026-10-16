// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { ConfirmProvider } from '../../components/confirm';
import type { PointsMember } from '../../lib/types';
import { HistoryDialog } from './history';

// jsdom has no modal dialogs. The stand-ins open and close the dialog element.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false;
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const member: PointsMember = {
  id: 1,
  uuid: 'u-1',
  name: 'Alice',
  username: 'alice',
  email: 'alice@asu.edu',
  asu_id: null,
  academic_standing: null,
  major: null,
  discord_linked: false,
  points: 15,
  joined_at: null,
  created_at: null,
};

const entry = (id: number, points: number) => ({
  id,
  points,
  event: 'GBM',
  awarded_by_officer: 'officer',
  timestamp: null,
  last_updated: null,
});

const history = { user: { id: 1, name: 'Alice', email: 'alice@asu.edu', username: 'alice' }, total_points: 15, points_history: [entry(11, 5), entry(12, 10)] };

describe('points history', () => {
  it('deletes the entry the officer clicks by its id, also when two entries share an event name', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'DELETE') return new Response(JSON.stringify({ message: 'Points deleted successfully' }), { status: 200 });
      if (url.endsWith('/points')) return new Response(JSON.stringify(history), { status: 200 });
      return new Response('{}', { status: 404 });
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ConfirmProvider>
          <HistoryDialog prefix="soda" member={member} onClose={() => {}} onEdit={() => {}} />
        </ConfirmProvider>
      </QueryClientProvider>,
    );

    const buttons = await screen.findAllByRole('button', { name: 'Delete the entry for GBM' });
    expect(buttons).toHaveLength(2);
    await user.click(buttons[1]);
    await user.click(await screen.findByRole('button', { name: 'Delete' }));

    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/api\/points\/soda\/entries\/12$/), expect.objectContaining({ method: 'DELETE' })),
    );
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('delete_points'))).toBe(false);
  });
});
