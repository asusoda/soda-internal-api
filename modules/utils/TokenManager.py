import jwt
import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from modules.points.models import Session
from shared import db_connect


class TokenManager:
    def __init__(self, algorithm="RS256") -> None:
        self.algorithm = algorithm
        self.private_key, self.public_key = self.generate_keys()

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
        token = jwt.encode(payload, self.private_key, algorithm=self.algorithm)
        
        # Store session in database
        db = next(db_connect.get_db())
        try:
            session = Session(
                token=token,
                username=username,
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=exp_minutes)
            )
            db.add(session)
            db.commit()
        finally:
            db.close()
            
        return token

    def retrieve_username(self, token):
        try:
            db = next(db_connect.get_db())
            try:
                session = db.query(Session).filter_by(token=token).first()
                if session:
                    return session.username
                return None
            finally:
                db.close()
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
        try:
            # Check if token exists in database
            db = next(db_connect.get_db())
            try:
                session = db.query(Session).filter_by(token=token).first()
                if not session:
                    return False
                    
                # Check if token is expired
                if session.expires_at < datetime.datetime.utcnow():
                    return False
                    
                return True
            finally:
                db.close()
        except jwt.InvalidSignatureError:
            return False

    def is_token_expired(self, token):
        try:
            db = next(db_connect.get_db())
            try:
                session = db.query(Session).filter_by(token=token).first()
                if not session:
                    return True
                return session.expires_at < datetime.datetime.utcnow()
            finally:
                db.close()
        except jwt.ExpiredSignatureError:
            return True

    def refresh_token(self, token):
        db = next(db_connect.get_db())
        try:
            session = db.query(Session).filter_by(token=token).first()
            if not session:
                return None
                
            # Generate new token
            new_token = self.generate_token(session.username)
            
            # Delete old session
            db.delete(session)
            db.commit()
            
            return new_token
        finally:
            db.close()

    def generate_app_token(self, name, app_name):
        payload = {
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=120),
            "name": name,
            "app_name": app_name,
        }
        token = jwt.encode(payload, self.private_key, algorithm=self.algorithm)
        
        # Store app token in database
        db = next(db_connect.get_db())
        try:
            session = Session(
                token=token,
                username=name,
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=120),
                is_app_token=app_name
            )
            db.add(session)
            db.commit()
        finally:
            db.close()
            
        return token

    def delete_token(self, token):
        db = next(db_connect.get_db())
        try:
            session = db.query(Session).filter_by(token=token).first()
            if session:
                db.delete(session)
                db.commit()
        finally:
            db.close()
