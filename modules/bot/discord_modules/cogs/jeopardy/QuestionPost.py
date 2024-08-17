import discord
from discord_modules.cogs.jeopardy.JeopardyQuestion import JeopardyQuestion


class QuestionPost(discord.ui.View):
    def __init__(self, question: JeopardyQuestion):
        super().__init__()
        self.question = question

    @discord.ui.button(label="Buzz In", style=discord.ButtonStyle.blurple)
    async def button_callback(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        user = interaction.user
        await interaction.response.send_message(f"<@{user.id}> buzzed in!")
        button.disabled = True
        return user
