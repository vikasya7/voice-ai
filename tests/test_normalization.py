from datetime import date

from app.voice.normalization import (
    normalize_phone,
    normalize_time,
    normalize_date,
)


def test_phone():
    assert normalize_phone("987-654-3210") == "9876543210"

    assert (
        normalize_phone(
            "one two three four five six seven eight nine zero"
        )
        == "1234567890"
    )


def test_time():

    assert normalize_time("5 PM") == "17:00"

    assert normalize_time("5 p.m.") == "17:00"

    assert normalize_time("6 PM") == "18:00"

    assert normalize_time("six in the evening") == "18:00"

    assert normalize_time("10 AM") == "10:00"

    assert normalize_time("6:30 PM") == "18:30"

    assert normalize_time("half past six") == "06:30"

    assert normalize_time("half past six in the evening") == "18:30"

    assert normalize_time("quarter past five") == "05:15"

    assert normalize_time("quarter past five PM") == "17:15"
    assert normalize_time("1-2-3-4-5-6-7-8-9-0") is None
    assert normalize_time("1234567890") is None
    assert normalize_time("haircut") is None


def test_date():

    today = date(2026, 10, 3)

    assert (
        normalize_date("today", today)
        == "2026-10-03"
    )

    assert (
        normalize_date("tomorrow", today)
        == "2026-10-04"
    )

    assert (
        normalize_date("Monday", today)
        == "2026-10-05"
    )


def test_date_should_not_be_time():
    assert normalize_time("October 5") is None
    assert normalize_time("December 12") is None