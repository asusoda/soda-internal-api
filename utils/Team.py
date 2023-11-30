from typing import List, Dict, Tuple, Set, Union, Optional, Any, Callable, TypeVar, Generic
class Team():

    def __init__(self, name : str ) -> None:
        self.name = name
        self.members = []
        self.score = 0


    def __str__(self) -> str:
        return f"Team(name={self.name}, members={self.members}, score={self.score})"
    
    def addPoints(self, points : int) -> None:
        self.score += points

    def removePoints(self, points : int) -> None:
        self.score -= points

    def getScore(self) -> int:
        return self.score
    
    def add_team_member(self, member_id : int) -> None:
        self.members.append(member_id)

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "members": self.members,
            "score": self.score
        }
    def get_name(self) -> str:
        return self.name
    