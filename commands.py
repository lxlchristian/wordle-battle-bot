from telegram import Update
from telegram.ext import CallbackContext
from wordbank import answer_words, valid_words
from random import choice

WORD_DROP = 3
START_WORDS = 2
STATE_EMOJIS = ["⬇️", "5️⃣", "4️⃣", "3️⃣", "2️⃣", "1️⃣"]


# ----------- INVALID INPUTS ----------

def check_valid(user_input, previous_guesses):
    """Catches all invalid inputs"""
    # Check if the input is in the valid word list of 5-letter words

    if user_input not in valid_words:
        return "Sorry, that's not in the word list. Try again."

    # Check if the guessed word is in the last 10 words
    elif user_input in previous_guesses:
        return "You can't use a word in your recent guesses!"

    else:
        return "valid"


# ----------- FORMATTERS ----------

def format_results(results: list):
    """"Helper function for formatting results as a single string"""
    # Reverse the list so the oldest word is at the bottom
    results = results[::-1]
    string = "".join([result + "\n" for result in results])
    return string


# ----------- WORD CLASS ----------

class Word:
    """Word class which includes checking methods etc"""
    def __init__(self, blank=False, inherit=""):
        self.is_guessed = self.is_inherited = self.to_be_sent = False

        # Create attribute for blankness, passed when calling the Object
        self.is_blank = blank
        if self.is_blank:
            self.answer = None

        # If inherit is not blank, re-inherit the previous word
        elif inherit != "":
            self.answer = inherit
            self.is_inherited = True
            print(f"Inherited {inherit}")

        # If not blank, choose an answer word
        else:
            self.answer = choice(answer_words)
            print(self.answer)

        # Initialise the format of the hints
        self.green_hints = ["•"] * 5
        self.yellow_hints = [""] * 5
        self.ordered_hints = []

    def guess_to_squares(self, guess: str):
        """Converts a guess to corresponding squares, and manages the hints"""
        if self.is_blank:
            return "⬜️⬜️⬜️⬜️⬜️"

        dummy_guess = list(guess)
        dummy_ans = list(self.answer)
        squares = [""] * 5

        # Prioritise green squares to account for multiple letters in the guess via separate for loops
        for i in range(5):
            letter = dummy_guess[i]
            if letter == dummy_ans[i]:
                squares[i] = "🟩"

                # Remove the guessed letter from both strings to prevent a yellow match for the same letter
                dummy_ans[i] = dummy_guess[i] = ""

                # Make the letter a green hint
                self.green_hints[i] = letter

                # If there is a yellow hint in that position, remove it
                if self.green_hints[i] == self.yellow_hints[i]:
                    self.yellow_hints[i] = ""
                    self.ordered_hints.remove(letter)

        for i in range(5):
            letter = dummy_guess[i]
            if letter != "":
                if letter in dummy_ans:
                    squares[i] = "🟨"

                    # Remove the guessed letter from both strings to prevent a double match for the same letter
                    letter_in_ans_i = dummy_ans.index(dummy_guess[i])
                    dummy_ans[letter_in_ans_i] = dummy_guess[i] = ""

                    # Make the letter a yellow hint (bound to its actual position in the answer)
                    # if there is no green OR yellow hint in that position
                    if self.green_hints[letter_in_ans_i] != letter and self.yellow_hints[letter_in_ans_i] != letter:
                        self.yellow_hints[letter_in_ans_i] = letter
                        self.ordered_hints.append(letter)

                else:
                    squares[i] = "⬛️"[0]

        # Check if the word is correctly guessed
        if squares == ["🟩"] * 5:
            self.is_guessed = True
            return f"🟩🟩🟩🟩🟩  💥 {self.answer} 💥"

        # Format squares
        squares_formatted = "".join(squares[:5])

        # Format hints
        if self.is_inherited:
            separator = "🔸"
        else:
            separator = "🔹"

        hints_formatted = "  " + " ".join(self.green_hints) + f"  {separator}  " + ", ".join(self.ordered_hints)

        return squares_formatted + hints_formatted


# ----------- WORD MANAGER CLASS ----------

