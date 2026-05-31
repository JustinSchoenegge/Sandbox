import random
from datetime import datetime

QUOTES = [
    "The secret of getting ahead is getting started. — Mark Twain",
    "Small daily improvements lead to stunning results. — Robin Sharma",
    "An investment in knowledge pays the best interest. — Benjamin Franklin",
    "The body achieves what the mind believes.",
    "Discipline is the bridge between goals and accomplishment. — Jim Rohn",
    "You don't have to be great to start, but you have to start to be great.",
    "Push yourself, because no one else is going to do it for you.",
    "Wake up with determination. Go to bed with satisfaction.",
    "Do something today that your future self will thank you for.",
]


def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Morning"
    elif hour < 17:
        return "Afternoon"
    return "Evening"


def get_quote():
    today = datetime.now().strftime("%Y-%m-%d")
    random.seed(today)
    quote = random.choice(QUOTES)
    random.seed()
    return quote
