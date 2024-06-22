from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class JeopardyGame(Base):
    __tablename__ = 'jeopardy_game'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    teams = relationship('JeopardyTeam', back_populates='game')
    players = relationship('JeopardyPlayer', back_populates='game')
    categories = relationship('Category', back_populates='game')
    per_category = Column(Integer)
    uuid = Column(String)
    is_announced = Column(Boolean)
    is_started = Column(Boolean)
    messages = relationship('JeopardyMessage', back_populates='game')

    def __repr__(self):
        return f'<JeopardyGame(name={self.name}, description={self.description})>'

class JeopardyQuestion(Base):
    __tablename__ = 'jeopardy_question'

    id = Column(Integer, primary_key=True)
    question = Column(String)
    answer = Column(String)
    category_id = Column(Integer, ForeignKey('category.id'))
    category = relationship('Category', back_populates='questions')

    def __repr__(self):
        return f'<JeopardyQuestion(question={self.question}, answer={self.answer})>'
