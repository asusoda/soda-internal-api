from datetime import UTC, datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from core.db import db_connect
from core.http.responses import error_handler
from modules.auth.access import decide
from modules.auth.decorators import auth_required, dual_auth_required, org_officer_required
from modules.organizations.service import find_by_prefix
from modules.points.models import Points
from modules.storefront import service
from modules.storefront.models import Order, OrderItem, Product
from modules.users.models import User, UserOrganizationMembership

storefront_blueprint = Blueprint("storefront", __name__)


def price_mismatch(org_prefix, total_amount, priced) -> bool:
    """True if the order must be refused because the client's prices differ from the catalog.

    priced holds (product, quantity, client unit price). A mismatch is logged as
    checkout_price_mismatch, and refused only when ACCESS_ENFORCE is true.
    """
    if not service.prices_mismatch(total_amount, priced):
        return False
    return decide("checkout_price_mismatch", org=org_prefix)


@storefront_blueprint.route("/<string:org_prefix>/products", methods=["GET"])
@error_handler
def get_products(org_prefix):
    """Get all products for an organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        products = service.products(db, org.id)
        return jsonify(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "price": p.price,
                    "stock": p.stock,
                    "image_url": p.image_url,
                    "category": p.category,
                    "organization_id": p.organization_id,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in products
            ]
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["GET"])
@error_handler
def get_product(org_prefix, product_id):
    """Get a specific product by ID for an organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        product = service.product(db, product_id, org.id)
        if not product:
            return jsonify({"error": "Product not found"}), 404

        return jsonify(
            {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "stock": product.stock,
                "image_url": product.image_url,
                "category": product.category,
                "organization_id": product.organization_id,
                "created_at": product.created_at.isoformat() if product.created_at else None,
                "updated_at": product.updated_at.isoformat() if product.updated_at else None,
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/products", methods=["POST"])
@auth_required
@error_handler
def create_product(org_prefix):
    """Create a new product for an organization"""
    data = request.get_json()

    if not data.get("name"):
        return jsonify({"error": "Product name is required"}), 400
    if not data.get("price"):
        return jsonify({"error": "Product price is required"}), 400
    if not data.get("stock"):
        return jsonify({"error": "Product stock is required"}), 400

    category = service.normalize_category(data.get("category"))

    new_product = Product(
        name=data["name"],
        description=data.get("description", ""),
        price=float(data["price"]),
        stock=int(data["stock"]),
        image_url=data.get("image_url", ""),
        category=category,
    )

    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        created_product = service.create_product(db, new_product, org.id)
        return jsonify(
            {
                "message": "Product created successfully",
                "id": created_product.id,
                "product": {
                    "id": created_product.id,
                    "name": created_product.name,
                    "description": created_product.description,
                    "price": created_product.price,
                    "stock": created_product.stock,
                    "image_url": created_product.image_url,
                    "category": created_product.category,
                    "organization_id": created_product.organization_id,
                },
            }
        ), 201
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["PUT"])
@auth_required
@error_handler
def update_product(org_prefix, product_id):
    """Update a product for an organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        product = service.product(db, product_id, org.id)
        if not product:
            return jsonify({"error": "Product not found"}), 404

        data = request.get_json()
        service.change_product(product, data)
        db.commit()
        return jsonify(
            {
                "message": "Product updated successfully",
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "price": product.price,
                    "stock": product.stock,
                    "image_url": product.image_url,
                    "category": product.category,
                    "organization_id": product.organization_id,
                },
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_product(org_prefix, product_id):
    """Delete a product for an organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        success = service.delete_product(db, product_id, org.id)
        if not success:
            return jsonify({"error": "Product not found"}), 404

        return jsonify({"message": "Product deleted successfully"}), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/orders", methods=["GET"])
@dual_auth_required
@org_officer_required
@error_handler
def get_orders(org_prefix):
    """Get all orders for an organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        orders = service.orders(db, org.id)
        return jsonify(
            [
                {
                    "id": o.id,
                    "user_id": o.user_id,
                    "total_amount": o.total_amount,
                    "status": o.status,
                    "message": o.message,
                    "created_at": o.created_at.isoformat(),
                    "updated_at": o.updated_at.isoformat() if o.updated_at else None,
                    "organization_id": o.organization_id,
                    "user_name": o.user.name if o.user else "Unknown User",
                    "user_email": o.user.email if o.user else None,
                    "items": [
                        {
                            "id": item.id,
                            "product_id": item.product_id,
                            "quantity": item.quantity,
                            "price_at_time": item.price_at_time,
                        }
                        for item in o.items
                    ],
                }
                for o in orders
            ]
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["GET"])
@auth_required
@error_handler
def get_order(org_prefix, order_id):
    """Get a specific order by ID for an organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        order = service.order(db, order_id, org.id)
        if not order:
            return jsonify({"error": "Order not found"}), 404

        return jsonify(
            {
                "id": order.id,
                "user_id": order.user_id,
                "total_amount": order.total_amount,
                "status": order.status,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
                "organization_id": order.organization_id,
                "items": [
                    {
                        "id": item.id,
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "price_at_time": item.price_at_time,
                    }
                    for item in order.items
                ],
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/orders", methods=["POST"])
@dual_auth_required
@error_handler
def create_order(org_prefix):
    """Create a new order for an organization with dual authentication"""
    data = request.get_json()
    user_email = g.get("clerk_user_email")

    if not user_email or "@" not in user_email:
        return jsonify({"error": "Authenticated user email is missing or invalid"}), 400
    if not data.get("total_amount"):
        return jsonify({"error": "Total amount is required"}), 400
    if not data.get("items") or len(data["items"]) == 0:
        return jsonify({"error": "Order items are required"}), 400

    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        membership = (
            db.query(UserOrganizationMembership)
            .filter(
                UserOrganizationMembership.user_id == user.id,
                UserOrganizationMembership.organization_id == org.id,
                UserOrganizationMembership.is_active,
            )
            .first()
        )
        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 403

        total_amount = float(data["total_amount"])

        points_sum = (
            db.query(func.sum(Points.points))
            .filter(Points.user_id == user.id, Points.organization_id == org.id)
            .scalar()
            or 0
        )

        if points_sum < total_amount:
            return jsonify({"error": f"Insufficient points. You have {points_sum} points but need {total_amount}"}), 400

        order_items = []
        priced = []
        for item in data["items"]:
            if not all(k in item for k in ["product_id", "quantity", "price"]):
                return jsonify({"error": "Each item must have product_id, quantity, and price"}), 400
            if int(item["quantity"]) < 1:
                return jsonify({"error": "Quantity must be at least 1"}), 400

            product = service.product(db, int(item["product_id"]), org.id)
            if not product:
                return jsonify({"error": f"Product {item['product_id']} not found"}), 404
            if product.stock < int(item["quantity"]):
                return jsonify({"error": f"Insufficient stock for product {product.name}"}), 400

            product.stock -= int(item["quantity"])
            priced.append((product, int(item["quantity"]), float(item["price"])))

            order_items.append(
                OrderItem(
                    product_id=int(item["product_id"]),
                    quantity=int(item["quantity"]),
                    price_at_time=float(item["price"]),
                )
            )

        if price_mismatch(org_prefix, total_amount, priced):
            return jsonify({"error": "Prices have changed. Reload the store and try again."}), 409

        new_order = Order(user_id=user.id, total_amount=total_amount, status="completed")
        created_order = service.create_order(db, new_order, order_items, org.id)

        # A negative point entry pays for the order
        point_deduction = Points(
            user_id=user.id,
            organization_id=org.id,
            points=-int(total_amount),
            event=f"Storefront Purchase - Order #{created_order.id}",
            timestamp=datetime.now(UTC),
            awarded_by_officer="System",
        )
        db.add(point_deduction)
        db.commit()

        return jsonify(
            {
                "message": "Order placed and points deducted successfully",
                "id": created_order.id,
                "points_deducted": int(total_amount),
                "order": {
                    "id": created_order.id,
                    "user_id": created_order.user_id,
                    "total_amount": created_order.total_amount,
                    "status": created_order.status,
                    "created_at": created_order.created_at.isoformat(),
                },
            }
        ), 201
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["PUT"])
@auth_required
@error_handler
def update_order_status(org_prefix, order_id):
    """Update order status for an organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        order = service.order(db, order_id, org.id)
        if not order:
            return jsonify({"error": "Order not found"}), 404

        data = request.get_json()
        try:
            service.change_order(order, data)
        except service.StoreError as e:
            return jsonify({"error": e.message}), e.status
        db.commit()
        return jsonify(
            {
                "message": "Order updated successfully",
                "order": {
                    "id": order.id,
                    "user_id": order.user_id,
                    "total_amount": order.total_amount,
                    "status": order.status,
                    "message": order.message,
                    "updated_at": order.updated_at.isoformat() if order.updated_at else None,
                },
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_order(org_prefix, order_id):
    """Delete an order for an organization"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        order = service.order(db, order_id, org.id)
        if not order:
            return jsonify({"error": "Order not found"}), 404

        service.remove_order(db, order, org.id)
        db.commit()
        return jsonify({"message": "Order deleted successfully"}), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/store", methods=["GET"])
@error_handler
def get_store_products(org_prefix):
    """Get all available products for public store front"""
    db = next(db_connect.get_db())
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        products = service.products(db, org.id)
        available_products = [p for p in products if p.stock > 0]

        return jsonify(
            {
                "organization": {"name": org.name, "prefix": org.prefix, "description": org.description},
                "products": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "price": p.price,
                        "stock": p.stock,
                        "image_url": p.image_url,
                    }
                    for p in available_products
                ],
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/store/purchase", methods=["POST"])
@auth_required
@error_handler
def purchase_products(org_prefix):
    """Public endpoint for customers to purchase products (Discord auth)"""
    return create_order(org_prefix)
