from flask import Blueprint, request, jsonify
from modules.auth.decoraters import auth_required, error_handler
from shared import db
from datetime import datetime #Added date time for created and updated just in case, remove UTCnow if not needed.

merch_blueprint = Blueprint("merch", __name__)

# Database Models
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_time = db.Column(db.Float, nullable=False)

# API Endpoints
@merch_blueprint.route("/products", methods=["GET"])
@error_handler
def get_products():
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'price': p.price,
        'stock': p.stock,
        'image_url': p.image_url
    } for p in products]), 200

@merch_blueprint.route("/products/<int:product_id>", methods=["GET"])
@error_handler
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'price': product.price,
        'stock': product.stock,
        'image_url': product.image_url
    }), 200

@merch_blueprint.route("/products", methods=["POST"])
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
    db.session.add(new_product)
    db.session.commit()
    return jsonify({'message': 'Product created successfully', 'id': new_product.id}), 201

@merch_blueprint.route("/products/<int:product_id>", methods=["PUT"])
@auth_required
@error_handler
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    
    product.name = data.get('name', product.name)
    product.description = data.get('description', product.description)
    product.price = data.get('price', product.price)
    product.stock = data.get('stock', product.stock)
    product.image_url = data.get('image_url', product.image_url)
    
    db.session.commit()
    return jsonify({'message': 'Product updated successfully'}), 200

@merch_blueprint.route("/products/<int:product_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product deleted successfully'}), 200

@merch_blueprint.route("/orders", methods=["GET"])
@auth_required
@error_handler
def get_orders():
    orders = Order.query.all()
    return jsonify([{
        'id': o.id,
        'user_id': o.user_id,
        'total_amount': o.total_amount,
        'status': o.status,
        'created_at': o.created_at.isoformat()
    } for o in orders]), 200

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
    db.session.add(new_order)
    db.session.commit()
    
    # Add order items
    for item in data['items']:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item['product_id'],
            quantity=item['quantity'],
            price_at_time=item['price']
        )
        db.session.add(order_item)
    
    db.session.commit()
    return jsonify({'message': 'Order created successfully', 'id': new_order.id}), 201 