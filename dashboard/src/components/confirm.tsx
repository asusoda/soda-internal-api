// Asks the officer to confirm. The promise resolves true when the officer accepts.
import { AlertDialog } from '@base-ui/react/alert-dialog';
import { Trash2 } from 'lucide-react';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { cx } from './ui/cx';
import { Button } from './ui/controls';

type Ask = (question: string, action?: string) => Promise<boolean>;

type Pending = { id: number; question: string; action: string; resolve: (yes: boolean) => void };

type ConfirmApi = {
  ask: (question: string, action?: string) => { id: number; promise: Promise<boolean> };
  cancel: (id: number) => void;
};

const ConfirmContext = createContext<ConfirmApi | null>(null);

// The open native dialog, so the confirm panel is in its top layer and not hidden behind it.
function topDialog(): HTMLElement | null {
  const dialogs = document.querySelectorAll('dialog[open]');
  const top = dialogs[dialogs.length - 1];
  return top instanceof HTMLElement ? top : null;
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [layer, setLayer] = useState<HTMLElement | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  const nextId = useRef(0);
  const settle = (yes: boolean) => {
    const current = pendingRef.current;
    if (!current) return;
    pendingRef.current = null;
    current.resolve(yes);
    setPending(null);
  };
  const settleRef = useRef(settle);
  settleRef.current = settle;

  const ask = useCallback<ConfirmApi['ask']>((question, action = 'Confirm') => {
    const previous = pendingRef.current;
    if (previous) {
      pendingRef.current = null;
      previous.resolve(false);
    }
    let resolvePromise: (yes: boolean) => void = () => {};
    const promise = new Promise<boolean>((resolve) => {
      resolvePromise = resolve;
    });
    const next = { id: ++nextId.current, question, action, resolve: resolvePromise };
    pendingRef.current = next;
    setLayer(topDialog());
    setPending(next);
    return { id: next.id, promise };
  }, []);

  const cancel = useCallback((id: number) => {
    if (pendingRef.current?.id === id) settleRef.current(false);
  }, []);

  const api = useMemo(() => ({ ask, cancel }), [ask, cancel]);

  return (
    <ConfirmContext.Provider value={api}>
      {children}
      <AlertDialog.Root
        open={pending !== null}
        onOpenChange={(open) => {
          if (!open) settle(false);
        }}
      >
        <AlertDialog.Portal container={layer ?? undefined}>
          <AlertDialog.Backdrop className="fixed inset-0 bg-black/45 backdrop-blur-[2px] transition-opacity duration-150 data-ending-style:opacity-0 data-starting-style:opacity-0" />
          <AlertDialog.Viewport className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <AlertDialog.Popup className="w-full max-w-md rounded-xl border border-line bg-panel p-5 text-fg shadow-2xl outline-none transition duration-150 data-ending-style:opacity-0 data-starting-style:scale-[0.98] data-starting-style:opacity-0">
              <AlertDialog.Title className="text-sm font-medium text-pretty">{pending?.question}</AlertDialog.Title>
              <div className="mt-4 flex justify-end gap-2">
                <AlertDialog.Close render={<Button type="button" variant="ghost" />}>Cancel</AlertDialog.Close>
                <Button type="button" variant="danger" onClick={() => settle(true)}>
                  {pending?.action ?? 'Confirm'}
                </Button>
              </div>
            </AlertDialog.Popup>
          </AlertDialog.Viewport>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): Ask {
  const api = useContext(ConfirmContext);
  if (!api) throw new Error('ConfirmProvider is missing.');
  const owned = useRef<number | null>(null);
  useEffect(
    () => () => {
      if (owned.current != null) api.cancel(owned.current);
    },
    [api],
  );
  return useCallback(
    (question, action) => {
      const { id, promise } = api.ask(question, action);
      owned.current = id;
      return promise.finally(() => {
        if (owned.current === id) owned.current = null;
      });
    },
    [api],
  );
}

// An icon button that deletes after the officer confirms the question.
export function DeleteButton({
  label,
  question,
  onDelete,
  title = 'Delete',
  disabled,
  className,
}: {
  label: string;
  question: string;
  onDelete: () => void;
  title?: string;
  disabled?: boolean;
  className?: string;
}) {
  const confirm = useConfirm();
  return (
    <Button
      variant="ghost"
      size="icon"
      title={title}
      aria-label={label}
      className={cx('hover:text-bad', className)}
      disabled={disabled}
      onClick={() => {
        void confirm(question, 'Delete').then((yes) => {
          if (yes) onDelete();
        });
      }}
    >
      <Trash2 className="size-4" />
    </Button>
  );
}
