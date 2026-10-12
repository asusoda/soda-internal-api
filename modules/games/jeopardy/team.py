from typing import (
    Any,
)

import discord


class Team:
    def __init__(self, name: str, role: discord.Role | None = None) -> None:
        self.name = name
        self.role = role
        self.members: list[discord.Member | discord.User] = []
        self.score = 0

    def __str__(self) -> str:
        return f"Team(name={self.name}, members={self.members}, score={self.score})"

    def attach_role(self, role: discord.Role) -> None:
        if self.role is None:
            self.role = role
        else:
            raise Exception("Role already attached to team")

    def add_points(self, points: int) -> None:
        points = int(points)
        self.score += points

    def remove_points(self, points: int) -> None:
        self.score -= points

    def getScore(self) -> int:
        return self.score

    def add_team_member(self, member: discord.Member | discord.User) -> None:
        self.members.append(member)

    def to_json(self) -> dict[str, Any]:
        """The team as JSON. Members are their display names."""
        return {"name": self.name, "members": [member.display_name for member in self.members], "score": self.score}

    def get_name(self) -> str:
        return self.name
