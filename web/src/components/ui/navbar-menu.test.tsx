import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { Menu } from './navbar-menu';

test('the mobile menu lists the links and closes after a click', () => {
  const goToUsers = vi.fn();
  render(
    <Menu setActive={() => {}} mobileLinks={[{ name: 'Dashboard', onClick: vi.fn() }, { name: 'Manage Users', onClick: goToUsers }]}>
      <div>Org</div>
      <div>Center</div>
      <div>Right</div>
    </Menu>
  );
  expect(screen.queryByRole('button', { name: 'Manage Users' })).toBeNull();

  const toggles = screen.getAllByRole('button');
  fireEvent.click(toggles[toggles.length - 1]);
  expect(screen.getByRole('button', { name: 'Dashboard' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Manage Users' }));

  expect(goToUsers).toHaveBeenCalledOnce();
  expect(screen.queryByRole('button', { name: 'Manage Users' })).toBeNull();
});
