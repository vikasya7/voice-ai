import re
from datetime import date, timedelta


# ---------------------------------------------------------
# PHONE NORMALIZATION
# ---------------------------------------------------------

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

_DIGIT_ALT = "|".join(DIGIT_WORDS)


def normalize_phone(text: str | None) -> str | None:
    """
    Convert spoken or formatted phone numbers into digits.

        "987-654-3210"                -> "9876543210"
        "one two three four five six" -> "123456"
        "double five"                 -> "55"
        "triple zero"                 -> "000"
    """

    if not text:
        return None

    text = text.lower().strip()

    # "double five" -> "55"
    # "triple zero" -> "000"
    text = re.sub(
        rf"\b(double|triple)\s+({_DIGIT_ALT})\b",
        lambda m: DIGIT_WORDS[m.group(2)]
        * (2 if m.group(1) == "double" else 3),
        text,
    )

    # Convert spoken digit words to digits
    text = re.sub(
        rf"\b({_DIGIT_ALT})\b",
        lambda m: DIGIT_WORDS[m.group(1)],
        text,
    )

    digits = re.sub(r"\D", "", text)

    # Reasonable phone-number length
    if 7 <= len(digits) <= 15:
        return digits

    return None


# ---------------------------------------------------------
# SHARED DATE PATTERNS
# ---------------------------------------------------------

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)

ISO_RE = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})\b"
)

SLASH_RE = re.compile(
    r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\b"
)

MONTH_DAY_RE = re.compile(
    rf"\b({_MONTH})\b\s+(\d{{1,2}})"
    rf"(?:st|nd|rd|th)?\b"
    rf"(?:\s*,?\s*(\d{{4}}))?"
)

DAY_MONTH_RE = re.compile(
    rf"\b(\d{{1,2}})"
    rf"(?:st|nd|rd|th)?\s+"
    rf"(?:of\s+)?({_MONTH})\b"
    rf"(?:\s*,?\s*(\d{{4}}))?"
)

ORDINAL_RE = re.compile(
    r"\b\d{1,2}(?:st|nd|rd|th)\b"
)

_DATE_STRIP_PATTERNS = [
    ISO_RE,
    SLASH_RE,
    MONTH_DAY_RE,
    DAY_MONTH_RE,
    ORDINAL_RE,
]


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

OFFSET_WORDS = {
    "quarter": 15,
    "half": 30,
    "five": 5,
    "ten": 10,
    "twenty": 20,
    "twenty five": 25,
    "twenty-five": 25,
}

MINUTE_WORDS = {
    "fifteen": 15,
    "thirty": 30,
    "forty five": 45,
    "forty-five": 45,
    "fortyfive": 45,
}

_NUM_ALT = "|".join(NUMBER_WORDS)

_OFFSET_ALT = "|".join(
    sorted(
        (
            re.escape(k).replace(
                r"\ ",
                r"[\s-]"
            )
            for k in OFFSET_WORDS
        ),
        key=len,
        reverse=True,
    )
)

_MINUTE_ALT = r"fifteen|thirty|forty[\s-]?five"


def _hour_value(token: str) -> int | None:
    if token.isdigit():
        return int(token)

    return NUMBER_WORDS.get(token)


def _to_24h(
    hour: int,
    is_pm: bool,
    is_am: bool,
    is_night: bool = False,
) -> int:

    # 12 at night = midnight
    if is_night and hour == 12:
        return 0

    if is_pm and hour < 12:
        return hour + 12

    if is_am and hour == 12:
        return 0

    return hour


def _fmt(total_minutes: int) -> str:
    total_minutes %= 24 * 60

    return (
        f"{total_minutes // 60:02d}:"
        f"{total_minutes % 60:02d}"
    )


