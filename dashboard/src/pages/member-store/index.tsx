import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Minus, Package, Plus, ShoppingCart } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { AuthFrame } from '../../components/auth-frame';
import { Badge, Button, Card, CardHeader, EmptyState, ErrorNote, OkNote, SkeletonRows } from '../../components/ui';
import { compact, timeAgo } from '../../lib/format';
import {
  type CartLine,
  freshCart,
  type MemberOrder,
  type MemberProfile,
  memberApi,
  type StoreBody,
  storePath,
} from './shared';

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'muted'> = {
  pending: 'warn',
  processing: 'warn',
  shipped: 'ok',
  delivered: 'ok',
  cancelled: 'bad',
};

function loadCart(prefix: string): CartLine[] {
  try {
    return JSON.parse(sessionStorage.getItem(`cart_${prefix}`) ?? '[]') as CartLine[];
  } catch {
    return [];
  }
}

// The org store for members: products for everyone, and the cart, points and orders after sign-in.
export function MemberStorePage() {
  const prefix = useParams().prefix ?? '';
  const signInError = useSearchParams()[0].get('error');
  const client = useQueryClient();
  const [cart, setCart] = useState<CartLine[]>(() => loadCart(prefix));
  const [placed, setPlaced] = useState(false);
  useEffect(() => {
    try {
      sessionStorage.setItem(`cart_${prefix}`, JSON.stringify(cart));
    } catch {
      // The cart stays in memory only.
    }
  }, [cart, prefix]);

  const store = useQuery({
    queryKey: ['member-store', prefix, 'store'],
    queryFn: () =>
      memberApi<StoreBody>(`/api/storefront/${prefix}/members/store`).catch(() =>
        memberApi<StoreBody>(`/api/storefront/${prefix}/store`),
      ),
  });
  const orders = useQuery({
    queryKey: ['member-store', prefix, 'orders'],
    queryFn: () => memberApi<MemberOrder[]>(`/api/storefront/${prefix}/members/orders`),
    retry: false,
  });
  const signedIn = orders.isSuccess;
  // Rebuilds the cart from the current products each time the store loads.
  useEffect(() => {
    if (store.data) setCart((lines) => freshCart(lines, store.data.products));
  }, [store.data]);
  const profile = useQuery({
    queryKey: ['member-store', prefix, 'profile'],
    queryFn: () => memberApi<MemberProfile>(`/api/points/${prefix}/member_profile`),
    enabled: signedIn,
    retry: false,
  });

  // Ends the API session, which holds the Discord sign-in
  const signOut = useMutation({
    mutationFn: () => memberApi('/api/auth/logout', { method: 'POST', body: '{}' }),
    // The cache holds the stores of every org that this browser opened, so all of them are cleared
    onSuccess: () => client.resetQueries({ queryKey: ['member-store'] }),
  });

  const total = cart.reduce((n, line) => n + line.product.price * line.quantity, 0);
  const order = useMutation({
    mutationFn: () =>
      memberApi(`/api/storefront/${prefix}/members/orders`, {
        method: 'POST',
        body: JSON.stringify({
          total_amount: total,
          items: cart.map((l) => ({ product_id: l.product.id, quantity: l.quantity, price: l.product.price })),
        }),
      }),
    onSuccess: () => {
      setCart([]);
      setPlaced(true);
      client.invalidateQueries({ queryKey: ['member-store', prefix] });
    },
  });

  const change = (productId: number, by: number) =>
    setCart((lines) =>
      lines
        .map((l) => (l.product.id === productId ? { ...l, quantity: Math.min(l.quantity + by, l.product.stock) } : l))
        .filter((l) => l.quantity > 0),
    );
  const add = (product: StoreBody['products'][number]) => {
    setPlaced(false);
    setCart((lines) =>
      lines.some((l) => l.product.id === product.id) ? lines : [...lines, { product, quantity: 1 }],
    );
  };
  const inCart = (id: number) => cart.find((l) => l.product.id === id)?.quantity ?? 0;
  const products = store.data?.products ?? [];

  return (
    <AuthFrame width="max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{store.data?.organization.name ?? 'Store'}</h1>
          <p className="mt-1 text-sm text-pretty text-muted">
            {store.data?.organization.description ?? 'Spend the points you earn at events.'}
          </p>
        </div>
        {signedIn ? (
          <div className="text-right text-sm">
            <div className="font-medium">{profile.data?.user.name ?? profile.data?.user.email ?? 'Signed in'}</div>
            <div className="text-muted tabular-nums">
              {profile.data ? `${compact(profile.data.current_organization.points)} points` : ''}
            </div>
            <button
              type="button"
              className="text-muted underline hover:text-fg"
              onClick={() => signOut.mutate()}
              disabled={signOut.isPending}
            >
              Sign out
            </button>
          </div>
        ) : (
          <Link
            to={`${storePath(prefix)}/login`}
            className="flex h-9 items-center rounded-lg bg-fg px-3 text-sm font-medium text-bg hover:opacity-90"
          >
            Member sign-in
          </Link>
        )}
      </div>
      {signInError || signOut.error ? (
        <div className="mb-4">
          <ErrorNote error={signOut.error ?? signInError} />
        </div>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card>
          <CardHeader title="Products" hint="Prices are in points." />
          {store.error ? (
            <div className="p-4">
              <ErrorNote error={store.error} />
            </div>
          ) : store.isLoading ? (
            <SkeletonRows rows={4} />
          ) : products.length ? (
            <ul className="grid gap-3 p-3 sm:grid-cols-2">
              {products.map((p) => (
                <li key={p.id} className="flex flex-col overflow-hidden rounded-xl border border-line bg-bg">
                  {p.image_url ? (
                    <img src={p.image_url} alt="" className="aspect-[16/9] w-full object-cover sm:aspect-[4/3]" loading="lazy" />
                  ) : (
                    <div className="flex aspect-[16/9] items-center sm:aspect-[4/3] justify-center bg-panel-2 text-muted">
                      <Package className="size-8" />
                    </div>
                  )}
                  <div className="flex flex-1 flex-col gap-1 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium">{p.name}</span>
                      <span className="text-sm font-medium tabular-nums">{compact(p.price)}</span>
                    </div>
                    {p.description ? <p className="text-xs text-pretty text-muted">{p.description}</p> : null}
                    <div className="mt-auto flex items-center justify-between pt-2">
                      <span className="text-xs text-muted">{p.stock} left</span>
                      <Button onClick={() => add(p)} disabled={inCart(p.id) > 0}>
                        {inCart(p.id) ? 'In cart' : 'Add to cart'}
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={Package} title="No products yet">
              Officers add products on the dashboard.
            </EmptyState>
          )}
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Cart" />
            <div className="space-y-3 p-4">
              {cart.length ? (
                <>
                  <ul className="space-y-2">
                    {cart.map((l) => (
                      <li key={l.product.id} className="flex items-center gap-2 text-sm">
                        <span className="min-w-0 flex-1 truncate">{l.product.name}</span>
                        <Button variant="ghost" size="icon" aria-label={`One less ${l.product.name}`} onClick={() => change(l.product.id, -1)}>
                          <Minus className="size-3.5" />
                        </Button>
                        <span className="w-5 text-center tabular-nums">{l.quantity}</span>
                        <Button variant="ghost" size="icon" aria-label={`One more ${l.product.name}`} onClick={() => change(l.product.id, 1)}>
                          <Plus className="size-3.5" />
                        </Button>
                      </li>
                    ))}
                  </ul>
                  <div className="flex justify-between border-t border-line pt-3 text-sm font-medium">
                    <span>Total</span>
                    <span className="tabular-nums">{compact(total)} points</span>
                  </div>
                  {order.error ? <ErrorNote error={order.error} /> : null}
                  {signedIn ? (
                    <Button variant="primary" className="w-full" onClick={() => order.mutate()} disabled={order.isPending || !store.data || store.isError}>
                      Place order
                    </Button>
                  ) : (
                    <p className="text-xs text-muted">
                      <Link to={`${storePath(prefix)}/login`} className="underline">
                        Sign in
                      </Link>{' '}
                      to place the order.
                    </p>
                  )}
                </>
              ) : (
                <p className="flex items-center gap-2 text-sm text-muted">
                  <ShoppingCart className="size-4" /> The cart is empty.
                </p>
              )}
              {placed ? <OkNote>Order placed. An officer will get it to you.</OkNote> : null}
            </div>
          </Card>
          {signedIn ? (
            <Card>
              <CardHeader title="Your orders" />
              {orders.data?.length ? (
                <ul className="divide-y divide-line">
                  {orders.data.map((o) => (
                    <li key={o.id} className="p-4 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium tabular-nums">{compact(o.total_amount)} points</span>
                        <Badge tone={STATUS_TONE[o.status] ?? 'muted'}>{o.status}</Badge>
                      </div>
                      <div className="mt-1 truncate text-xs text-muted">
                        {o.items.map((i) => `${i.quantity} x ${i.product_name}`).join(', ')}
                      </div>
                      <div className="text-xs text-muted">{timeAgo(o.created_at)}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="p-4 text-sm text-muted">No orders yet.</p>
              )}
            </Card>
          ) : null}
        </div>
      </div>
    </AuthFrame>
  );
}
