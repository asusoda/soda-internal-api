from utils.config import Config
from pymongo import MongoClient

class DBManager():

    def __init__(self, config: Config) -> None:
        # Ensure the DB type is MongoDB
        if config.get_db_type() != "mongodb":
            raise ValueError("Only MongoDB is supported in this DBManager")

        # Prepare the MongoDB URI with proper authentication details
        db_uri = config.get_db_uri().replace("<password>", config.get_db_password())
        self.client = MongoClient(db_uri)
        self.db = self.client[config.get_db_name()]


    def create_collection(self, collection_name: str, options: dict = {}) -> str:
        """
        Create a new collection with the specified name.
        
        Args:
            collection_name (str): Name of the new collection.
            options (dict, optional): Additional options for the collection like 'capped', 'size', etc.
            
        Returns:
            str: The name of the created collection.
        
        Raises:
            CollectionInvalid: If the collection already exists.
        """
        self.db.create_collection(collection_name, **options)
        return collection_name

    def insert_one(self, collection_name: str, data: dict):
        """Insert a single document into the specified collection."""
        collection = self.db[collection_name]
        return collection.insert_one(data).inserted_id

    def find_one(self, collection_name: str, query: dict) -> dict:
        """Retrieve a single document from the specified collection based on the query."""
        collection = self.db[collection_name]
        return collection.find_one(query)

    def find(self, collection_name: str, query: dict) -> list:
        """Retrieve multiple documents from the specified collection based on the query."""
        collection = self.db[collection_name]
        return list(collection.find(query))
    
    def ping(self) -> bool:
        """
        Ping the MongoDB server.
        
        Returns:
            bool: True if the server is alive, False otherwise.
        """
        try:
            # The 'ping' command will return {} if the server is alive
            result = self.db.command("ping")
            return result == {'ok' : 1}
        except Exception as e:
            print(f"Error while pinging: {e}")
            return False


    def update_one(self, collection_name: str, query: dict, update_data: dict) -> int:
        """Update a single document in the specified collection."""
        collection = self.db[collection_name]
        result = collection.update_one(query, {"$set": update_data})
        return result.modified_count

    def delete_one(self, collection_name: str, query: dict) -> int:
        """Delete a single document from the specified collection."""
        collection = self.db[collection_name]
        result = collection.delete_one(query)
        return result.deleted_count

    def close(self):
        """Close the database connection."""
        self.client.close()

    def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection with the specified name exists.
        
        Args:
            collection_name (str): Name of the collection to check.
            
        Returns:
            bool: True if the collection exists, False otherwise.
        """
        return collection_name in self.db.list_collection_names()
    
    def add_category(self, name, description):
        """Adds a new category."""
        return self.categories_collection.insert_one({"name": name, "description": description}).inserted_id

    def add_question(self, category, question, answer, value, uuid):
        """Adds a new question."""
        data = {
            "category": category,
            "question": question,
            "answer": answer,
            "value": value,
            "uuid": uuid
        }
        return self.questions_collection.insert_one(data).inserted_id

    def get_questions_by_category(self, category_name):
        """Retrieve all questions from the specified category."""
        return list(self.questions_collection.find({"category": category_name}))