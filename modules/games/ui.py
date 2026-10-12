from typing import Protocol

import discord

from modules.games.jeopardy.question import JeopardyQuestion


class GameCogProtocol(Protocol):
    """Protocol defining the interface that UI components need from GameCog.

    This decouples UI components from the concrete GameCog implementation,
    avoiding circular imports while maintaining type safety.
    """

    question_post: dict

    def get_member_role(self, member: discord.User | discord.Member | None) -> discord.Role | None:
        """Get the game role assigned to a member."""
        pass


class QuestionPost(discord.ui.View):
    def __init__(
        self,
        question: JeopardyQuestion,
        voice: discord.StageChannel,
        cog: GameCogProtocol,
        question_uuid: str | None,
        avoid,
    ):
        """
        Initializes the QuestionPost instance.

        Args:
            question (JeopardyQuestion): The question to display.
            voice (discord.StageChannel): The voice channel to move the user to.
            cog (GameCogProtocol): Any object implementing the GameCogProtocol interface.
            question_uuid (Optional[str]): The UUID of the question.
            avoid (Optional[str]): The roles to avoid.
        """
        super().__init__(timeout=None)
        self.question = question
        self.voice = voice
        self.cog = cog
        self.avoid = avoid
        self.question_uuid = question_uuid

    @discord.ui.button(label="Buzz In", style=discord.ButtonStyle.blurple)
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        user = interaction.user
        # Only a server member can join the stage
        if not isinstance(user, discord.Member):
            await interaction.response.send_message("Only server members can buzz in!", ephemeral=True)
            return
        member_role = self.cog.get_member_role(user)
        if member_role in self.avoid:
            await interaction.response.send_message("You are not allowed to buzz in!", ephemeral=True)
        else:
            self.cog.question_post[self.question_uuid]["rolesAnswered"].append(member_role)
            button.disabled = True
            button.label = f"{user.name} buzzed in!"
            await interaction.response.edit_message(view=self)
            await user.move_to(self.voice)
            await user.request_to_speak()


class AnsweredQuestion(discord.ui.View):
    def __init__(self, question: JeopardyQuestion, answer: str):
        """
        Initializes the AnsweredQuestion instance.

        Args:
            question (JeopardyQuestion): The question that was answered.
            answer (str): The answer to the question.
        """
        super().__init__(timeout=None)
        self.question = question
        self.answer = answer
        self.add_item(discord.ui.Button(label="Reveal Answer", style=discord.ButtonStyle.blurple))

    @discord.ui.button(label="Reveal Answer", style=discord.ButtonStyle.blurple)
    async def reveal_answer(self, button: discord.ui.Button, interaction: discord.Interaction):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"The answer is: {self.answer}", ephemeral=True)