class WordManager:
    """Manages all the current words and guesses, linked to a specific player"""
    def __init__(self, capacity):
        # The words list is initialised as a list of blank words with length capacity (they become white squares)
        self.capacity = capacity
        self.current_words = [Word(blank=True)] * self.capacity
        self.current_results = self.recent_guesses = []
        self.guess_count = self.word_count = 0
        self.answer_to_inherit = ""
        self.correct_word_place = None
        self.lost_game = self.won_game = False

        for i in range(START_WORDS):
            self.add_word()

        # Initialise results to accommodate opponents sending words before user has made any guesses
        self.current_results = [word.guess_to_squares("00000") for word in self.current_words]

    def add_word(self, inherit=""):
        """Changes the first blank word into a non-blank word"""
        if self.word_count == self.capacity:
            self.lost_game = True
            return

        for i in range(self.capacity):
            if self.current_words[i].is_blank:
                if inherit == "":
                    self.current_words[i] = Word()
                    answer_words.remove(self.current_words[i].answer)

                else:
                    self.current_words[i] = Word(inherit=inherit)

                self.word_count += 1
                break

    def is_correct(self):
        """Return true if any words are guessed correctly"""
        for word in self.current_words:
            if word.is_guessed:
                self.correct_word_place = self.current_words.index(word)
                if not word.is_inherited:
                    self.answer_to_inherit = word.answer
                    return "correct_1"
                return "correct_2"
        return "incorrect"

    def clear_word(self, word_index):
        """Clear word at a particular index"""
        self.current_results.pop(word_index)
        self.current_results.append("⬜️⬜️⬜️⬜️⬜️")
        self.current_words.pop(word_index)
        self.current_words.append(Word(blank=True))
        self.word_count -= 1

    def receive_blocks(self, sender_name, receiver_chat_id, context, inherit=""):
        """If an opponent gets a word right, this function is triggered for all other users to receive a new word"""
        # Check for word inheritance and call the add word function accordingly
        self.add_word() if inherit == "" else self.add_word(inherit=inherit)

        # If the add word results in the lost_game attribute to be true, return lose
        if self.lost_game:
            reply = self.respond_lose(sender_name=sender_name)
            context.bot.send_message(chat_id=receiver_chat_id, text=reply)
            return "lose"

        else:
            reply = self.respond_result(new_word=True, sender_name=sender_name)
            context.bot.send_message(chat_id=receiver_chat_id, text=reply)
            return "normal"

    def auto_receive(self, context):
        """Function to automatically receive a word"""
        chat_id = context.job.context

        self.add_word()
        
        # If the add word results in the lost_game attribute to be true, return lose
        if self.lost_game:
            reply = self.respond_lose()
            context.bot.send_message(chat_id=chat_id, text=reply)
            return "lose"

        else:
            reply = self.respond_result(new_word=True)
            context.bot.send_message(chat_id=chat_id, text=reply)
            return "normal"

    def make_guess(self, update: Update, context: CallbackContext):
        """Checks the user's guess against all current words and responds accordingly"""
        user_guess = update.message.text.upper()

        # Check the validity of the input; return an error message if invalid
        error_message = check_valid(user_guess, self.recent_guesses)
        if error_message != "valid":
            update.message.reply_text(error_message)
            return "invalid"

        # Turn guess into a result
        self.current_results = [word.guess_to_squares(user_guess) for word in self.current_words]

        # Keep track of words used in recent guesses (max 10)
        self.recent_guesses.append(user_guess)
        if len(self.recent_guesses) > 10:
            self.recent_guesses.pop(0)

        reply = ""
        # Format the response if a word is guessed correctly
        if self.is_correct() != "incorrect":
            reply = self.respond_result(new_word=False)

        # Keep track of the number of guesses, but only if no words are right
        if self.is_correct() == "incorrect":
            self.guess_count += 1

            # Add a word every few guesses, and register a reply fitting for the result
            if self.guess_count % WORD_DROP == 0:
                self.add_word()
                reply = self.respond_result(new_word=True)

                # If adding a word results in the lost_game attribute being true, change the reply to reflect the loss
                if self.lost_game:
                    reply = self.respond_lose()

            else:
                # Format the response in the case where a new word is not added
                reply = self.respond_result(new_word=False)

        update.message.reply_text(reply)

        # Removes the fully green lines for the next round
        if self.is_correct() != "incorrect":
            to_send = self.is_correct()

            self.clear_word(self.correct_word_place)
            self.correct_word_place = None

            # Check if all the words have been cleared
            if self.word_count == 0:
                update.message.reply_text("Good job, you've cleared them all! You win!")
                self.won_game = True
                return "win"

            # Return correct_1 or correct_2 depending on whether it is inherited
            return to_send
        return "normal"

    def respond_result(self, new_word, sender_name=None):
        """Formats the result"""
        count = self.guess_count % WORD_DROP
        states = [STATE_EMOJIS[0]] + STATE_EMOJIS[1 - WORD_DROP:]

        countdown_text = states[count] * 5 + "\n"

        if new_word:
            if sender_name:
                self.current_results[self.word_count - 1] = f"🟥🟥🟥🟥🟥  SENT BY {sender_name.upper()}"
            else:
                self.current_results[self.word_count - 1] = "🟧🟧🟧🟧🟧  NEW WORD"

        results_msg = countdown_text + format_results(self.current_results)
        results_msg += f"\nLast 10 guesses: {', '.join(self.recent_guesses[::-1])}"

        return results_msg

    def respond_lose(self, sender_name=None):
        """Sends game over message in response to the lost_game attribute"""
        lose_msg = ""

        if sender_name:
            lose_msg += f"{sender_name} sent you a word, but you were out of space!\n"

        for word in self.current_words[::-1]:
            lose_msg += f"🟥🟥🟥🟥🟥 : {word.answer}\n"

        lose_msg += "\nYou were overwhelmed by words! You've been eliminated!"

        return lose_msg


# ----------- OTHERS ----------

def unknown(update: Update, context: CallbackContext):
    """Responds to unknown commands."""
    context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")
