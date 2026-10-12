import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, test, vi } from 'vitest';
import memberClient from '../components/utils/memberClient';
import MemberStorePage from './MemberStorePage';

vi.mock('../components/utils/memberClient', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  storeLoginUrl: (prefix: string) => `https://api.test/api/auth/store_login?org=${prefix}`,
}));

const get = vi.mocked(memberClient.get);
const store = { organization: { name: 'SoDA', prefix: 'soda', description: null }, products: [] };
const profile = {
  user: { id: 1, name: 'Alice', username: 'alice', email: 'alice@asu.edu', asu_id: null, discord_linked: true },
  current_organization: { id: 1, name: 'SoDA', prefix: 'soda', points: 50 },
  organizations: [],
  total_points_all_orgs: 50,
};

const renderStore = () =>
  render(
    <MemoryRouter initialEntries={['/store/soda']}>
      <Routes>
        <Route path="/store/:orgPrefix" element={<MemberStorePage />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  get.mockReset();
});

test('a member with a Discord session is signed in', async () => {
  get.mockImplementation(async (url: string) => {
    if (url.endsWith('/members/orders')) return { data: [] };
    if (url.endsWith('/member_profile')) return { data: profile };
    return { data: store };
  });
  renderStore();
  expect(await screen.findByText('Alice')).toBeInTheDocument();
  expect(await screen.findByText('50 points')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Login' })).toBeNull();
});

test('without a Discord session the store offers the Discord sign-in', async () => {
  get.mockImplementation(async (url: string) => {
    if (url.endsWith('/members/orders') || url.endsWith('/members/store')) throw new Error('401');
    return { data: store };
  });
  renderStore();
  expect(await screen.findByRole('button', { name: 'Login' })).toBeInTheDocument();
  expect(get).not.toHaveBeenCalledWith(expect.stringContaining('member_profile'));
});
