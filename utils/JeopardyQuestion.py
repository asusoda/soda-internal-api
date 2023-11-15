import uuid

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
        