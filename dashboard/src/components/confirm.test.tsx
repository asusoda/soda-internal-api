// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ConfirmProvider, DeleteButton, useConfirm } from './confirm';

afterEach(cleanup);

function AskInDialog() {
  const confirm = useConfirm();
  return (
    <dialog open>
      <button type="button" onClick={() => void confirm('Delete order #3?', 'Delete')}>
        Delete order
      </button>
    </dialog>
  );
}

describe('ConfirmProvider', () => {
  it('shows the question inside the dialog that is already open', async () => {
    const user = userEvent.setup();
    render(
      <ConfirmProvider>
        <AskInDialog />
      </ConfirmProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Delete order' }));

    const alert = await screen.findByRole('alertdialog');
    expect(alert.textContent).toContain('Delete order #3?');
    expect(document.querySelector('dialog')?.contains(alert)).toBe(true);
  });

  it('closes the question when the control that asked goes away', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    const page = (shown: boolean) => (
      <ConfirmProvider>{shown ? <DeleteButton label="Delete item" question="Delete this item?" onDelete={onDelete} /> : null}</ConfirmProvider>
    );
    const view = render(page(true));

    await user.click(screen.getByRole('button', { name: 'Delete item' }));
    expect(await screen.findByRole('alertdialog')).toBeTruthy();

    await act(async () => {
      view.rerender(page(false));
    });

    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(onDelete).not.toHaveBeenCalled();
  });
});
