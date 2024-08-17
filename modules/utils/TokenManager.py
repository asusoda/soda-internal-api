import jwt
import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class TokenManager:
    def __init__(self, algorithm="RS256") -> None:
        self.algorithm = algorithm
        self.private_key, self.public_key = self.generate_keys()
        self.blacklist = set()

    def generate_keys(self):
        # Generate a private RSA key
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # Generate the corresponding public key
        public_key = private_key.public_key()

        # Serialize private key to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Serialize public key to PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return private_pem.decode("utf-8"), public_pem.decode("utf-8")

    def generate_token(self, username, exp_minutes=60):
        payload = {
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=exp_minutes),
            "username": username,
        }
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def retrieve_username(self, token):
        try:
            payload = jwt.decode(token, self.public_key, algorithms=[self.algorithm])
            return payload.get("username")
        except jwt.ExpiredSignatureError:
            try:
                payload = jwt.decode(
                    token,
                    self.public_key,
                    algorithms=[self.algorithm],
                    options={"verify_exp": False},
                )
                return payload.get("username")
            except jwt.DecodeError:
                return None

    def decode_token(self, token):
        return jwt.decode(token, self.public_key, algorithms=[self.algorithm])

    def get_username_from_expiration(self, token):
        try:
            payload = jwt.decode(token, self.public_key, algorithms=[self.algorithm])
            return payload["username"]
        except jwt.InvalidTokenError:
            return None

    def is_token_valid(self, token):
        if token in self.blacklist:
            return False
        try:
            self.decode_token(token)
            return True
        except jwt.InvalidSignatureError:
            return False

    def is_token_expired(self, token):
        try:
            self.decode_token(token)
            return False
        except jwt.ExpiredSignatureError:
            return True

    def refresh_token(self, token):
        username = self.retrieve_username(token)
        return self.generate_token(username)
    
    def genreate_app_token(self, name, app_name):
        payload = {
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=120),
            "name": name,
            "app_name": app_name,
        }
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)
    
    def delete_token(self, token):
        self.blacklist.add(token)
    
