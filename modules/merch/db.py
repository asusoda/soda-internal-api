import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from modules.merch.models import Base
from modules.utils.logging_config import get_logger

# Get logger
logger = get_logger("merch.db")

class StoreConnector:
    """Database connector for the Storefront/Merchandise system"""
    
    def __init__(self, db_url="sqlite:///./data/storefront.db") -> None:
        """Initialize the database connector
        
        Args:
            db_url (str): Database connection URL
        """
        self.SQLALCHEMY_DATABASE_URL = db_url
        self.engine = create_engine(
            self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self._check_and_create_tables()
        logger.info(f"Storefront database initialized at {db_url}")

    def _check_and_create_tables(self):
        """Check if the database file exists and create tables if it doesn't"""
        db_path = self.SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
        
        # Make sure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=self.engine)
        logger.debug("Ensured storefront database tables exist")

    def get_db(self):
        """Get a database session
        
        Yields:
            Session: A SQLAlchemy session
        """
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def create_product(self, db, product):
        """Create a new product
        
        Args:
            db: Database session
            product: Product object to create
            
        Returns:
            Product: The created product
        """
        db.add(product)
        db.commit()
        db.refresh(product)
        return product

    def create_order(self, db, order, order_items):
        """Create a new order with items
        
        Args:
            db: Database session
            order: Order object to create
            order_items: List of OrderItem objects
            
        Returns:
            Order: The created order
        """
        db.add(order)
        db.flush()  # Flush to get the order ID
        
        for item in order_items:
            item.order_id = order.id
            db.add(item)
            
        db.commit()
        db.refresh(order)
        return order
        
    def get_all_products(self, db):
        """Get all products
        
        Args:
            db: Database session
            
        Returns:
            List[Product]: List of all products
        """
        from modules.merch.models import Product
        return db.query(Product).all()
    
    def get_product(self, db, product_id):
        """Get a product by ID
        
        Args:
            db: Database session
            product_id: Product ID
            
        Returns:
            Product: The product with the given ID
        """
        from modules.merch.models import Product
        return db.query(Product).filter(Product.id == product_id).first()
    
    def get_all_orders(self, db):
        """Get all orders
        
        Args:
            db: Database session
            
        Returns:
            List[Order]: List of all orders
        """
        from modules.merch.models import Order
        return db.query(Order).all() 