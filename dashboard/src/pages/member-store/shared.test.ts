import { describe, expect, it } from 'vitest';
import { freshCart, type StoreProduct } from './shared';

const product = (id: number, price: number, stock: number): StoreProduct => ({
  id,
  name: `Product ${id}`,
  description: null,
  price,
  stock,
  image_url: null,
});

describe('freshCart', () => {
  it('uses current prices, stops at stock and drops missing or sold-out products', () => {
    const cart = [
      { product: product(1, 10, 9), quantity: 2 },
      { product: product(2, 5, 9), quantity: 5 },
      { product: product(3, 5, 9), quantity: 1 },
      { product: product(4, 5, 9), quantity: 1 },
    ];
    const current = [product(1, 12, 9), product(2, 5, 3), product(4, 5, 0)];
    expect(freshCart(cart, current)).toEqual([
      { product: product(1, 12, 9), quantity: 2 },
      { product: product(2, 5, 3), quantity: 3 },
    ]);
  });
});
