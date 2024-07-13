from typing import List, Dict, Tuple, Set, Union, Optional, Any, Callable, TypeVar, Generic
import discord
class Team():

    def __init__(self, name : str, role: Optional[discord.Role] = None) -> None:
        if role is None:
            self.name = name
            self.role = None
            self.members = []
            self.score = 0
        else:
            self.name = name
            self.role = role
            self.members = []
            self.score = 0


    def __str__(self) -> str:
        return f"Team(name={self.name}, members={self.members}, score={self.score})"
    
    def attach_role(self, role : discord.role) -> None:
        if self.role is None:
            self.role = role
        else:
            raise Exception("Role already attached to team")

    def add_points(self, points : int) -> None:
        points = int(points)
        self.score += points

    def remove_points(self, points : int) -> None:
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
    