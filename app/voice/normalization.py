import re
from datetime import date, timedelta


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


def normalize_phone(text: str) -> str:
    """
    Convert spoken or formatted phone numbers into digits.

    Examples:
        "987-654-3210" -> "9876543210"
        "one two three four five six seven eight nine zero"
            -> "1234567890"
    """

    text = text.lower()

    for word, digit in DIGIT_WORDS.items():
        text = re.sub(rf"\b{word}\b", digit, text)

    return re.sub(r"\D", "", text)


# ---------------------------------------------------------
# TIME NORMALIZATION
# ---------------------------------------------------------

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def normalize_time(text: str) -> str | None:
    """
    Convert common spoken appointment times into HH:MM.

    Examples:
        "5 PM" -> "17:00"
        "6 p.m." -> "18:00"
        "six PM" -> "18:00"
        "10 AM" -> "10:00"
        "6:30 PM" -> "18:30"
        "half past six" -> "18:30"
        "quarter past five" -> "17:15"
        "quarter to six" -> "17:45"
    """

    text = text.lower().strip()

    # Normalize punctuation.
    text = text.replace(".", "")
    text = text.replace(",", "")

    # -----------------------------------------------------
    # AM / PM
    # -----------------------------------------------------

    is_pm = bool(
        re.search(r"\b(pm|p m|evening|afternoon|night)\b", text)
    )

    is_am = bool(
        re.search(r"\b(am|a m|morning)\b", text)
    )
    # Don't interpret dates like "October 5" as a time
    if re.search(
    r"\b(january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+\d{1,2}\b",
    text,
    ):
       return None

    # -----------------------------------------------------
    # HALF PAST
    # -----------------------------------------------------

    match = re.search(
        r"half\s+past\s+([a-z]+|\d{1,2})",
        text
    )

    if match:

        hour_text = match.group(1)

        if hour_text.isdigit():
            hour = int(hour_text)
        else:
            hour = NUMBER_WORDS.get(hour_text)

        if hour is not None:

            if is_pm and hour < 12:
                hour += 12

            return f"{hour:02d}:30"

    # -----------------------------------------------------
    # QUARTER PAST
    # -----------------------------------------------------

    match = re.search(
        r"quarter\s+past\s+([a-z]+|\d{1,2})",
        text
    )

    if match:

        hour_text = match.group(1)

        if hour_text.isdigit():
            hour = int(hour_text)
        else:
            hour = NUMBER_WORDS.get(hour_text)

        if hour is not None:

            if is_pm and hour < 12:
                hour += 12

            return f"{hour:02d}:15"

    # -----------------------------------------------------
    # QUARTER TO
    # -----------------------------------------------------

    match = re.search(
        r"quarter\s+to\s+([a-z]+|\d{1,2})",
        text
    )

    if match:

        hour_text = match.group(1)

        if hour_text.isdigit():
            hour = int(hour_text)
        else:
            hour = NUMBER_WORDS.get(hour_text)

        if hour is not None:

            hour -= 1

            if hour == 0:
                hour = 12

            if is_pm and hour < 12:
                hour += 12

            return f"{hour:02d}:45"

    # -----------------------------------------------------
    # NUMERIC TIME
    # -----------------------------------------------------

    match = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\b",
        text
    )

    if match:

        hour = int(match.group(1))
        minute = int(match.group(2) or 0)

        if is_pm and hour < 12:
            hour += 12

        if is_am and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # -----------------------------------------------------
    # SPOKEN HOUR
    # -----------------------------------------------------

    for word, hour in NUMBER_WORDS.items():

        if re.search(rf"\b{word}\b", text):

            if is_pm and hour < 12:
                hour += 12

            if is_am and hour == 12:
                hour = 0

            return f"{hour:02d}:00"

    return None


# ---------------------------------------------------------
# DATE NORMALIZATION
# ---------------------------------------------------------

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def normalize_date(
    text: str,
    today: date | None = None
) -> str | None:
    """
    Convert common relative dates into YYYY-MM-DD.

    Examples:
        "today" -> today's date
        "tomorrow" -> tomorrow's date
        "Monday" -> next Monday
        "next Friday" -> next Friday
    """

    if today is None:
        today = date.today()

    text = text.lower().strip()

    # Today
    if "today" in text:
        return today.isoformat()

    # Tomorrow
    if "tomorrow" in text:
        return (
            today + timedelta(days=1)
        ).isoformat()

    # Next weekday
    match = re.search(
        r"(?:next\s+)?"
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        text
    )

    if match:

        target_day = WEEKDAYS[match.group(1)]
        current_day = today.weekday()

        days_ahead = (
            target_day - current_day
        ) % 7

        # If today is the same weekday,
        # "Monday" means the next Monday.
        if days_ahead == 0:
            days_ahead = 7

        return (
            today + timedelta(days=days_ahead)
        ).isoformat()

    # Already YYYY-MM-DD
    match = re.search(
        r"\b(20\d{2}-\d{2}-\d{2})\b",
        text
    )

    if match:
        return match.group(1)

    return None