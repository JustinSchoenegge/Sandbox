import random


def get_guess():
    while True:
        raw = input("Your guess: ")
        if raw.isdigit():
            return int(raw)
        print("Please enter a whole number.")


def play_round():
    secret = random.randint(1, 100)
    attempts = 0

    print("\nI'm thinking of a number between 1 and 100.")

    while True:
        guess = get_guess()
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

    while True:
        play_round()
        again = input("\nPlay again? (y/n): ").strip().lower()
        if again != "y":
            print("Thanks for playing!")
            break


main()
