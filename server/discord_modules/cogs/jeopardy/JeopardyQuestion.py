import uuid
import json

class JeopardyQuestion:
    """
    Represents a single Jeopardy question.

    Attributes:
        category (str): The category of the question.
        question (str): The question text.
        answer (str): The answer to the question.
        value (int): The point value of the question.
        answered (bool): Whether the question has been answered.
        id (uuid.UUID): Unique identifier for the question.
    """

    def __init__(self, category, question, answer, value):
        self.category = category
        self.question = question
        self.answer = answer
        self.value = value
        self.answered = False
        self.revealed = False
        self.id = str(uuid.uuid4())

    def to_json(self):
        """
        Converts the JeopardyQuestion instance to a JSON-serializable dictionary.

        Returns:
            dict: A dictionary representation of the question.
        """
        return {
            "category": self.category,
            "question": self.question,
            "answer": self.answer,
            "value": self.value,
            "answered": self.answered,
            "id": self.id
        }
        