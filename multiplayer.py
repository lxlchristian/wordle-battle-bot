import telegram.error
from commands import WordManager
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from telegram.utils import helpers

MAX_PLAYERS = 8
PLAYER_CAPACITY_RATIO = [0, 5, 6, 7, 7, 8, 8, 9, 9]
TIMEOUT_SECS = 10 * 60
TIME_LIMIT = 30
STATUS_INTERVAL = 30
JOIN_CALLBACK = "join-callback"
START_LINK = "join-the-game"


# ----------- BOT MANAGER ----------

class BotManager:
    """Class to manage the simultaneous handling of games in multiple group chats"""
    def __init__(self):
        self.game_managers = []

    def new_game(self, update: Update, context: CallbackContext):
        """Adds a new game manager to the list of game managers, then accesses it and starts a game"""
        # Check if there is already a game in this group, or if the user attempted to start a game in a private chat
        for game in self.game_managers:
            if update.effective_chat.id == game.group_chat_id:
                update.message.reply_text("Sorry, you can't start a game when there is one already running!")
                return

        if update.effective_chat.type == "private":
            update.message.reply_text("Sorry, you can't start a game when not in a group chat!")
            return

        game_manager = GameManager()
        game_manager.start_game(update, context)

        # Schedule the game to end automatically after 10 minutes of being started and not begun
        context.job_queue.run_once(game_manager.timeout, TIMEOUT_SECS, name=f"timeout{game_manager}")
        context.job_queue.run_once(self.timeout_check, TIMEOUT_SECS + 1, context=game_manager,
                                   name=f"timeout{game_manager}")

        # Append to the list of game managers
        self.game_managers.append(game_manager)
        print(self.game_managers)

    def timeout_check(self, context: CallbackContext):
        """Removes a timed out game from the list of game managers after 10 minutes"""
        game_manager = context.job.context
        if game_manager.game_has_ended:
            try:
                self.game_managers.remove(game_manager)

        # In the case where the game has already been removed from the list via force end
            except ValueError:
                return

    def matching_group(self, update: Update, context: CallbackContext):
        """Identifies the index of the game manager which this update should be performed in"""
        current_chat_id = update.effective_chat.id
        # Check that the current chat id either belongs to a member of the group, or is the group chat id itself
        for game_manager in self.game_managers:
            bot = context.bot
            try:
                bot.get_chat_member(game_manager.group_chat_id, current_chat_id)
                user_is_in_group = True

            except telegram.error.BadRequest:
                user_is_in_group = False

            if current_chat_id == game_manager.group_chat_id or user_is_in_group:
                return self.game_managers.index(game_manager)

    # The following functions search for the matching game and execute the function in the given word manager
    def add_player(self, update: Update, context: CallbackContext):
        game_index = self.matching_group(update, context)
        if game_index is not None:
            self.game_managers[game_index].add_player(update, context)

    def show_players(self, update: Update, context: CallbackContext):
        game_index = self.matching_group(update, context)
        if game_index is not None:
            self.game_managers[game_index].show_players(update, context)

    def begin_game(self, update: Update, context: CallbackContext):
        game_index = self.matching_group(update, context)
        if game_index is not None:
            self.game_managers[game_index].begin_game(update, context)

    def guess_callback(self, update: Update, context: CallbackContext):
        game_index = self.matching_group(update, context)
        if game_index is not None:
            self.game_managers[game_index].guess_callback(update, context)
            if self.game_managers[game_index].game_has_ended:
                self.game_managers.pop(game_index)

    def force_end(self, update: Update, context: CallbackContext):
        game_index = self.matching_group(update, context)
        if game_index is not None:
            self.game_managers[game_index].force_end(update, context)
            if self.game_managers[game_index].game_has_ended:
                self.game_managers.pop(game_index)


# ----------- GAME START COMMANDS ----------

def join(update: Update, context: CallbackContext):
    """After being directed to the private chat"""
    update.message.reply_text(
        "⬇️ Click below to join the game ⬇️",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="Join", callback_data=JOIN_CALLBACK)]]
        ),
    )


# ----------- GAME MANAGER ----------