def normalize_time(text: str | None) -> str | None:
    """
    Convert spoken or written times into 24-hour HH:MM.

        "5pm"                  -> "17:00"
        "9:30 pm"              -> "21:30"
        "half past six"        -> "06:30"
        "quarter to twelve pm" -> "11:45"
        "five thirty evening"  -> "17:30"
    """

    if not text:
        return None

    text = text.lower().strip()

    # Remove "I am" / "I'm"
    text = re.sub(
        r"\bi\s+am\b|\bi'm\b",
        " ",
        text,
    )

    # 9.30 -> 9:30
    text = re.sub(
        r"(?<=\d)\.(?=\d{2}\b)",
        ":",
        text,
    )

    # p.m. -> pm
    text = text.replace(".", "")
    text = text.replace(",", "")

    # Remove dates so date numbers are not interpreted as times
    for pattern in _DATE_STRIP_PATTERNS:
        text = pattern.sub(" ", text)

    # -----------------------------------------------------
    # PHONE NUMBER PROTECTION
    # -----------------------------------------------------

    # Example:
    # 1-2-3-4-5-6-7-8-9-0
    # should NEVER become 01:00
    #
    # Also protects:
    # 1234567890
    # 987-654-3210
    if re.search(
        r"(?<!\d)(?:\d[\s\-\.]*){7,}(?!\d)",
        text,
    ):
        return None

    # -----------------------------------------------------
    # AM / PM
    # -----------------------------------------------------

    explicit_pm = bool(
        re.search(
            r"(?<![a-z])p\s?m\b",
            text,
        )
    )

    explicit_am = bool(
        re.search(
            r"(?<![a-z])a\s?m\b",
            text,
        )
    )

    is_night = (
        bool(re.search(r"\bnight\b", text))
        and not explicit_pm
    )

    is_pm = (
        explicit_pm
        or bool(
            re.search(
                r"\b(evening|afternoon|night)\b",
                text,
            )
        )
    )

    is_am = (
        explicit_am
        or bool(
            re.search(
                r"\bmorning\b",
                text,
            )
        )
    ) and not is_pm

    # -----------------------------------------------------
    # NOON / MIDNIGHT
    # -----------------------------------------------------

    if re.search(r"\bnoon\b", text):
        return "12:00"

    if re.search(r"\bmidnight\b", text):
        return "00:00"

    # -----------------------------------------------------
    # OFFSET TIME
    #
    # half past six
    # quarter past five
    # ten past 4
    # twenty to nine
    # -----------------------------------------------------

    match = re.search(
        rf"\b({_OFFSET_ALT})\s+"
        rf"(past|to)\s+"
        rf"([a-z]+|\d{{1,2}})\b",
        text,
    )

    if match:

        offset_key = re.sub(
            r"[\s-]+",
            " ",
            match.group(1),
        )

        offset = (
            OFFSET_WORDS.get(offset_key)
            or OFFSET_WORDS.get(match.group(1))
        )

        direction = match.group(2)

        hour = _hour_value(match.group(3))

        valid = (
            offset is not None
            and hour is not None
        )

        # "half to" is not valid
        if valid and not (
            offset == 30
            and direction == "to"
        ):

            hour24 = _to_24h(
                hour,
                is_pm,
                is_am,
                is_night,
            )

            base = hour24 * 60

            if direction == "past":
                total = base + offset
            else:
                total = base - offset

            if 0 <= hour24 <= 23:
                return _fmt(total)

    # -----------------------------------------------------
    # NUMERIC TIME
    #
    # 9:30
    # 9:30pm
    # 6 pm
    # 5pm
    # 10 am
    # 14:30
    # -----------------------------------------------------

    match = re.search(
        r"(?<![\d:])"
        r"(\d{1,2})"
        r"(?::(\d{2}))?"
        r"(?!\d)",
        text,
    )

    if match:

        hour = int(match.group(1))

        minute = int(
            match.group(2) or 0
        )

        hour = _to_24h(
            hour,
            is_pm,
            is_am,
            is_night,
        )

        if (
            0 <= hour <= 23
            and 0 <= minute <= 59
        ):
            return f"{hour:02d}:{minute:02d}"

        return None

    # -----------------------------------------------------
    # NUMBER-WORD TIME
    #
    # five pm
    # six in the evening
    # five thirty pm
    # -----------------------------------------------------

    match = re.search(
        rf"\b({_NUM_ALT})\b"
        rf"(?:\s+(?:o'?clock|({_MINUTE_ALT})))?",
        text,
    )

    if match:

        hour = NUMBER_WORDS[
            match.group(1)
        ]

        minute = 0

        if match.group(2):

            minute_key = re.sub(
                r"[\s-]+",
                " ",
                match.group(2),
            )

            minute = MINUTE_WORDS[
                minute_key
            ]

        hour = _to_24h(
            hour,
            is_pm,
            is_am,
            is_night,
        )

        return f"{hour:02d}:{minute:02d}"

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

_WEEKDAY_RE = re.compile(
    r"\b(?:next\s+|this\s+|coming\s+)?"
    r"(monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday)\b"
)

_IN_DAYS_RE = re.compile(
    rf"\bin\s+(\d{{1,2}}|{_NUM_ALT})\s+days?\b"
)


def _safe_date(
    year: int,
    month: int,
    day: int,
) -> date | None:

    try:
        return date(
            year,
            month,
            day,
        )
    except ValueError:
        return None


def _roll_forward(
    month: int,
    day: int,
    today: date,
) -> date | None:
    """
    Pick this year's occurrence,
    or next year's if already past.
    """

    for year in (
        today.year,
        today.year + 1,
        today.year + 2,
    ):

        candidate = _safe_date(
            year,
            month,
            day,
        )

        if (
            candidate
            and candidate >= today
        ):
            return candidate

    return None


