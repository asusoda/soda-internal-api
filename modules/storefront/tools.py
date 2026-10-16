"""Store tools: products and orders."""

from core.tools import tool
from modules.storefront import service

IDS = {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": service.MAX_IDS}
STATUS = {"type": "string", "enum": service.ORDER_STATUSES}
PRODUCT = {
    "name": {"type": "string", "minLength": 1, "maxLength": 100},
    "description": {"type": "string", "maxLength": 5000},
    "price": {"type": "number", "minimum": 0},
    "stock": {"type": "integer", "minimum": 0},
    "image_url": {"type": "string", "maxLength": 255},
    "category": {"type": ["string", "null"], "maxLength": 50},
}


@tool(
    "store.products",
    description="The store's products: name, description, price in points, stock, image and category.",
    scope="store:read",
    module="storefront",
)
def store_products(db, org, caller):
    return {"products": [service.product_dict(p) for p in service.products(db, int(org.id))]}


@tool(
    "store.orders",
    description="The store's orders, newest first, with the buyer, status, message and items.",
    scope="store:read",
    module="storefront",
    input_schema={"type": "object", "properties": {"status": STATUS}, "additionalProperties": False},
)
def store_orders(db, org, caller, status: str | None = None):
    return {"orders": service.order_list(db, int(org.id), status)}


@tool(
    "store.save_product",
    description="Add a product, or change the product with id. A new product needs name, price and stock.",
    scope="store:write",
    module="storefront",
    input_schema={
        "type": "object",
        "properties": {"id": {"type": "integer"}, **PRODUCT},
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def store_save_product(db, org, caller, id: int | None = None, **data):
    return {"product": service.save_product(db, int(org.id), data, id)}


@tool(
    "store.delete_products",
    description="Delete products by id, up to 100. If one id is missing or has orders, nothing changes.",
    scope="store:write",
    module="storefront",
    confirm=True,
    input_schema={"type": "object", "properties": {"ids": IDS}, "required": ["ids"], "additionalProperties": False},
)
def store_delete_products(db, org, caller, ids: list[int]):
    return service.delete_products(db, int(org.id), ids)


@tool(
    "store.update_orders",
    description=(
        "Set the status, the message to the buyer, or both, of up to 100 orders. "
        "A change to cancelled puts the items back in stock and refunds the points. "
        "A cancelled order cannot change to another status."
    ),
    scope="store:write",
    module="storefront",
    input_schema={
        "type": "object",
        "properties": {"ids": IDS, "status": STATUS, "message": {"type": ["string", "null"], "maxLength": 2000}},
        "required": ["ids"],
        "minProperties": 2,
        "additionalProperties": False,
    },
)
def store_update_orders(db, org, caller, ids: list[int], **data):
    return {"orders": service.update_orders(db, int(org.id), ids, data)}


@tool(
    "store.delete_orders",
    description=(
        "Delete orders by id, up to 100. The items of an order that is not cancelled or delivered go back in stock, "
        "and its points are refunded."
    ),
    scope="store:write",
    module="storefront",
    confirm=True,
    input_schema={"type": "object", "properties": {"ids": IDS}, "required": ["ids"], "additionalProperties": False},
)
def store_delete_orders(db, org, caller, ids: list[int]):
    return service.delete_orders(db, int(org.id), ids)
