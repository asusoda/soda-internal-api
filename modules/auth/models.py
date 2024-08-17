from shared import base
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, JSON


class Token(base):
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True)
    token_type = Column(String)
    username = Column(String)

    def __repr__(self):
        return f"<Token(token_type={self.token_type}, username={self.username})>"
