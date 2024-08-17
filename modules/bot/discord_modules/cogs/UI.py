import discord
from discord.ext import commands
from discord.ui import Button, View
from discord.ext.commands import Cog
from typing import Optional, List
import random
from modules.bot.discord_modules.cogs.jeopardy.JeopardyQuestion import JeopardyQuestion
from modules.bot.discord_modules.cogs.jeopardy.Jeopardy import JeopardyGame
from modules.bot.discord_modules.cogs import GameCog


class QuestionPost(discord.ui.View):
    def __init__(
        self,
        question: JeopardyQuestion,
        voice: discord.StageChannel,
        cog: GameCog,
        question_uuid: Optional[str],
        avoid,
    ):
        """
        Initializes the QuestionPost instance.

        Args:
            question (JeopardyQuestion): The question to display.
            voice (discord.StageChannel): The voice channel to move the user to.
            cog (GameCog): The GameCog instance.
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
    async def button_callback(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        member_role = self.cog.get_member_role(interaction.user)
        if member_role in self.avoid:
            await interaction.response.send_message(
                "You are not allowed to buzz in!", ephemeral=True
            )
        else:
            self.cog.question_post[self.question_uuid]["rolesAnswered"].append(
                member_role
            )
            button.disabled = True
            user = interaction.user
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
        self.add_item(
            discord.ui.Button(label="Reveal Answer", style=discord.ButtonStyle.blurple)
        )

    @discord.ui.button(label="Reveal Answer", style=discord.ButtonStyle.blurple)
    async def reveal_answer(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"The answer is: {self.answer}", ephemeral=True)
