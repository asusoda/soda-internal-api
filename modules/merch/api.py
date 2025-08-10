from flask import Blueprint, request, jsonify
from modules.auth.decoraters import auth_required, error_handler
from modules.utils.db import DBConnect
from modules.merch.models import Product, Order, OrderItem

merch_blueprint = Blueprint("merch", __name__)
db_connect = DBConnect()

# API Endpoints
@merch_blueprint.route("/<string:org_prefix>/products", methods=["GET"])
@error_handler
def get_products(org_prefix):
    db = next(db_connect.get_db())
    try:
        # Get organization ID from prefix
        from modules.organizations.models import Organization
        org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        products = db_connect.get_merch_products(db, org.id)
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'price': p.price,
            'stock': p.stock,
            'image_url': p.image_url,
            'organization_id': p.organization_id
        } for p in products]), 200
    finally:
        db.close()

@merch_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["GET"])
@error_handler
def get_product(org_prefix, product_id):
    db = next(db_connect.get_db())
    try:
        # Get organization ID from prefix
        from modules.organizations.models import Organization
        org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        product = db_connect.get_merch_product(db, product_id, org.id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
            
        return jsonify({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'stock': product.stock,
            'image_url': product.image_url,
            'organization_id': product.organization_id
        }), 200
    finally:
        db.close()

@merch_blueprint.route("/<string:org_prefix>/products", methods=["POST"])
@auth_required
@error_handler
def create_product(org_prefix):
    data = request.get_json()
    new_product = Product(
        name=data['name'],
        description=data.get('description', ''),
        price=data['price'],
        stock=data['stock'],
        image_url=data.get('image_url', '')
    )
    
    db = next(db_connect.get_db())
    try:
        # Get organization ID from prefix
        from modules.organizations.models import Organization
        org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        created_product = db_connect.create_merch_product(db, new_product, org.id)
        return jsonify({'message': 'Product created successfully', 'id': created_product.id}), 201
    finally:
        db.close()

@merch_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["PUT"])
@auth_required
@error_handler
def update_product(org_prefix, product_id):
    db = next(db_connect.get_db())
    try:
        # Get organization ID from prefix
        from modules.organizations.models import Organization
        org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        product = db_connect.get_merch_product(db, product_id, org.id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
            
        data = request.get_json()
        
        product.name = data.get('name', product.name)
        product.description = data.get('description', product.description)
        product.price = data.get('price', product.price)
        product.stock = data.get('stock', product.stock)
        product.image_url = data.get('image_url', product.image_url)
        
        db.commit()
        return jsonify({'message': 'Product updated successfully'}), 200
    finally:
        db.close()

@merch_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_product(org_prefix, product_id):
    db = next(db_connect.get_db())
    try:
        # Get organization ID from prefix
        from modules.organizations.models import Organization
        org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        success = db_connect.delete_merch_product(db, product_id, org.id)
        if not success:
            return jsonify({"error": "Product not found"}), 404
            
        return jsonify({'message': 'Product deleted successfully'}), 200
    finally:
        db.close()

@merch_blueprint.route("/<string:org_prefix>/orders", methods=["GET"])
@auth_required
@error_handler
def get_orders(org_prefix):
    db = next(db_connect.get_db())
    try:
        # Get organization ID from prefix
        from modules.organizations.models import Organization
        org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        orders = db_connect.get_merch_orders(db, org.id)
        return jsonify([{
            'id': o.id,
            'user_id': o.user_id,
            'total_amount': o.total_amount,
            'status': o.status,
            'created_at': o.created_at.isoformat(),
            'organization_id': o.organization_id
        } for o in orders]), 200
    finally:
        db.close()

@merch_blueprint.route("/<string:org_prefix>/orders", methods=["POST"])
@auth_required
@error_handler
def create_order(org_prefix):
    data = request.get_json()
    new_order = Order(
        user_id=data['user_id'],
        total_amount=data['total_amount'],
        status='pending'
    )
    
    # Prepare order items
    order_items = []
    for item in data['items']:
        order_items.append(OrderItem(
            product_id=item['product_id'],
            quantity=item['quantity'],
            price_at_time=item['price']
        ))
    
    db = next(db_connect.get_db())
    try:
        # Get organization ID from prefix
        from modules.organizations.models import Organization
        org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        created_order = db_connect.create_merch_order(db, new_order, order_items, org.id)
        return jsonify({'message': 'Order created successfully', 'id': created_order.id}), 201
    finally:
        db.close() 