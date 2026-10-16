"""Product and order queries for the storefront. No Flask here."""

import math
from collections import Counter
from datetime import UTC, datetime

from core import webhooks
from core.errors import ServiceError
from core.log import get_logger
from modules.auth import scopes
from modules.points.models import Points
from modules.storefront.models import Order, OrderItem, Product

logger = get_logger(__name__)

webhooks.declare("order.created", "Store orders", "A member places an order in the store.", "storefront")
scopes.declare("store:read", "Read the store's products and orders, with the name and email of each buyer")
scopes.declare("store:write", "Add, change and delete products, and change the status of orders or delete them")

ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]
MAX_IDS = 100


class StoreError(ServiceError):
    pass


def normalize_category(value):
    """The category with whitespace stripped; an empty string becomes None."""
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    return value


def prices_mismatch(total_amount, priced) -> bool:
    """True if the client's total or a client unit price differs from the catalog by more than half a cent.

    priced holds (product, quantity, client unit price).
    """
    return abs(catalog_total(priced) - float(total_amount)) > 0.005 or any(
        abs(float(product.price) - client_price) > 0.005 for product, _, client_price in priced
    )


def parse_total(value) -> float:
    """The client's total as a positive number. Raises StoreError for a value that is not a positive number."""
    if isinstance(value, bool):
        raise StoreError("Total amount must be a number")
    try:
        total = float(value)
    except (TypeError, ValueError):
        raise StoreError("Total amount must be a number") from None
    if not math.isfinite(total) or total <= 0:
        raise StoreError("Total amount must be greater than 0")
    return total


def price_items(db, organization_id, items) -> tuple[list[OrderItem], list[tuple[Product, int, float]]]:
    """Order items at catalog prices, and the (product, quantity, client unit price) of each. Changes no stock.

    Raises StoreError for a bad item, a product that is not in the org, or too little stock.
    """
    if not isinstance(items, list) or not items:
        raise StoreError("Order items are required")
    order_items: list[OrderItem] = []
    priced: list[tuple[Product, int, float]] = []
    wanted: Counter[int] = Counter()
    for item in items:
        if not isinstance(item, dict) or not all(k in item for k in ("product_id", "quantity", "price")):
            raise StoreError("Each item must have product_id, quantity, and price")
        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
            client_price = float(item["price"])
        except (TypeError, ValueError):
            raise StoreError("Each item must have a numeric product_id, quantity, and price") from None
        if quantity < 1:
            raise StoreError("Quantity must be at least 1")
        found = product(db, product_id, organization_id, for_update=True)
        if not found:
            raise StoreError(f"Product {product_id} not found", 404)
        wanted[found.id] += quantity
        if found.stock < wanted[found.id]:
            raise StoreError(f"Insufficient stock for product {found.name}")
        priced.append((found, quantity, client_price))
        order_items.append(OrderItem(product_id=found.id, quantity=quantity, price_at_time=float(found.price)))
    return order_items, priced


def catalog_total(priced) -> float:
    """The sum of catalog price times quantity. priced holds (product, quantity, client unit price)."""
    return float(sum(float(product.price) * quantity for product, quantity, _ in priced))


def take_stock(priced) -> None:
    """Lower the stock of each product by its quantity. The caller commits."""
    for found, quantity, _ in priced:
        found.stock -= quantity


def points_number(value: float) -> float | int:
    """The value as an int when it has no fraction, else the float."""
    return int(value) if float(value).is_integer() else value


def purchase_event(order_id) -> str:
    """The event of the points entry that pays for an order."""
    return f"Storefront Purchase - Order #{order_id}"


def refund_event(order_id) -> str:
    """The event of the points entry that gives back the points of an order."""
    return f"Refund - Order #{order_id}"


def create_product(db, product, organization_id):
    """Add the product to the org and commit. Rolls back and raises on an error."""
    try:
        product.organization_id = organization_id
        db.add(product)
        db.commit()
        db.refresh(product)
        logger.info(f"Created storefront product '{product.name}' for organization {organization_id}")
        return product
    except Exception as e:
        logger.error(f"Error creating storefront product: {str(e)}")
        db.rollback()
        raise


