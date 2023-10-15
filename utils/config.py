import os
class Config():

    def __init__(self) -> None:
        try:
            self.secret_key = os.environ['SECRET_KEY']
            self.client_id = os.environ['CLIENT_ID']
            self.client_secret = os.environ['CLIENT_SECRET']
            self.redirect_uri = os.environ['REDIRECT_URI']
            self.bot_token = os.environ['BOT_TOKEN']
            self.db_type = os.environ['DB_TYPE']
            self.db_uri = os.environ['DB_URI']
            self.db_name = os.environ['DB_NAME']
            self.db_user = os.environ['DB_USER']
            self.db_password = os.environ['DB_PASSWORD']
        except KeyError as e:
            print(f"Missing environment variable: {e}")
            exit(1)
        

    def get_secret_key(self):
        return self.secret_key
    
    def get_client_id(self):
        return self.client_id
    
    def get_client_secret(self):
        return self.client_secret
    
    def get_redirect_uri(self):
        return self.redirect_uri
    
    def get_bot_token(self):
        return self.bot_token
    
    def get_db_type(self):
        return self.db_type
    
    def get_db_uri(self):
        return self.db_uri
    
    def get_db_name(self):
        return self.db_name
    
    def get_db_user(self):
        return self.db_user
    
    def get_db_password(self):
        return self.db_password
    
    
   
