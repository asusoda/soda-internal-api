// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { Tooltip } from './tooltip';

afterEach(cleanup);

describe('Tooltip', () => {
  it('ties the open tip to the control', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip label="Collapse sidebar" keys={['Ctrl', 'B']} side="bottom">
        <button type="button">Collapse</button>
      </Tooltip>,
    );

    await user.hover(screen.getByRole('button', { name: 'Collapse' }));

    const tip = await screen.findByRole('tooltip');
    expect(tip.textContent).toContain('Collapse sidebar');
    expect(tip.textContent).toContain('Ctrl');
    expect(tip.textContent).toContain('B');
    expect(screen.getByRole('button', { name: 'Collapse' }).getAttribute('aria-describedby')).toBe(tip.id);
  });
});