def create_order(db, order, order_items, organization_id, charge: float | None = None):
    """Add the order and its items to the org and commit. Rolls back and raises on an error.

    With charge, a negative points entry of that amount pays for the order in the same commit.
    """
    try:
        order.organization_id = organization_id
        db.add(order)
        db.flush()

        for item in order_items:
            item.organization_id = organization_id
            item.order_id = order.id
            db.add(item)

        if charge is not None:
            db.add(
                Points(
                    user_id=order.user_id,
                    organization_id=organization_id,
                    points=-charge,
                    event=purchase_event(order.id),
                    timestamp=datetime.now(UTC),
                    awarded_by_officer="System",
                )
            )

        db.commit()
        db.refresh(order)
        logger.info(f"Created storefront order {order.id} for organization {organization_id}")
        _announce(order, len(order_items), organization_id)
        return order
    except Exception as e:
        logger.error(f"Error creating storefront order: {str(e)}")
        db.rollback()
        raise


def _announce(order, items: int, organization_id) -> None:
    """Send the order.created webhook event."""
    message = webhooks.Message(
        title=f"New store order #{order.id}",
        fields=(("Items", str(items)), ("Total", f"{float(order.total_amount or 0):g} points")),
        color=webhooks.GREEN,
    )
    webhooks.emit(int(organization_id), "order.created", message)


def products(db, organization_id):
    """The org's products, or [] on an error."""
    try:
        return db.query(Product).filter(Product.organization_id == organization_id).all()
    except Exception as e:
        logger.error(f"Error getting storefront products: {str(e)}")
        return []


def product(db, product_id, organization_id, for_update=False):
    """The org's product with this id, or None. for_update locks the row until the caller commits."""
    try:
        query = db.query(Product).filter(Product.id == product_id, Product.organization_id == organization_id)
        return (query.with_for_update() if for_update else query).first()
    except Exception as e:
        logger.error(f"Error getting storefront product: {str(e)}")
        return None


def orders(db, organization_id):
    """The org's orders, or [] on an error."""
    try:
        return db.query(Order).filter(Order.organization_id == organization_id).all()
    except Exception as e:
        logger.error(f"Error getting storefront orders: {str(e)}")
        return []


def order(db, order_id, organization_id, for_update: bool = False):
    """The org's order with this id, or None. With for_update, the row stays locked until the commit."""
    try:
        query = db.query(Order).filter(Order.id == order_id, Order.organization_id == organization_id)
        return (query.with_for_update() if for_update else query).first()
    except Exception as e:
        logger.error(f"Error getting storefront order: {str(e)}")
        return None


def _check_no_orders(db, product_ids) -> None:
    """Raises StoreError 409 if an order item refers to one of the products."""
    if db.query(OrderItem.id).filter(OrderItem.product_id.in_(product_ids)).first():
        raise StoreError("Product has orders. Set its stock to 0 to hide it from the store.", 409)


def delete_product(db, product_id, organization_id) -> bool:
    """Delete the org's product and commit. False if it is missing or the delete fails.

    Raises StoreError 409 if an order has the product.
    """
    found = product(db, product_id, organization_id)
    if found:
        _check_no_orders(db, [found.id])
    try:
        if found:
            db.delete(found)
            db.commit()
            logger.info(f"Deleted storefront product {product_id} for organization {organization_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting storefront product: {str(e)}")
        db.rollback()
        return False


def product_dict(product: Product) -> dict:
    """A product as the officer routes and tools return it."""
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "stock": product.stock,
        "image_url": product.image_url,
        "category": product.category,
        "organization_id": product.organization_id,
    }


def order_dict(order: Order) -> dict:
    """An order with its buyer and items, as the order list returns it."""
    return {
        "id": order.id,
        "user_id": order.user_id,
        "total_amount": order.total_amount,
        "status": order.status,
        "message": order.message,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "organization_id": order.organization_id,
        "user_name": order.user.name if order.user else "Unknown User",
        "user_email": order.user.email if order.user else None,
        "items": [
            {"id": i.id, "product_id": i.product_id, "quantity": i.quantity, "price_at_time": i.price_at_time}
            for i in order.items
        ],
    }


def change_product(product: Product, data: dict) -> None:
    """Set the product fields that data has. The caller commits."""
    if "name" in data:
        product.name = data["name"]
    if "description" in data:
        product.description = data["description"]
    if "price" in data:
        product.price = float(data["price"])
    if "stock" in data:
        product.stock = int(data["stock"])
    if "image_url" in data:
        product.image_url = data["image_url"]
    if "category" in data:
        product.category = normalize_category(data["category"])


def _restock(db, order: Order, organization_id) -> None:
    """Put the items of the order back in stock. The caller commits."""
    for item in order.items:
        found = product(db, item.product_id, organization_id, for_update=True)
        if found:
            found.stock += item.quantity


