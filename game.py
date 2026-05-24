import random

SCORES_FILE = "scores.txt"


def save_score(name, attempts):
    with open(SCORES_FILE, "a") as f:
        f.write(f"{name}: {attempts} attempt(s)\n")


def show_scores():
    try:
        with open(SCORES_FILE, "r") as f:
            lines = f.readlines()
        print("\n--- Past Scores ---")
        for line in lines:
            print(line.strip())
        print("-------------------")
    except FileNotFoundError:
        print("No scores yet!")


def get_guess():
    while True:
        raw = input("Your guess (or 'q' to quit): ").strip().lower()
        if raw == "q":
            return None
        if raw.isdigit():
            value = int(raw)
            if 1 <= value <= 100:
                return value
            print("Please enter a number between 1 and 100.")
        else:
            print("Please enter a whole number.")


def play_round():
    secret = random.randint(1, 100)
    attempts = 0

    print("\nI'm thinking of a number between 1 and 100.")

    while True:
        guess = get_guess()
        if guess is None:
            print("Round abandoned.")
            return None
        attempts += 1

        if guess < secret:
            print("Too low!")
        elif guess > secret:
            print("Too high!")
        else:
            print(f"Correct! You got it in {attempts} attempt(s).")
            return attempts


def main():
    print("=== Number Guesser ===")
    name = input("What's your name? ").strip() or "Anonymous"
    show_scores()

    while True:
        attempts = play_round()
        if attempts is not None:
            save_score(name, attempts)
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again != "y":
            print("Thanks for playing!")
            break