def normalize_date(
    text: str | None,
    today: date | None = None,
) -> str | None:
    """
    Convert common spoken or written dates into YYYY-MM-DD.

        "today"
            -> today

        "tonight"
            -> today

        "tomorrow"
            -> tomorrow

        "day after tomorrow"
            -> today + 2

        "in 3 days"
            -> today + 3

        "Monday"
            -> next Monday

        "next Friday"
            -> next Friday

        "October 10"
            -> next occurrence

        "10th Oct"
            -> next occurrence

        "10/10/2026"
            -> 2026-10-10

        "2026-10-10"
            -> 2026-10-10
    """

    if not text:
        return None

    if today is None:
        today = date.today()

    text = text.lower().strip()

    # -----------------------------------------------------
    # RELATIVE DATES FIRST
    #
    # This is important because a booking sentence such as:
    #
    # "I want to book tomorrow at 9:30 pm"
    #
    # should immediately resolve to tomorrow.
    # -----------------------------------------------------

    # "day after tomorrow"
    if re.search(
        r"\bday\s+after\s+tomorrow\b",
        text,
    ):
        return (
            today + timedelta(days=2)
        ).isoformat()

    # "tomorrow"
    if re.search(
        r"\btomorrow\b",
        text,
    ):
        return (
            today + timedelta(days=1)
        ).isoformat()

    # "today" / "tonight"
    if re.search(
        r"\b(today|tonight)\b",
        text,
    ):
        return today.isoformat()

    # "in 3 days"
    match = _IN_DAYS_RE.search(text)

    if match:

        token = match.group(1)

        if token.isdigit():
            n = int(token)
        else:
            n = NUMBER_WORDS[token]

        return (
            today + timedelta(days=n)
        ).isoformat()

    # -----------------------------------------------------
    # PHONE NUMBER PROTECTION
    # -----------------------------------------------------
    #
    # IMPORTANT:
    #
    # A phone number such as:
    #
    # 1-2-3-4-5-6-7-8-9-0
    #
    # can accidentally look like:
    #
    # 1-2
    #
    # to the date parser.
    #
    # Therefore, before checking numeric dates,
    # detect long digit sequences.
    # -----------------------------------------------------

    if re.search(
        r"(?<!\d)(?:\d[\s\-\.]*){7,}(?!\d)",
        text,
    ):
        return None

    # Plain continuous phone number
    #
    # Example:
    # 1234567890
    #
    # Don't let it become a date.
    if re.search(
        r"(?<!\d)\d{7,15}(?!\d)",
        text,
    ):
        return None

    # -----------------------------------------------------
    # ISO DATE
    #
    # 2026-10-10
    # -----------------------------------------------------

    match = ISO_RE.search(text)

    if match:

        d = _safe_date(
            *map(int, match.groups())
        )

        return (
            d.isoformat()
            if d
            else None
        )

    # -----------------------------------------------------
    # MONTH + DAY
    #
    # October 10
    # Oct 10 2027
    # -----------------------------------------------------

    match = MONTH_DAY_RE.search(text)

    if match:

        month = MONTHS[
            match.group(1)[:3]
        ]

        day = int(
            match.group(2)
        )

        if match.group(3):

            d = _safe_date(
                int(match.group(3)),
                month,
                day,
            )

        else:

            d = _roll_forward(
                month,
                day,
                today,
            )

        return (
            d.isoformat()
            if d
            else None
        )

    # -----------------------------------------------------
    # DAY + MONTH
    #
    # 10 October
    # 10th of Oct 2027
    # -----------------------------------------------------

    match = DAY_MONTH_RE.search(text)

    if match:

        day = int(
            match.group(1)
        )

        month = MONTHS[
            match.group(2)[:3]
        ]

        if match.group(3):

            d = _safe_date(
                int(match.group(3)),
                month,
                day,
            )

        else:

            d = _roll_forward(
                month,
                day,
                today,
            )

        return (
            d.isoformat()
            if d
            else None
        )

    # -----------------------------------------------------
    # SLASH DATE
    #
    # India / UK convention:
    #
    # 10/10/2026
    # = 10 October 2026
    # -----------------------------------------------------

    match = SLASH_RE.search(text)

    if match:

        day = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        if match.group(3):

            year = int(
                match.group(3)
            )

            if year < 100:
                year += 2000

            d = _safe_date(
                year,
                month,
                day,
            )

        else:

            d = _roll_forward(
                month,
                day,
                today,
            )

        return (
            d.isoformat()
            if d
            else None
        )

    # -----------------------------------------------------
    # WEEKDAY
    #
    # Monday
    # next Friday
    # coming Sunday
    # -----------------------------------------------------

    match = _WEEKDAY_RE.search(text)

    if match:

        target_day = WEEKDAYS[
            match.group(1)
        ]

        days_ahead = (
            target_day
            - today.weekday()
        ) % 7

        # Same weekday means next week
        if days_ahead == 0:
            days_ahead = 7

        return (
            today
            + timedelta(days=days_ahead)
        ).isoformat()

    return None