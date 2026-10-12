import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useConfirm } from '../../components/confirm';
import { Button, Dialog, Field, FormActions, Select, Table, Td, Textarea, Th, Tr } from '../../components/ui';
import { send } from '../../lib/api';
import { compact, when } from '../../lib/format';
import type { Order, Product } from '../../lib/types';

// The statuses update_order_status accepts. A checkout order starts as completed, which officers cannot set.
const STATUSES = ['pending', 'processing', 'shipped', 'delivered', 'cancelled'];

// Statuses with nothing left for an officer to do.
const CLOSED = new Set(['delivered', 'cancelled']);

export function OrderDialog({
  prefix,
  order,
  products,
  onClose,
}: {
  prefix: string;
  order: Order | null;
  products: Map<number, Product>;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={Boolean(order)}
      onClose={onClose}
      title={order ? `Order #${order.id}` : 'Order'}
      description={order ? `${order.user_name}${order.user_email ? `, ${order.user_email}` : ''}. Placed ${when(order.created_at)}.` : undefined}
      wide
    >
      {order ? <OrderForm key={order.id} prefix={prefix} order={order} products={products} onDone={onClose} /> : null}
    </Dialog>
  );
}

function OrderForm({ prefix, order, products, onDone }: { prefix: string; order: Order; products: Map<number, Product>; onDone: () => void }) {
  const client = useQueryClient();
  const confirm = useConfirm();
  const [status, setStatus] = useState(order.status);
  const [message, setMessage] = useState(order.message ?? '');
  const changed = status !== order.status || message !== (order.message ?? '');
  const refresh = () => client.invalidateQueries({ queryKey: ['store', prefix] });
  const save = useMutation({
    // The route refuses a status it does not know, so the status goes only when it changed.
    mutationFn: () =>
      send(`/api/storefront/${prefix}/orders/${order.id}`, 'PUT', {
        ...(status !== order.status ? { status } : {}),
        message,
      }),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  const remove = useMutation({
    mutationFn: () => send(`/api/storefront/${prefix}/orders/${order.id}`, 'DELETE'),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  const options = STATUSES.includes(order.status) ? STATUSES : [order.status, ...STATUSES];
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="overflow-hidden rounded-lg border border-line">
        <Table>
          <thead>
            <tr>
              <Th>Item</Th>
              <Th className="text-right">Qty</Th>
              <Th className="text-right">Points</Th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <Tr key={item.id}>
                <Td className="w-full max-w-0">
                  <div className="truncate">{products.get(item.product_id)?.name ?? `Product ${item.product_id} (deleted)`}</div>
                  <div className="text-xs text-muted tabular-nums">{compact(item.price_at_time)} each</div>
                </Td>
                <Td className="text-right tabular-nums">{item.quantity}</Td>
                <Td className="text-right tabular-nums">{compact(item.price_at_time * item.quantity)}</Td>
              </Tr>
            ))}
            <Tr>
              <Td className="font-medium">Total</Td>
              <Td />
              <Td className="text-right font-medium tabular-nums">{compact(order.total_amount)}</Td>
            </Tr>
          </tbody>
        </Table>
      </div>
      <div className="grid gap-5 sm:grid-cols-[200px_minmax(0,1fr)]">
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            {options.map((s) => (
              <option key={s} value={s} disabled={!STATUSES.includes(s)}>
                {s}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Message to the member" hint="For example, where and when to pick up the order.">
          <Textarea value={message} onChange={(e) => setMessage(e.target.value)} className="min-h-20" />
        </Field>
      </div>
      <FormActions error={save.error ?? remove.error}>
        <Button variant="primary" disabled={!changed || save.isPending}>
          Save order
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button
          type="button"
          variant="danger"
          className="ml-auto"
          disabled={remove.isPending}
          onClick={() => {
            const stock = CLOSED.has(order.status) ? 'Stock does not change.' : 'Its items go back into stock.';
            void confirm(`Delete order #${order.id}? ${stock} The member does not get the points back.`, 'Delete').then((yes) => {
              if (yes) remove.mutate();
            });
          }}
        >
          <Trash2 className="size-4" /> Delete
        </Button>
      </FormActions>
    </form>
  );
}
