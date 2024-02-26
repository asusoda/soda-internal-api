from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
from  discord_modules.cogs.jeopardy.Team import Team
from discord_modules.cogs.jeopardy.JeopardyQuestion import JeopardyQuestion
import uuid
import discord

import uuid
import discord

class JeopardyGame:
    """
    Manages a Jeopardy-style game in a Discord environment. It handles game initialization,
    team and player management, question handling, and game state tracking.

    Attributes:
        name (str): The name of the Jeopardy game.
        description (str): A description of the game.
        teams (list): A list of Team objects participating in the game.
        players (list): A list of Discord Members participating in the game.
        categories (list): Categories of questions in the game.
        per_category (int): Number of questions per category.
        questions (dict): A dictionary mapping categories to their respective questions.
        uuid (uuid.UUID): A unique identifier for the game.
        is_announced (bool): Flag indicating if the game has been announced.
        is_started (bool): Flag indicating if the game has started.
    """

    def __init__(self, game_data):
        """
        Initializes the JeopardyGame instance with provided game data.

        Args:
            game_data (dict): Data required to set up the game.
        """
        self.name = game_data['game']['name']
        self.description = game_data['game']['description']
        self.teams = self._create_teams(game_data['game']['teams'])
        self.players = []
        self.categories = game_data['game']['categories']
        self.category_name = ()
        self.per_category = game_data['game']['per_category']
        self.questions = self._create_questions(game_data['questions'])
        self.uuid = uuid.uuid4()
        self.is_announced = False
        self.is_started = False
        self.messages = []


    def to_json(self):
        """
        Converts the JeopardyGame instance to a JSON-serializable dictionary.

        Returns:
            dict: A dictionary representation of the game.
        """
        quest = {}
        for question in self.questions:
            if question.category not in quest:
                quest[question.category] = []
            quest[question.category].append(question.to_json())

        return {
            "game": {
                "name": self.name,
                "description": self.description,
                "teams": [team.to_json() for team in self.teams],
                "categories": self.categories,
                "per_category": self.per_category,
                "uuid": str(self.uuid),
                "announced": self.is_announced,
                "started": self.is_started
            },
            "questions": quest
        }

    def _create_questions(self, questions_data):
        """
        Creates and organizes JeopardyQuestion objects from provided data.

        Args:
            questions_data (dict): Question data categorized by their categories.

        Returns:
            dict: Organized questions by category.
        """
        print(questions_data)
        queations = []
        for categoory in questions_data.keys():
            for question in questions_data[categoory]:
                queations.append(JeopardyQuestion(categoory, question['question'], question['answer'], question['value']))
                self.category_name = categoory
        return queations

    def _create_teams(self, data):
        """
        Creates Team objects from provided data.

        Args:
            data (list): Data for creating teams.

        Returns:
            list: A list of initialized Team objects.
        """
        return [Team(team_data) for team_data in data]

    def get_question(self, uuid):
        """
        Retrieves an unanswered question of a specific value from a given category.

        Args:
            category (str): The category of the question.
            value (int): The value of the question.

        Returns:
            JeopardyQuestion or None: The question object if found, otherwise None.
        """
        for questions in self.questions.values():
            for question in questions:
                if question.id == uuid:
                    return question
        return None
    def mark_question_as_answered(self, category, value):
        """
        Marks a question as answered in a specific category and value.

        Args:
            category (str): The category of the question.
            value (int): The value of the question.

        Returns:
            bool: True if the question was successfully marked as answered, False otherwise.
        """
        question = self.get_question(category, value)
        if question:
            question.answered = True
            return True
        return False

    def add_member_to_team(self, team_name, member):
        """
        Adds a Discord member to a specified team.

        Args:
            team_name (str): The name of the team.
            member (discord.Member): The Discord member to add.

        Returns:
            bool: True if the member was successfully added, False otherwise.
        """
        team = next((team for team in self.teams if team.name == team_name), None)
        if team:
            team.add_member(member)
            return True
        return False

    def award_points(self, team_name, points):
        """
        Awards points to a specified team.

        Args:
            team_name (str): The name of the team.
            points (int): The number of points to award.

        Returns:
            bool: True if points were successfully awarded, False otherwise.
        """
        team = next((team for team in self.teams if team.name == team_name), None)
        if team:
            team.add_points(points)
            return True
        return False

    def announce(self):
        """
        Marks the game as announced.
        """
        self.is_announced = True

    def start(self):
        """
        Marks the game as started.
        """
        self.is_started = True

    def add_member(self, member: discord.Member):
        """
        Adds a player
        """
        self.players.append(member)

    def get_question_by_uuid(self, uuid: str) -> Optional[JeopardyQuestion]:
        """
        Retrieves a question by its UUID.

        Args:
            uuid (uuid.UUID): The UUID of the question.

        Returns:
            JeopardyQuestion or None: The question object if found, otherwise None.
        """
        for question in self.questions:
            if question.id == uuid:
                return question
        return None
    
    def answer_question(self, uuid: str) -> bool:
        """
        Marks a question as answered in a specific category and value.

        Args:
            uuid (uuid.UUID): The UUID of the question.

        Returns:
            bool: True if the question was successfully marked as answered, False otherwise.
        """
        question = self.get_question_by_uuid(uuid)
        if question:
            question.answered = True
            return True, question
        return False
    
    def get_winners(self) -> List[str]:
        """
        Retrieves the winning team(s).

        Returns:
            list: A list of winning Team objects.
        """
        winners = []
        max_points = max([team.points for team in self.teams])
        for team in self.teams:
            if team.points == max_points:
                for member in team.members:
                    winners.append(member)


    def attach_roles(self, roles: list[discord.Role]) -> None:
        """
        Attaches roles to teams
        """
        for team in self.teams:
            for role in roles:
                if team.name == role.name: 
                    team.attach_role(role)
                    
    def get_members(self):
        """
        Retrieves the members of the game
        """
        return self.players
    
    def get_board(self):
        """
        Retrieves the board
        """
        data = {}
        for question in self.questions:
            if question.category not in data.keys():
                data[question.category] = []
            if not question.answered:
                data[question.category].append(question.value)
            else:
                data[question.category].append("XXXX")

        return data
    
    def get_questions_in_sorted_categories_and_by_points(self):
        """
        Retrieves the questions in sorted categories and by points
        """
        data = {}
        for question in self.questions:
            if question.category not in data.keys():
                data[question.category] = []
            if not question.answered:
                data[question.category].append(question.value)
            else:
                data[question.category].append("XXXX")

        return data