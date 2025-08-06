from flask import Blueprint, request, jsonify
from modules.auth.decoraters import auth_required, error_handler
from shared import store_db
from modules.merch.models import Product, Order, OrderItem

merch_blueprint = Blueprint("merch", __name__)

# API Endpoints
@merch_blueprint.route("/merch/products", methods=["GET"])
@error_handler
def get_products():
    db = next(store_db.get_db())
    try:
        products = store_db.get_all_products(db)
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'price': p.price,
            'stock': p.stock,
            'image_url': p.image_url
        } for p in products]), 200
    finally:
        db.close()

@merch_blueprint.route("/merch/products/<int:product_id>", methods=["GET"])
@error_handler
def get_product(product_id):
    db = next(store_db.get_db())
    try:
        product = store_db.get_product(db, product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
            
        return jsonify({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'stock': product.stock,
            'image_url': product.image_url
        }), 200
    finally:
        db.close()

@merch_blueprint.route("/merch/products/add", methods=["POST"])
@auth_required
@error_handler
def create_product():
    data = request.get_json()
    new_product = Product(
        name=data['name'],
        description=data.get('description', ''),
        price=data['price'],
        stock=data['stock'],
        image_url=data.get('image_url', '')
    )
    
    db = next(store_db.get_db())
    try:
        created_product = store_db.create_product(db, new_product)
        return jsonify({'message': 'Product created successfully', 'id': created_product.id}), 201
    finally:
        db.close()

@merch_blueprint.route("/merch/products/<int:product_id>", methods=["PUT"])
@auth_required
@error_handler
def update_product(product_id):
    db = next(store_db.get_db())
    try:
        product = store_db.get_product(db, product_id)
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

@merch_blueprint.route("/api/products/<int:product_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_product(product_id):
    db = next(store_db.get_db())
    try:
        product = store_db.get_product(db, product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
            
        db.delete(product)
        db.commit()
        return jsonify({'message': 'Product deleted successfully'}), 200
    finally:
        db.close()

@merch_blueprint.route("/orders", methods=["GET"])
@auth_required
@error_handler
def get_orders():
    db = next(store_db.get_db())
    try:
        orders = store_db.get_all_orders(db)
        return jsonify([{
            'id': o.id,
            'user_id': o.user_id,
            'total_amount': o.total_amount,
            'status': o.status,
            'created_at': o.created_at.isoformat()
        } for o in orders]), 200
    finally:
        db.close()

@merch_blueprint.route("/orders", methods=["POST"])
@auth_required
@error_handler
def create_order():
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
    
    db = next(store_db.get_db())
    try:
        created_order = store_db.create_order(db, new_order, order_items)
        return jsonify({'message': 'Order created successfully', 'id': created_order.id}), 201
    finally:
        db.close() 