class GameManager:
    """Class to manage the start and end of the game, and the players with their individual word managers"""
    def __init__(self):
        self.game_is_on = self.game_has_begun = self.game_has_ended = False
        self.single_player = False
        self.group_chat_id = 0
        self.group_member_ids = []
        self.current_players = []
        self.all_player_ids = []
        self.word_managers = {}
        self.word_capacity = 0

    def reset(self):
        """Reset the game manager for the next game"""
        self.__init__()

    def message_all(self, message: str, context: CallbackContext):
        """Helper function for sending a message to everyone in the game"""
        for chat in self.all_player_ids:
            context.bot.send_message(chat_id=chat, text=message)

    def start_game(self, update: Update, context: CallbackContext):
        """Start the game and ask users to join the game by redirecting them to a private chat."""
        self.game_is_on = True
        self.group_chat_id = update.effective_chat.id

        bot = context.bot
        url = helpers.create_deep_linked_url(bot.username, payload=START_LINK)

        text = "Welcome to Wordle Battle! Click to join the game, or type /help to learn how to play!"
        keyboard = InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(text="Join Game", url=url)
        )
        update.message.reply_text(text, reply_markup=keyboard)

    def add_player(self, update: Update, context: CallbackContext):
        """Add a player when a user clicks inline Join button"""
        user = update.effective_user

        if not self.game_is_on:
            context.bot.send_message(chat_id=update.effective_chat.id, text="There is no game currently running.")
            return

        if self.game_has_begun:
            context.bot.send_message(chat_id=update.effective_chat.id, text="You can't join now, the game has already begun!")
            return

        if user in self.current_players:
            context.bot.send_message(chat_id=update.effective_chat.id, text="You're already in the game!")
            return

        self.current_players.append(user)
        self.all_player_ids.append(user.id)

        self.message_all(context=context, message=f"{user.name} joined the game.")
        self.show_players(update, context)

        if len(self.current_players) == MAX_PLAYERS:
            self.start_game(update, context)

    def show_players(self, update: Update, context: CallbackContext):
        """Command to show the existing players in the current game"""
        if not self.game_is_on:
            context.bot.send_message(chat_id=update.effective_chat.id, text="There is no game currently running.")

        elif not self.game_has_begun:
            players = "Current players: " + ", ".join([player.name for player in self.current_players])
            context.bot.send_message(chat_id=update.effective_chat.id, text=players)

        else:
            status = [f"{player.name}: {self.word_managers[player].word_count}/{self.word_capacity}"
                      for player in self.current_players]
            context.bot.send_message(chat_id=update.effective_chat.id, text=" ,".join(status))

    def begin_game(self, update: Update, context: CallbackContext):
        """Assign users to their individual word managers"""
        user = update.effective_user

        if not self.game_is_on:
            update.message.reply_text("You must first start a game using /startgame!")
            return

        if self.game_has_begun:
            update.message.reply_text("The game has already begun!")
            return

        if user.id not in self.all_player_ids:
            update.message.reply_text("You're not in the game!")
            return

        self.game_has_begun = True

        self.word_capacity = PLAYER_CAPACITY_RATIO[len(self.all_player_ids)]
        self.word_managers = {player: WordManager(self.word_capacity) for player in self.current_players}

        if len(self.current_players) == 1:
            self.single_player = True

        if update.effective_chat.id == self.group_chat_id:
            update.message.reply_text(f"{user.name} has started the game! Head over to your individual chat with Wordle Battle Bot to start playing.")

        self.message_all(message=f"{user.name} has has started the game! Begin by guessing a 5-letter word.", context=context)
        self.message_all(message=f"If your stack exceeds more than {self.word_capacity} words, you lose!", context=context)

        for player in self.current_players:
            self.auto_show_status(chat_id=player.id, context=context)
            self.auto_drop(user=player, context=context)

    def auto_drop(self, user, context: CallbackContext):
        """This function is called every time a user makes a guess, to reset the queue for blocks to be dropped"""
        # Replaces the current timers if this function is called, i.e. when a new guess is made
        current_jobs = context.job_queue.get_jobs_by_name(f"drop{user.id}")
        for job in current_jobs:
            job.schedule_removal()

        # Schedules the auto_receive function for the individual word managers
        context.job_queue.run_repeating(self.word_managers[user].auto_receive, TIME_LIMIT, context=user.id,
                                        name=f"drop{user.id}")

        # Schedule warning messages to be sent when approaching the time limit
        for i in [0.6666, 0.3333]:
            context.job_queue.run_repeating(auto_warning, TIME_LIMIT, first=TIME_LIMIT * (1-i),
                                            context=(user.id, TIME_LIMIT * i), name=f"drop{user.id}")

        # Schedules the check_win_lose method to be called on repeat, cancelling all jobs when the player has lost
        context.job_queue.run_repeating(self.check_win_lose, TIME_LIMIT, name=f"drop{user.id}")

    def show_status(self, context: CallbackContext):
        """Displays on command how many lives left the opponents have"""

        status = [f"{player.name}: {self.word_managers[player].word_count}/{self.word_capacity}"
                  for player in self.current_players]

        chat_id = context.job.context
        context.bot.send_message(chat_id=chat_id, text=", ".join(status))

    def auto_show_status(self, context: CallbackContext, chat_id):
        """Schedules the show_status function to show the status of all players, calling itself once over"""
        # Schedule the auto_receive function for the individual word managers
        context.job_queue.run_repeating(self.show_status, STATUS_INTERVAL, name=f"status{chat_id}", context=chat_id)

    def guess_callback(self, update: Update, context: CallbackContext):
        """Passes user response to respective word managers to tabulate the result, then responds accordingly"""
        user = update.message.from_user

        # Do not proceed if a game has not started
        if not self.game_has_begun:
            return

        # Do not proceed if the user is not a current player of the game
        if user not in self.current_players:
            return

        # Make a guess and save the return result ("invalid", "normal", "correct_1", "correct_2", "win", "lose")
        guess_result = self.word_managers[user].make_guess(update, context)

        # If the player has made a guess, reset the timer
        if guess_result != "invalid":
            self.auto_drop(user=user, context=context)

        # Check for any winners or losers and react accordingly
        self.check_win_lose(context)

        # If correct, make all other players receive blocks (where 'user' is guesser and 'players' is everyone else)
        if guess_result == "correct_1":
            for player in self.current_players:
                if player != user:
                    inherited_answer = self.word_managers[user].answer_to_inherit
                    self.word_managers[player].receive_blocks(sender_name=user.name,
                                                              receiver_chat_id=player.id,
                                                              context=context,
                                                              inherit=inherited_answer)

                    # Check for any winners or losers and react accordingly
                    self.check_win_lose(context)

    def check_win_lose(self, context: CallbackContext):
        """Called after every time blocks are added/removed to eliminate players or end the game"""
        for player in self.current_players:
            if self.word_managers[player].won_game:
                self.message_all(f"{player.name} has cleared all their words. {player.name} wins!", context)
                self.message_all(f"The game has ended. Goodbye!", context)
                for user in self.current_players:
                    cancel_auto(user, context)
                self.game_has_ended = True
                break

            if self.word_managers[player].lost_game:
                if self.single_player:
                    self.message_all("You lose!", context)
                    self.message_all("The game has ended. Goodbye!", context)
                    self.game_has_ended = True

                else:
                    self.message_all(f"{player.name} got overwhelmed by words and has been eliminated!", context)

                self.current_players.remove(player)
                cancel_auto(player, context)

            if not self.single_player:
                if len(self.current_players) == 1:
                    winner = self.current_players[0]
                    self.message_all(f"{winner.name} is the last one remaining. {winner.name} wins!", context)
                    self.message_all(f"The game has ended. Goodbye!", context)
                    cancel_auto(winner, context)
                    self.game_has_ended = True

    def force_end(self, update: Update, context: CallbackContext):
        """Ends the game on command."""
        user = update.effective_user
        self.game_has_ended = True

        context.bot.send_message(chat_id=self.group_chat_id, text=f"The game was ended by {user.name}. Goodbye!")
        self.message_all(f"The game was ended by {user.name}. Goodbye!", context)

        for user in self.current_players:
            cancel_auto(user, context)

    def timeout(self, context: CallbackContext):
        """Ends the game automatically when called after 10 minutes of the game not being begun"""
        if not self.game_has_begun and not self.game_has_ended:
            context.bot.send_message(chat_id=self.group_chat_id, text=f"Game ended due to timeout.")
            self.message_all(f"Game ended due to timeout.", context)
            self.game_has_ended = True


