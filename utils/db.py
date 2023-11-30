from utils.config import Config
from pymongo import MongoClient

class DBManager():

    def __init__(self, config: Config) -> None:
        # Ensure the DB type is MongoDB
        required_collections = ["staff", "games"]
        if config.get_db_type() != "mongodb":
            raise ValueError("Only MongoDB is supported in this DBManager")

        # Prepare the MongoDB URI with proper authentication details
        db_uri = config.get_db_uri().replace("<password>", config.get_db_password())
        self.client = MongoClient(db_uri)
        self.db = self.client[config.get_db_name()]
        self.access_tokens = {}
        for collection in required_collections:
            if not self.collection_exists(collection):
                self.create_collection(collection)

        self.auth_users_cache = self.load_auth_users_cache()

        
    def load_auth_users_cache(self) -> dict:
        """
        Load authorized users into cache from the database.

        Returns:
            dict: A dictionary of authorized users with user_id as key.
        """
        users = self.get_auth_users()
        return {user['user_id']: user for user in users}

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
    
    def add_or_update_game(self, game_data: dict) -> str:
        """
        Add a new game to the 'games' collection or update an existing one with the same name.
        
        Args:
            game_data (dict): The game data to be added or updated.
            
        Returns:
            str: The ID of the inserted or updated game.
        """
        collection = self.db['games']
        # Assuming 'name' is a unique identifier for each game
        query = {"game.name": game_data['game']['name']}
        existing_game = collection.find_one(query)

        if existing_game:
            # Update the existing game record
            result = collection.replace_one(query, game_data)
            return str(result.upserted_id) if result.upserted_id else existing_game['_id']
        else:
            # Insert a new game record
            return str(collection.insert_one(game_data).inserted_id)
        
    
    def get_game(self, game_name: str) -> dict:
        """
        Get the game with the specified name.
        
        Args:
            game_name (str): Name of the game to be retrieved.
            
        Returns:
            dict: The game data.
        """
        collection = self.db['games']
        query = {"game.name": game_name}
        return collection.find_one(query)
    
    def get_all_games(self) -> list:
        """
        Get all the games.
        
        Returns:
            list: List of all the games.
        """
        collection = self.db['games']
        data = list(collection.find())
        for game in data:
            game['_id'] = str(game['_id'])
        return data
    
    def delete_game(self, game_name: str) -> int:
        """
        Delete the game with the specified name.
        
        Args:
            game_name (str): Name of the game to be deleted.
            
        Returns:
            int: Number of games deleted.
        """
        collection = self.db['games']
        query = {"game.name": game_name}
        result = collection.delete_one(query)
        return result.deleted_count
    

        
    def add_auth_user(self, user_id: str):
        """
        Add a new user to the 'staff' collection.
        
        Args:
            user_id (str): ID of the user to be added.
        """
        collection = self.db['staff']
        query = {"user_id": user_id}
        existing_user = collection.find_one(query)
        if not existing_user:
            collection.insert_one({"user_id": user_id})
            self.auth_users_cache[user_id] = {"user_id": user_id}

    def remove_auth_user(self, user_id: str):
        """
        Remove a user from the 'staff' collection.
        
        Args:
            user_id (str): ID of the user to be removed.
        """
        collection = self.db['staff']
        query = {"user_id": user_id}
        collection.delete_one(query)
        self.auth_users_cache.pop(user_id, None)

    def get_auth_users(self) -> list:
        """
        Get all the authenticated users.
        
        Returns:
            list: List of all the authenticated users.
        """
        collection = self.db['staff']
        data = list(collection.find())
        for user in data:
            user['_id'] = str(user['_id'])

        return data
    
    def is_user_authorized(self, user_id: str) -> bool:
        """
        Check if a user is authorized using cache.

        Args:
            user_id (str): ID of the user to be checked.

        Returns:
            bool: True if user is authorized, False otherwise.
        """
        return user_id in self.auth_users_cache
    

    def bind_access_token(self, user_id: str, token: str):
        """
        Bind an access token to a user.

        Args:
            user_id (str): ID of the user.
            token (str): The access token.
        """
        self.access_tokens[token] = user_id
        