def _refund(db, order: Order, organization_id) -> None:
    """Add a points entry that gives back what the order took, less refunds already given. The caller commits.

    An order with no purchase entry, such as a pending member order, gets no refund.
    """
    rows = (
        db.query(Points.points)
        .filter(
            Points.organization_id == organization_id,
            Points.user_id == order.user_id,
            Points.event.in_([purchase_event(order.id), refund_event(order.id)]),
        )
        .all()
    )
    owed = -sum(float(row.points or 0) for row in rows)
    if owed > 0:
        db.add(
            Points(
                user_id=order.user_id,
                organization_id=organization_id,
                points=owed,
                event=refund_event(order.id),
                timestamp=datetime.now(UTC),
                awarded_by_officer="System",
            )
        )


def change_order(db, order: Order, data: dict) -> None:
    """Set the status and message that data has. The caller commits.

    A change to cancelled puts the items back in stock and refunds the points. Raises StoreError for an unknown
    status, and 409 for a change away from cancelled.
    """
    if "status" in data:
        status = data["status"]
        if status not in ORDER_STATUSES:
            raise StoreError(f"Invalid status. Must be one of: {', '.join(ORDER_STATUSES)}")
        if order.status == "cancelled" and status != "cancelled":
            raise StoreError("A cancelled order cannot change status. Place a new order.", 409)
        if status == "cancelled" and order.status != "cancelled":
            _restock(db, order, order.organization_id)
            _refund(db, order, order.organization_id)
        order.status = status
    if "message" in data:
        order.message = data["message"]


def remove_order(db, order: Order, organization_id) -> None:
    """Delete an order. The caller commits.

    Unless the order is cancelled or delivered, its items go back in stock and its points are refunded.
    """
    if order.status not in ["cancelled", "delivered"]:
        _restock(db, order, organization_id)
        _refund(db, order, organization_id)
    db.delete(order)


def _all(db, model, ids: list[int], organization_id, label: str, for_update: bool = False) -> list:
    query = db.query(model).filter(model.id.in_(ids), model.organization_id == organization_id)
    rows = (query.with_for_update() if for_update else query).all()
    missing = sorted(set(ids) - {row.id for row in rows})
    if missing:
        raise StoreError(f"No {label} with ids {', '.join(str(i) for i in missing)}", 404)
    return rows


def save_product(db, organization_id, data: dict, product_id: int | None = None) -> dict:
    """Add a product, or change the product with product_id. Commits."""
    if product_id is None:
        for key in ("name", "price", "stock"):
            if data.get(key) in (None, ""):
                raise StoreError(f"Product {key} is required")
        row = Product(
            name=data["name"],
            description=data.get("description", ""),
            price=float(data["price"]),
            stock=int(data["stock"]),
            image_url=data.get("image_url", ""),
            category=normalize_category(data.get("category")),
        )
        return product_dict(create_product(db, row, organization_id))
    found = product(db, product_id, organization_id)
    if found is None:
        raise StoreError("Product not found", 404)
    change_product(found, data)
    db.commit()
    return product_dict(found)


def delete_products(db, organization_id, ids: list[int]) -> dict:
    """Delete products by id in one commit. If one id is missing or has orders, nothing changes."""
    rows = _all(db, Product, ids, organization_id, "products")
    _check_no_orders(db, [row.id for row in rows])
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": sorted(ids)}


def order_list(db, organization_id, status: str | None = None) -> list[dict]:
    """The org's orders, newest first. status keeps the orders with that status."""
    rows = [o for o in orders(db, organization_id) if status is None or o.status == status]
    return [order_dict(o) for o in sorted(rows, key=lambda o: o.id, reverse=True)]


def update_orders(db, organization_id, ids: list[int], data: dict) -> list[dict]:
    """Set the status or message of orders in one commit. If one id is missing, nothing changes."""
    rows = _all(db, Order, ids, organization_id, "orders", for_update=True)
    for row in rows:
        change_order(db, row, data)
    db.commit()
    return [order_dict(row) for row in rows]


def delete_orders(db, organization_id, ids: list[int]) -> dict:
    """Delete orders in one commit. Stock and points go back as remove_order does."""
    for row in _all(db, Order, ids, organization_id, "orders", for_update=True):
        remove_order(db, row, organization_id)
    db.commit()
    return {"deleted": sorted(ids)}
