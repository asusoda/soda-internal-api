// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ComponentProps, type MouseEvent } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, NavLink } from 'react-router';
import { Badge } from './ui/data';
import { Tooltip } from './tooltip';

afterEach(cleanup);

describe('Tooltip', () => {
  it('ties the open tip to the control', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Tooltip label="Collapse sidebar" keys={['Ctrl', 'B']} side="bottom">
        <button type="button" onClick={onClick}>
          Collapse
        </button>
      </Tooltip>,
    );

    const button = screen.getByRole('button', { name: 'Collapse' });
    await user.hover(button);

    const tip = await screen.findByRole('tooltip');
    expect(tip.textContent).toContain('Collapse sidebar');
    expect(tip.textContent).toContain('Ctrl');
    expect(tip.textContent).toContain('B');
    expect(button.getAttribute('aria-describedby')).toBe(tip.id);

    await user.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('puts the trigger on a component child and keeps its click', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn((event: MouseEvent<HTMLAnchorElement>) => event.preventDefault());
    render(
      <Tooltip label="Home">
        <Mark href="/home" onClick={onClick}>
          Home
        </Mark>
      </Tooltip>,
    );

    const link = screen.getByRole('link', { name: 'Home' });
    expect(link.parentElement?.classList.contains('contents')).toBe(false);
    await user.hover(link);

    const tip = await screen.findByRole('tooltip');
    expect(link.getAttribute('aria-describedby')).toBe(tip.id);
    expect(link.hasAttribute('data-base-ui-tooltip-trigger')).toBe(true);

    await user.click(link);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('keeps a nav link class that depends on the route', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/home']}>
        <Tooltip label="Home">
          <NavLink to="/home" className={({ isActive }) => (isActive ? 'is-active' : 'is-idle')}>
            Home
          </NavLink>
        </Tooltip>
      </MemoryRouter>,
    );

    const link = screen.getByRole('link', { name: 'Home' });
    expect(link.className).toContain('is-active');
    await user.hover(link);
    const tip = await screen.findByRole('tooltip');
    expect(link.getAttribute('aria-describedby')).toBe(tip.id);
    expect(link.className).toContain('is-active');
  });

  it('describes a badge from the badge itself', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip label="Paid by the org">
        <Badge>1 page</Badge>
      </Tooltip>,
    );

    const badge = screen.getByText('1 page');
    expect(badge.parentElement?.classList.contains('contents')).toBe(false);
    await user.hover(badge);
    const tip = await screen.findByRole('tooltip');
    expect(badge.getAttribute('aria-describedby')).toBe(tip.id);
  });

  it('keeps the child description and adds the tip while it is open', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip label="More">
        <button type="button" aria-describedby="hint">
          Go
        </button>
      </Tooltip>,
    );

    const button = screen.getByRole('button', { name: 'Go' });
    expect(button.getAttribute('aria-describedby')).toBe('hint');

    await user.hover(button);
    const tip = await screen.findByRole('tooltip');
    expect(button.getAttribute('aria-describedby')).toBe(`hint ${tip.id}`);
  });

  it('gives a fragment a span the tip can name', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip label="Both">
        <>
          <span>One</span>
          <span>Two</span>
        </>
      </Tooltip>,
    );

    const one = screen.getByText('One');
    expect(one.parentElement?.tagName).toBe('SPAN');
    await user.hover(one);
    const tip = await screen.findByRole('tooltip');
    expect(one.parentElement?.getAttribute('aria-describedby')).toBe(tip.id);
  });

  it('keeps the type of an input', () => {
    render(
      <Tooltip label="Agree">
        <input type="checkbox" aria-label="Agree" />
      </Tooltip>,
    );

    expect(screen.getByRole('checkbox', { name: 'Agree' })).toBeTruthy();
  });

  it('runs the child ref cleanup when the control goes away', () => {
    const clean = vi.fn();
    const ref = vi.fn((_node: Element | null) => clean);
    const view = render(
      <Tooltip label="Go">
        <button type="button" ref={ref}>
          Go
        </button>
      </Tooltip>,
    );

    expect(ref.mock.calls[0]?.[0]).toBeInstanceOf(HTMLButtonElement);
    view.unmount();
    expect(clean).toHaveBeenCalledOnce();
    expect(ref.mock.calls.some((call) => call[0] === null)).toBe(false);
  });
});

function Mark(props: ComponentProps<'a'>) {
  return <a {...props} />;
}
