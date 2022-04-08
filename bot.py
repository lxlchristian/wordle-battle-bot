"""
Telegram bot that hosts multiplayer Wordle games.
Functionality is inspired by multiplayer Tetris.
Deployed using Heroku.
"""

import logging
import os
from multiplayer import BotManager, join, about, how_to_play, example, START_LINK, JOIN_CALLBACK
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler
)

PORT = int(os.environ.get('PORT', 8443))
TOKEN = os.environ.get("TOKEN")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


def error(update, context):
    """Log errors caused by updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main() -> None:
    """Run the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Initialise bot manager to manage simultaneous games and game data
    bot_manager = BotManager()

    # Initiate the game
    dispatcher.add_handler(CommandHandler("about", about))
    dispatcher.add_handler(CommandHandler("help", how_to_play))
    dispatcher.add_handler(CommandHandler("example", example))
    dispatcher.add_handler(CommandHandler("startgame", bot_manager.new_game))
    dispatcher.add_handler(CommandHandler("start", join, filters=Filters.regex(START_LINK)))
    dispatcher.add_handler(CallbackQueryHandler(bot_manager.add_player, pattern=JOIN_CALLBACK))
    dispatcher.add_handler(CommandHandler("players", bot_manager.show_players))
    dispatcher.add_handler(CommandHandler("begin", bot_manager.begin_game))
    dispatcher.add_handler(MessageHandler(Filters.regex("^[a-zA-Z]{5}$"), bot_manager.guess_callback))
    dispatcher.add_handler(CommandHandler("end", bot_manager.force_end))

    # Add error handler
    dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_webhook(listen="0.0.0.0",
                          port=int(PORT),
                          url_path=TOKEN)
    updater.bot.setWebhook('https://radiant-sea-67615.herokuapp.com/' + TOKEN)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
