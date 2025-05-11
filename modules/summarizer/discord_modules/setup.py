from modules.summarizer.discord_modules.cog import SummarizerCog

def setup_summarizer_cog(bot):
    """
    Register the summarizer cog with the Discord bot

    Args:
        bot: The Discord bot instance
    """
    # Remove any existing summarizer cogs
    for cog in bot.cogs:
        if cog.lower() == "summarizer":
            bot.remove_cog(cog)

    # Add the new cog
    summarizer_cog = SummarizerCog(bot)
    bot.add_cog(summarizer_cog)

    print(f"Registered commands: {[cmd.name for cmd in bot.application_commands]}")

    return True