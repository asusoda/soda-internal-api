from typing import Any
import uuid

from utils.JeprodyQuestion import JeopardyQuestion
class JeopardyGame:
    def __init__(self, game_data):
        self.name = game_data['game']['name']
        self.description = game_data['game']['description']
        self.teams = game_data['game']['teams']
        self.players = game_data['game']['players']
        self.categories = game_data['game']['categories']
        self.per_category = game_data['game']['per_category']
        self.questions = self._create_questions(game_data['questions'])

    def _create_questions(self, questions_data):
        questions = {}
        for category, qs in questions_data.items():
            questions[category] = []
            for q in qs:
                question_obj = JeopardyQuestion(category, q['question'], q['answer'], q['value'])
                questions[category].append(question_obj)
        return questions

    def get_question(self, category, value):
        for q in self.questions[category]:
            if q.value == value and not q.answered:
                return q
        return None

    def mark_question_as_answered(self, category, value):
        question = self.get_question(category, value)
        if question:
            question.answered = True
            return True
        return False
       
    def get(self, name):
        if name in ['name', 'description', 'teams', 'players', 'categories', 'per_category', 'questions']:
            return getattr(self, name)
        else:
            raise AttributeError(f'Attribute {name} does not exist')
        
    def toJSON(self):
        data  = {}
        data['game'] = {}
        data['game']['name'] = self.name
        data['game']['description'] = self.description
        data['game']['teams'] = self.teams
        data['game']['players'] = self.players
        data['game']['categories'] = self.categories
        data['game']['per_category'] = self.per_category
        data['game']['uuid'] = str(uuid.uuid4())
        data['questions'] = {}
        