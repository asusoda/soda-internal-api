import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { expect, test } from 'vitest';
import { Menu } from './navbar-menu';

const menu = (
  <Menu
    setActive={() => {}}
    mobileLinks={[
      { name: 'Manage Users', to: '/soda/users' },
      { name: 'Store & Orders', to: '/store/soda', newTab: true },
    ]}
  >
    <div>Org</div>
    <div>Center</div>
    <div>Right</div>
  </Menu>
);

const renderMenu = () =>
  render(
    <MemoryRouter initialEntries={['/soda/dashboard']}>
      <Routes>
        <Route path="/soda/dashboard" element={menu} />
        <Route path="/soda/users" element={<p>Users page</p>} />
      </Routes>
    </MemoryRouter>
  );

const openMenu = () => {
  const toggles = screen.getAllByRole('button');
  fireEvent.click(toggles[toggles.length - 1]);
};

test('the mobile menu lists links that open their pages', () => {
  renderMenu();
  expect(screen.queryByRole('link', { name: 'Manage Users' })).toBeNull();

  openMenu();
  const users = screen.getByRole('link', { name: 'Manage Users' });
  expect(users.getAttribute('href')).toBe('/soda/users');
  expect(users.closest('div')?.className).toContain('overflow-y-auto');
  fireEvent.click(users);

  expect(screen.getByText('Users page')).toBeInTheDocument();
});

test('the store link opens in a new tab', () => {
  renderMenu();
  openMenu();
  const store = screen.getByRole('link', { name: 'Store & Orders' });
  expect(store.getAttribute('href')).toBe('/store/soda');
  expect(store.getAttribute('target')).toBe('_blank');
});
