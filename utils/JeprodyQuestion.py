class JeprodayQuestion:
    def __init__(self, category, question, answer, value, uuid):
        self.category = category
        self.question = question
        self.answer = answer
        self.value = value
        self.answered = False