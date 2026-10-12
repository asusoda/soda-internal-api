// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ConfirmProvider, DeleteButton } from '../confirm';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('DeleteButton', () => {
  it('asks in a dialog before it deletes', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(
      <ConfirmProvider>
        <DeleteButton label="Delete item" question="Delete this item?" onDelete={onDelete} />
      </ConfirmProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Delete item' }));

    const dialog = screen.getByRole('alertdialog');
    expect(dialog.textContent).toContain('Delete this item?');
    expect(onDelete).not.toHaveBeenCalled();
    expect(window.confirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it('leaves the row when the officer cancels', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(
      <ConfirmProvider>
        <DeleteButton label="Delete item" question="Delete this item?" onDelete={onDelete} />
      </ConfirmProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Delete item' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });
});
