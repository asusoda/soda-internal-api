"""Member routes of the storefront: the Discord member store and the Clerk wallet, orders and checkout.

The routes register on storefront_blueprint. modules/registry.py imports the blueprint from here, so they
register before the blueprint is mounted.
"""

from datetime import UTC, datetime

from flask import g, jsonify, request
from sqlalchemy import func

from core.db import db_connect
from core.http.responses import error_handler
from modules.auth.decorators import dual_auth_required, member_required
from modules.organizations.service import find_by_prefix
from modules.points.models import Points
from modules.storefront import service
from modules.storefront.api import price_mismatch, storefront_blueprint
from modules.storefront.models import Order, OrderItem
from modules.users.models import User, UserOrganizationMembership
from modules.users.service import get_or_create_user, get_or_create_user_from_clerk

__all__ = ["storefront_blueprint"]


@storefront_blueprint.route("/<string:org_prefix>/members/store", methods=["GET"])
@member_required
@error_handler
def get_member_store(org_prefix, **kwargs):
    """Get store front for organization members (may include member-only products)"""
    user_discord_id = kwargs.get("user_discord_id")
    organization = kwargs["organization"]

    user = get_or_create_user(user_discord_id, organization.id)

    db = next(db_connect.get_db())
    try:
        products = service.products(db, organization.id)
        available_products = [p for p in products if p.stock > 0]

        return jsonify(
            {
                "organization": {
                    "name": organization.name,
                    "prefix": organization.prefix,
                    "description": organization.description,
                },
                "user_info": {"discord_id": user_discord_id, "user_id": user.id if user else None, "is_member": True},
                "products": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "price": p.price,
                        "stock": p.stock,
                        "image_url": p.image_url,
                        "created_at": p.created_at.isoformat() if p.created_at else None,
                        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    }
                    for p in available_products
                ],
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/members/orders", methods=["GET"])
@member_required
@error_handler
def get_member_orders(org_prefix, **kwargs):
    """Get orders for the authenticated member"""
    user_discord_id = kwargs.get("user_discord_id")
    organization = kwargs["organization"]

    user = get_or_create_user(user_discord_id, organization.id)

    if not user:
        return jsonify({"error": "Could not create or find user"}), 500

    db = next(db_connect.get_db())
    try:
        orders = (
            db.query(Order)
            .filter(Order.organization_id == organization.id, Order.user_id == user.id)
            .order_by(Order.created_at.desc())
            .all()
        )

        return jsonify(
            [
                {
                    "id": o.id,
                    "total_amount": o.total_amount,
                    "status": o.status,
                    "message": o.message,
                    "created_at": o.created_at.isoformat(),
                    "updated_at": o.updated_at.isoformat() if o.updated_at else None,
                    "items": [
                        {
                            "id": item.id,
                            "product_id": item.product_id,
                            "quantity": item.quantity,
                            "price_at_time": item.price_at_time,
                            "product_name": item.product.name if item.product else "Unknown Product",
                        }
                        for item in o.items
                    ],
                }
                for o in orders
            ]
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/members/orders", methods=["POST"])
@member_required
@error_handler
def create_member_order(org_prefix, **kwargs):
    """Create a new order for authenticated member"""
    user_discord_id = kwargs.get("user_discord_id")
    organization = kwargs["organization"]

    user = get_or_create_user(user_discord_id, organization.id)

    if not user:
        return jsonify({"error": "Could not create or find user"}), 500

    data = request.get_json()

    if not data.get("total_amount"):
        return jsonify({"error": "Total amount is required"}), 400
    if not data.get("items") or len(data["items"]) == 0:
        return jsonify({"error": "Order items are required"}), 400

    new_order = Order(
        user_id=user.id,
        discord_user_id=user_discord_id,  # legacy column
        total_amount=float(data["total_amount"]),
        status="pending",
    )

    order_items = []
    for item in data["items"]:
        if not all(k in item for k in ["product_id", "quantity", "price"]):
            return jsonify({"error": "Each item must have product_id, quantity, and price"}), 400
        if int(item["quantity"]) < 1:
            return jsonify({"error": "Quantity must be at least 1"}), 400
        order_items.append(
            OrderItem(
                product_id=int(item["product_id"]), quantity=int(item["quantity"]), price_at_time=float(item["price"])
            )
        )

    db = next(db_connect.get_db())
    try:
        priced = []
        for item in order_items:
            product = service.product(db, item.product_id, organization.id)
            if not product:
                return jsonify({"error": f"Product {item.product_id} not found"}), 404
            if product.stock < item.quantity:
                return jsonify({"error": f"Insufficient stock for product {product.name}"}), 400

            product.stock -= item.quantity
            priced.append((product, item.quantity, item.price_at_time))

        if price_mismatch(org_prefix, new_order.total_amount, priced):
            return jsonify({"error": "Prices have changed. Reload the store and try again."}), 409

        created_order = service.create_order(db, new_order, order_items, organization.id)
        return jsonify(
            {
                "message": "Order created successfully",
                "id": created_order.id,
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


@storefront_blueprint.route("/<string:org_prefix>/members/orders/<int:order_id>", methods=["GET"])
@member_required
@error_handler
def get_member_order(org_prefix, order_id, **kwargs):
    """Get a specific order for the authenticated member"""
    user_discord_id = kwargs.get("user_discord_id")
    organization = kwargs["organization"]

    db = next(db_connect.get_db())
    try:
        order = (
            db.query(Order)
            .filter(Order.id == order_id, Order.organization_id == organization.id, Order.user_id == user_discord_id)
            .first()
        )

        if not order:
            return jsonify({"error": "Order not found"}), 404

        return jsonify(
            {
                "id": order.id,
                "total_amount": order.total_amount,
                "status": order.status,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
                "items": [
                    {
                        "id": item.id,
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "price_at_time": item.price_at_time,
                        "product_name": item.product.name if item.product else "Unknown Product",
                    }
                    for item in order.items
                ],
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/members/points", methods=["GET"])
@member_required
@error_handler
def get_user_points_public(org_prefix, **kwargs):
    """Get authenticated member's points balance (storefront endpoint)"""
    db = next(db_connect.get_db())
    try:
        user_discord_id = kwargs.get("user_discord_id")
        organization = kwargs["organization"]

        if not user_discord_id:
            return jsonify({"error": "User not found"}), 404

        user = db.query(User).filter_by(discord_id=user_discord_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        membership = (
            db.query(UserOrganizationMembership)
            .filter_by(user_id=user.id, organization_id=organization.id, is_active=True)
            .first()
        )

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 403

        total_points = (
            db.query(func.sum(Points.points)).filter_by(user_id=user.id, organization_id=organization.id).scalar() or 0
        )

        points_records = (
            db.query(Points)
            .filter_by(user_id=user.id, organization_id=organization.id)
            .order_by(Points.timestamp.desc())
            .limit(20)
            .all()
        )

        return jsonify(
            {
                "email": getattr(user, "email", None),
                "total_points": total_points,
                "points_breakdown": [
                    {
                        "points": p.points,
                        "event": p.event,
                        "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                        "awarded_by": p.awarded_by_officer,
                    }
                    for p in points_records
                ],
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/orders/<string:user_email>", methods=["GET"])
@dual_auth_required
@error_handler
def get_user_orders_clerk(org_prefix, user_email):
    """Get user's orders using dual authentication"""
    db = next(db_connect.get_db())
    try:
        if g.get("clerk_user_email") != user_email:
            return jsonify({"error": "Unauthorized: Email mismatch"}), 403

        organization = find_by_prefix(db, org_prefix)
        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        user = db.query(User).filter_by(email=user_email).first()

        if not user and g.get("clerk_user"):
            user = get_or_create_user_from_clerk(db, organization.id, g.clerk_user, user_email)
            if not user:
                return jsonify({"error": "Failed to create user account"}), 500

        if not user:
            return jsonify({"error": "User not found"}), 404

        orders = (
            db.query(Order)
            .filter(Order.organization_id == organization.id, Order.user_id == user.id)
            .order_by(Order.created_at.desc())
            .all()
        )

        return jsonify(
            [
                {
                    "id": o.id,
                    "total_amount": o.total_amount,
                    "status": o.status,
                    "message": o.message,
                    "created_at": o.created_at.isoformat(),
                    "updated_at": o.updated_at.isoformat() if o.updated_at else None,
                    "items": [
                        {
                            "id": item.id,
                            "product_id": item.product_id,
                            "quantity": item.quantity,
                            "price_at_time": item.price_at_time,
                            "product_name": item.product.name if item.product else "Unknown Product",
                        }
                        for item in o.items
                    ],
                }
                for o in orders
            ]
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/wallet/<string:user_email>", methods=["GET"])
@dual_auth_required
@error_handler
def get_user_wallet_clerk(org_prefix, user_email):
    """Get user wallet/points using dual authentication"""
    db = next(db_connect.get_db())
    try:
        if g.get("clerk_user_email") != user_email:
            return jsonify({"error": "Unauthorized: Email mismatch"}), 403

        organization = find_by_prefix(db, org_prefix)
        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        user = db.query(User).filter_by(email=user_email).first()

        if not user and g.get("clerk_user"):
            user = get_or_create_user_from_clerk(db, organization.id, g.clerk_user, user_email)
            if not user:
                return jsonify({"error": "Failed to create user account"}), 500

        if not user:
            return jsonify({"error": "User not found"}), 404

        total_points = (
            db.query(func.sum(Points.points))
            .filter(Points.user_id == user.id, Points.organization_id == organization.id)
            .scalar()
            or 0
        )

        points_records = (
            db.query(Points)
            .filter_by(user_id=user.id, organization_id=organization.id)
            .order_by(Points.timestamp.desc())
            .limit(20)
            .all()
        )

        return jsonify(
            {
                "email": user.email,
                "total_points": total_points,
                "points_breakdown": [
                    {
                        "points": p.points,
                        "event": p.event,
                        "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                        "awarded_by": p.awarded_by_officer,
                    }
                    for p in points_records
                ],
            }
        ), 200
    finally:
        db.close()


@storefront_blueprint.route("/<string:org_prefix>/checkout", methods=["POST"])
@dual_auth_required
@error_handler
def clerk_checkout(org_prefix):
    """Checkout endpoint using dual authentication"""
    data = request.get_json()
    user_email = g.get("clerk_user_email")

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

        if not user and g.get("clerk_user"):
            user = get_or_create_user_from_clerk(db, org.id, g.clerk_user, user_email)

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
