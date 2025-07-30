import jwt
import datetime
import secrets
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class TokenManager:
    def __init__(self, algorithm="RS256") -> None:
        self.algorithm = algorithm
        self.private_key, self.public_key = self.generate_keys()
        self.blacklist = set()
        # Store refresh tokens with their metadata
        self.refresh_tokens = {}  # refresh_token -> {user_id, username, expires_at}

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

    def generate_token_pair(self, username, discord_id=None, access_exp_minutes=30, refresh_exp_days=7):
        """
        Generate both access token and refresh token.
        
        Args:
            username (str): The user's display name
            discord_id (str): The user's Discord ID (recommended for security)
            access_exp_minutes (int): Access token expiration time in minutes
            refresh_exp_days (int): Refresh token expiration time in days
            
        Returns:
            tuple: (access_token, refresh_token)
        """
        # Generate access token (short-lived)
        access_token = self.generate_token(username, discord_id, access_exp_minutes)
        
        # Generate refresh token (long-lived, stored securely)
        refresh_token = self.generate_refresh_token(username, discord_id, refresh_exp_days)
        
        return access_token, refresh_token

    def generate_token(self, username, discord_id=None, exp_minutes=60):
        """
        Generate a JWT token with username and optional discord_id.
        
        Args:
            username (str): The user's display name
            discord_id (str): The user's Discord ID (recommended for security)
            exp_minutes (int): Token expiration time in minutes
            
        Returns:
            str: JWT token
        """
        payload = {
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=exp_minutes),
            "username": username,
            "type": "access"  # Token type for security
        }
        
        # Add discord_id to payload if provided (more secure)
        if discord_id:
            payload["discord_id"] = str(discord_id)
            
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def generate_refresh_token(self, username, discord_id=None, exp_days=7):
        """
        Generate a refresh token and store it securely.
        
        Args:
            username (str): The user's display name
            discord_id (str): The user's Discord ID
            exp_days (int): Refresh token expiration time in days
            
        Returns:
            str: Refresh token
        """
        # Generate a cryptographically secure random token
        refresh_token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=exp_days)
        
        # Store refresh token metadata
        self.refresh_tokens[refresh_token] = {
            "username": username,
            "discord_id": str(discord_id) if discord_id else None,
            "expires_at": expires_at,
            "created_at": datetime.datetime.utcnow()
        }
        
        return refresh_token

    def refresh_access_token(self, refresh_token):
        """
        Generate a new access token using a valid refresh token.
        
        Args:
            refresh_token (str): The refresh token
            
        Returns:
            str: New access token, or None if refresh token is invalid
        """
        # Check if refresh token exists and is not expired
        if refresh_token not in self.refresh_tokens:
            return None
            
        token_data = self.refresh_tokens[refresh_token]
        
        # Check if refresh token is expired
        if datetime.datetime.utcnow() > token_data["expires_at"]:
            # Remove expired refresh token
            del self.refresh_tokens[refresh_token]
            return None
        
        # Generate new access token
        new_access_token = self.generate_token(
            username=token_data["username"],
            discord_id=token_data["discord_id"],
            exp_minutes=30  # Short-lived access token
        )
        
        return new_access_token

    def revoke_refresh_token(self, refresh_token):
        """
        Revoke a refresh token.
        
        Args:
            refresh_token (str): The refresh token to revoke
            
        Returns:
            bool: True if token was revoked, False if not found
        """
        if refresh_token in self.refresh_tokens:
            del self.refresh_tokens[refresh_token]
            return True
        return False

    def cleanup_expired_refresh_tokens(self):
        """
        Remove expired refresh tokens from storage.
        """
        current_time = datetime.datetime.utcnow()
        expired_tokens = [
            token for token, data in self.refresh_tokens.items()
            if current_time > data["expires_at"]
        ]
        
        for token in expired_tokens:
            del self.refresh_tokens[token]

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

    def retrieve_discord_id(self, token):
        """
        Retrieve discord_id from JWT token.
        
        Args:
            token (str): JWT token
            
        Returns:
            str: Discord ID if present in token, None otherwise
        """
        try:
            payload = jwt.decode(token, self.public_key, algorithms=[self.algorithm])
            return payload.get("discord_id")
        except jwt.ExpiredSignatureError:
            try:
                payload = jwt.decode(
                    token,
                    self.public_key,
                    algorithms=[self.algorithm],
                    options={"verify_exp": False},
                )
                return payload.get("discord_id")
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
        discord_id = self.retrieve_discord_id(token)
        return self.generate_token(username, discord_id)

    def genreate_app_token(self, name, app_name):
        payload = {
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=120),
            "name": name,
            "app_name": app_name,
        }
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def delete_token(self, token):
        self.blacklist.add(token)
