import os
class Config():

    def __init__(self) -> None:
        # try:
        #     self.secret_key = os.environ['SECRET_KEY']
        #     self.client_id = os.environ['CLIENT_ID']
        #     self.client_secret = os.environ['CLIENT_SECRET']
        #     self.redirect_uri = os.environ['REDIRECT_URI']
        #     self.bot_token = os.environ['BOT_TOKEN']
        #     self.db_type = os.environ['DB_TYPE']
        #     self.db_uri = os.environ['DB_URI']
        #     self.db_name = os.environ['DB_NAME']
        #     self.db_user = os.environ['DB_USER']
        #     self.db_password = os.environ['DB_PASSWORD']
        # except KeyError as e:
        #     print(f"Missing environment variable: {e}")
        #     exit(1)\
        self.SECRET_KEY='Gju8sO9y4F8WtU1O'
        self.CLIENT_ID=1153940272867180594
        self.CLIENT_SECRET="_2DJ787FBtThsR9oaPI3Qx3MsB4rNwdN"
        self.REDIRECT_URI='http://127.0.0.1:5000/callback'
        self.BOT_TOKEN="MTE1Mzk0MDI3Mjg2NzE4MDU5NA.G_KwRB.oQhPJQxaVWH97rpAVwwSFpjEUuzc-Cc_Jyn5Us"
        self.DB_TYPE='mongodb'
        self.DB_URI="mongodb+srv://soda_bot:<password>@cluster0.j5dxukh.mongodb.net/?retryWrites=true&w=majority"
        self.DB_NAME="soda-bot"
        self.DB_USER="soda_bot"
        self.DB_PASSWORD="ovBj2HHnF6CYsWgw"
        

    def get_secret_key(self):
        return self.SECRET_KEY
    
    def get_client_id(self):
        return self.CLIENT_ID
    
    def get_client_secret(self):
        return self.CLIENT_SECRET
    
    def get_redirect_uri(self):
        return self.REDIRECT_URI
    
    def get_bot_token(self):
        return self.BOT_TOKEN
    
    def get_db_type(self):
        return self.DB_TYPE
    
    def get_db_uri(self):
        return self.DB_URI
    
    def get_db_name(self):
        return self.DB_NAME
    
    def get_db_user(self):
        return self.DB_USER
    
    def get_db_password(self):
        return self.DB_PASSWORD
    
    
   