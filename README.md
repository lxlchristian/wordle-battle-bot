# wordle-battle-bot
Telegram game bot developed using the python-telegram-bot package and Telegram's API. Inspired by Josh Wardle's Wordle. Hosted on Heroku.

BotManager Class:
Because this program incorporates interactions in both group chat and private chat settings, the program uses a BotManager object to initialise, append to, and sort through a list of current GameManager objects to ensure that commands function correctly (especially to handle a game being started at various states of the session e.g. when interactions have moved to private chat). GameManager objects are removed from the list after completion.

GameManager Class:
GameManager objects manage the cross-player interactions within a game by communicating with each player's designated WordManager object. For example, if one player has cleared a word from their stack according to their WordManager object, the GameManager responds by sorting through the list of remaining players and calling their WordManager object's receive_blocks method.

WordManager Class:
A WordManager object keeps track of a player's current Word objects, most recent results (results being feedback in the form of green/yellow/black squares), most recent guesses. Importantly, it contains the core functionality of receiving a user's input as a guess, and responding if the input was invalid, wrong, or correct. It also contains the lost_game or won_game attribute which is checked by the GameManager class on every callback.

Word Class:
A Word object selects a random word from the word bank to be its answer. It also contains the method for generating feedback for a user's guess - for example, if the guess was "SPITE" while the answer was "SPILL", the method would return the string "🟩🟩🟩⬛️⬛️". This class also manages the hints the user has acccumulated: the above example would generate the string "S P I • •". 
