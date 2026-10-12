import { render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import App from './App';

// Orb draws with WebGL, and jsdom has no WebGL context. Replace it with an
// empty component so that the login page can render.
vi.mock('./components/ui/Orb', () => ({ default: () => null }));

test('renders the login page at the root route when signed out', async () => {
  render(<App />);
  expect(
    await screen.findByRole('heading', { name: /soda admin panel/i })
  ).toBeInTheDocument();
});
