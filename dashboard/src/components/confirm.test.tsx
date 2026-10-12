// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { ConfirmProvider, useConfirm } from './confirm';

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
});
