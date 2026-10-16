# storefront

A merch store paid with points. Officers manage products and orders. Members buy with their points balance, signed in with Discord or Clerk.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `storefront_blueprint`; product, order and store routes |
| `member_api.py` | Member routes on the same blueprint: `/members/...`, `/orders/<email>`, `/wallet/<email>`, `/checkout` |
| `service.py` | Product and order queries and changes, category clean-up, catalog pricing of an order, the points charge and refund; declares `store:read` and `store:write` |
| `tools.py` | The `store.*` tools |
| `models.py` | Products, orders, order items |

## Surface

- Routes: `/api/storefront`, behind the `storefront` switch. Product and order changes need an officer of the org. `/members/...` routes need a Discord session of a server member. `/checkout`, `/wallet/<email>`, `/orders/<email>` and `POST /orders` need a Clerk or platform token. Product lists and `/store` are open.
- Jobs: none.
- Tools: `store.products`, `store.orders` (scope `store:read`); `store.save_product`, `store.update_orders`, `store.delete_products` (confirm), `store.delete_orders` (confirm) (scope `store:write`). Each one that takes `ids` takes up to 100. A cancel or a delete gives a refund as the routes do. A product that is in an order cannot be deleted.
- Webhook events: `order.created`, from `create_order()`. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `products`, `orders`, `order_items`.

## Known gaps

- Views in `api.py` and `member_api.py` open their own session, query and commit. `service.py` has only the shared queries.
- Checkout reads the balance and writes the order with no row lock. See Known faults in `docs/roadmap.md`.