# -------- HELPER FUNCTIONS ---------

def auto_warning(context: CallbackContext):
    """Sends a message as a warning of blocks approaching"""
    chat_id, remaining = context.job.context

    context.bot.send_message(chat_id=chat_id, text=f"New word arriving in {int(round(remaining))} seconds.")


def cancel_auto(user, context: CallbackContext):
    """Cancels any recurring automatic functions from the job queue for a given player"""
    drop_jobs = context.job_queue.get_jobs_by_name(f"drop{user.id}")
    for job in drop_jobs:
        job.schedule_removal()

    status_jobs = context.job_queue.get_jobs_by_name(f"status{user.id}")
    for job in status_jobs:
        job.schedule_removal()


def about(update: Update, context: CallbackContext):
    """Returns information about the game to the user."""
    update.message.reply_text(ABOUT_MSG)


def how_to_play(update: Update, context: CallbackContext):
    """Guides the user on how to start and play the game."""
    update.message.reply_text(HELP_MSG)


def example(update: Update, context: CallbackContext):
    """Shows an example of how guesses are made."""
    update.message.reply_text(EXAMPLE_MSG)


ABOUT_MSG = '''
🤪 INFO 🤪
Wordle Battle is a multiplayer version of Josh Wardle's famously addictive Wordle.
Games are started in a group chat, but are played in the private chat with me, the Wordle Battle Bot!
Perfect for everyone, die-hard Wordle nut or otherwise.
v1.0 by @lxlchristian
'''

