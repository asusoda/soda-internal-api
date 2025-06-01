from modules.summarizer.discord_modules.cog import SummarizerCog
from modules.utils.logging_config import get_logger

# Get module logger
logger = get_logger("summarizer.setup")

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
            logger.debug(f"Removed existing cog: {cog}")

    # Add the new cog
    summarizer_cog = SummarizerCog(bot)
    bot.add_cog(summarizer_cog)

    logger.info(f"Registered summarizer commands: {[cmd.name for cmd in bot.application_commands]}")

    return True