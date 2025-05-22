# Merch Store Module

This module handles the merchandise store functionality, including product management and order processing.

## Database Structure

### Products Table
- `id` (Integer, Primary Key)
- `name` (String, Required)
- `description` (Text)
- `price` (Float, Required)
- `stock` (Integer, Required)
- `image_url` (String)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Orders Table
- `id` (Integer, Primary Key)
- `user_id` (String, Required)
- `total_amount` (Float, Required)
- `status` (String, Default: 'pending')
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Order Items Table
- `id` (Integer, Primary Key)
- `order_id` (Integer, Foreign Key)
- `product_id` (Integer, Foreign Key)
- `quantity` (Integer, Required)
- `price_at_time` (Float, Required)

## API Endpoints

### Products

#### Get All Products
- **GET** `/products`
- Returns a list of all products
- No authentication required

#### Get Single Product
- **GET** `/products/<product_id>`
- Returns details of a specific product
- No authentication required

#### Create Product
- **POST** `/products`
- Creates a new product
- Requires authentication
- Request body:
  ```json
  {
    "name": "Product Name",
    "description": "Product Description",
    "price": 29.99,
    "stock": 100,
    "image_url": "https://example.com/image.jpg"
  }
  ```

#### Update Product
- **PUT** `/products/<product_id>`
- Updates an existing product
- Requires authentication
- Request body: Same as create product, all fields optional

#### Delete Product
- **DELETE** `/products/<product_id>`
- Deletes a product
- Requires authentication

### Orders

#### Get All Orders
- **GET** `/orders`
- Returns a list of all orders
- Requires authentication

#### Create Order
- **POST** `/orders`
- Creates a new order
- Requires authentication
- Request body:
  ```json
  {
    "user_id": "discord_user_id",
    "total_amount": 99.99,
    "items": [
      {
        "product_id": 1,
        "quantity": 2,
        "price": 49.99
      }
    ]
  }
  ```

## Authentication

All protected endpoints require Discord authentication. The authentication token should be included in the request header:

```
Authorization: Bearer <token>
```

## Error Handling

All endpoints use the `@error_handler` decorator to provide consistent error responses. Common error responses include:

- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error 