HELP_MSG = '''
😗 STARTING COMMANDS 😗
/startgame: Use this command in a group chat to initiate a game. Click the button that follows to join.
/begin: Use this command to start playing once everyone's in the game.

🧐 MAKING GUESSES 🧐
When the game begins, each player is assigned a stack of random 5-letter words.
Your goal is to 'clear' every word in your stack by guessing them correctly.
When you make a guess, the bot will give you letter-by-letter feedback for on your guess:
🟩: This letter is in the word, and in the right position
🟨: This letter is in the word, but in the wrong position
⬛️: This letter doesn't exist in the word
The hints you've gathered are shown on the right of each word.

😵‍💫 RECEIVING NEW WORDS 😵‍💫
A new word gets added to the stack for every three guesses you make, indicated by the number on top of the grid (e.g. 2️⃣).
This also happens every 30 seconds that you don't make a guess.
Clearing a word from your stack sends it to everyone's stack, unless said word was already sent to you by another player.
Words received from other players are indicated by 🔸 instead of 🔹.
If your stack goes over the capacity, you lose and are eliminated from the game!
Stack capacity depends on the number of players.

Recommended: Type /example to see an example guess being made
'''

EXAMPLE_MSG = '''
🤔 MAKING A GUESS: AN EXAMPLE 🤔
Every time you make a guess, the bot will give feedback in the form of a grid. Below shows an example of a guess being made.

Guess #1: LIVES
Bot's reply:
2️⃣2️⃣2️⃣2️⃣2️⃣
⬜️⬜️⬜️⬜️⬜️
⬜️⬜️⬜️⬜️⬜️
⬜️⬜️⬜️⬜️⬜️
🟨⬛⬛🟨🟨  • • • • •  🔹  L, E, S
🟩⬛⬛⬛⬛  L • • • •  🔹  

⬛️ THE STACK ⬜
A row of black squares represents a word in the stack. Every guess made is applied to all current words.
A row of white squares represents an empty space in the stack. They may eventually be filled up with more words (see below).

🟩 HINTS 🟨
🟨 indicates that the letters L, E and S from LIVES are in the first word, but in the wrong position. They are stored as unordered hints.
🟩 indicates that the letter L from LIVES is in the second word, and in the right position. It is stored as an ordered hint.

🟥 NEW WORDS 🟧
You receive new words:
1. Every three guesses you make (counted down by the number on top of the grid, i.e. 2️⃣ means two guesses left)
2. Every 30 seconds that pass without a guess made
3. Every time an opponent clears a word from their stack
'''