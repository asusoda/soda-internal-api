import jwt
import datetime

class TokenManager:
    def __init__(self, private_key, public_key, algorithm='RS256'):
        self.private_key = self._load_private_key(private_key)
        self.public_key = self._load_public_key(public_key)
        self.algorithm = algorithm


  
    def generate_token(self, payload, exp_minutes=60):
        expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=exp_minutes)
        payload.update({'exp': expiration})
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def decode_token(self, token):
        return jwt.decode(token, self.public_key, algorithms=[self.algorithm])

    def is_token_expired(self, token):
        try:
            self.decode_token(token)
            return False
        except jwt.ExpiredSignatureError:
            return True

    # Additional methods can be added as needed, such as token refresh logic
