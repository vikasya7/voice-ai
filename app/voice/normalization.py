import re

DIGIT_WORDS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}


def normalize_phone(text: str) -> str | None:
    text = text.lower()

    # Convert spoken digits to actual digits
    for word, digit in DIGIT_WORDS.items():
        text = re.sub(rf"\b{word}\b", digit, text)

    # Remove commas, spaces, hyphens, etc.
    digits = re.sub(r"\D", "", text)

    if not digits:
        return None

    return digits