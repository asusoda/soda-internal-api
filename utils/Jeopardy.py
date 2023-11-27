from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
from utils.Team import Team
import uuid
import discord
class JeopardyQuestion():

    
    def __init__(self, category, question, answer, value):
        self.category = category
        self.question = question
        self.answer = answer
        self.value = value
        self.answered = False
        self.id = uuid.uuid4()
        

    def to_json(self):
        return {
            "category": self.category,
            "question": self.question,
            "answer": self.answer,
            "value": self.value,
            "answered": self.answered,
            "id": str(self.id)
        }
        
class JeopardyGame:
    def __init__(self, game_data):
        self.name = game_data['game']['name']
        self.description = game_data['game']['description']
        self.teams = self._create_teams(game_data['game']['teams'])
        self.players = []
        self.categories = game_data['game']['categories']
        self.per_category = game_data['game']['per_category']
        self.questions = self._create_questions(game_data['questions'])
        self.uuid = uuid.uuid4()
        self.is_announced = False
        self.is_started = False

    def _create_questions(self, questions_data):
        questions = {}
        for category, qs in questions_data.items():
            questions[category] = []
            for q in qs:
                question_obj = JeopardyQuestion(category, q['question'], q['answer'], q['value'])
                questions[category].append(question_obj)
        return questions
    
    def _create_teams(self, data):
        teams = []
        for team in data:
            teams.append(Team(team))

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
        
    def to_json(self):
        data  = {}
        data['game'] = {}
        data['game']['name'] = self.name
        data['game']['description'] = self.description
        data['game']['teams'] = self.teams
        data['game']['players'] = self.players
        data['game']['categories'] = self.categories
        data['game']['per_category'] = self.per_category
        data['game']['uuid'] = self.uuid
        data['questions'] = {}
        for category, questions in self.questions.items():
            data['questions'][category] = []
            for question in questions:
                data['questions'][category].append(question.to_json())

        return data
    
    def add_member_to_team(self, team_name, member):
        for team in self.teams:
            if team.name == team_name:
                team.add_member(member)
                return True
        return False
    
    def award_points(self, team_name, points):
        for team in self.teams:
            if team.name == team_name:
                team.add_points(points)
                return True
        return False


    def announce(self):
        self.is_announced = True

    def start(self):
        self.is_started = True

    def add_member(self, member : discord.Member):
        self.players.append(member)