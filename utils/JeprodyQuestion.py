import uuid

class JeopardyQuestion():

    
    def __init__(self, category, question, answer, value):
        self.category = category
        self.question = question
        self.answer = answer
        self.value = value
        self.answered = False
        self.id = uuid.uuid4()
        