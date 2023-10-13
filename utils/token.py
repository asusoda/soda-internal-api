import jwt
import datetime
from quart import request, jsonify

class JWTUtility:
    def __init__(self, secret_key):
        self.SECRET_KEY = secret_key

    def generate_token(self, user_id):
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
            'iat': datetime.datetime.utcnow(),
            'sub': user_id
        }
        return jwt.encode(payload, self.SECRET_KEY, algorithm='HS256').decode('utf-8')

    def decode_token(self, token):
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=['HS256'])
            return payload['sub']
        except jwt.ExpiredSignatureError:
            return None  # Token has expired
        except jwt.InvalidTokenError:
            return None  # Invalid token

    async def require_token(self):
        token = request.headers.get('Authorization').split("Bearer ")[1]
        user_id = self.decode_token(token)
        if user_id is None:
            return jsonify({"message": "Invalid token", "status": "error"}), 401
