import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { expect, test, vi } from 'vitest';
import apiClient from '../components/utils/axios';
import UserPage from './UserPage';

vi.mock('../components/utils/axios', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }));
vi.mock('../components/auth/AuthContext', () => ({ useAuth: () => ({ currentOrg: { id: 1, prefix: 'soda' } }) }));
vi.mock('../hooks/userAuth', () => ({ default: () => ({}) }));
vi.mock('../components/shared/OrganizationNavbar', () => ({ default: ({ children }: { children: ReactNode }) => children }));

test('a member loaded for update does not fill the create form', async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: {
      user: { id: 1, name: 'Alice', email: 'alice@asu.edu', username: 'alice', asu_id: '1200000001', academic_standing: 'Junior', major: 'CS' },
      organization: { name: 'SoDA', prefix: 'soda' },
      total_points: 50,
      points_history: [],
    },
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: { message: 'User created' } });
  render(<UserPage />);

  fireEvent.change(screen.getByLabelText('User Email to Find/Update'), { target: { value: 'alice@asu.edu' } });
  fireEvent.click(screen.getByRole('button', { name: 'Find User' }));
  expect(await screen.findByDisplayValue('1200000001')).toBeInTheDocument();
  expect((screen.getByLabelText('ASU ID (Optional)') as HTMLInputElement).value).toBe('');

  fireEvent.change(screen.getByLabelText('User Email'), { target: { value: 'bob@asu.edu' } });
  fireEvent.change(document.getElementById('createName')!, { target: { value: 'Bob' } });
  fireEvent.submit(screen.getByLabelText('User Email').closest('form')!);
  expect(apiClient.post).toHaveBeenCalledWith('/api/points/soda/users', {
    email: 'bob@asu.edu',
    name: 'Bob',
    asu_id: undefined,
    academic_standing: undefined,
    major: undefined,
  });
});
