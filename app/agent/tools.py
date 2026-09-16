
from datetime import datetime


# Fake appointment availability
AVAILABLE_SLOTS = {
    "10:00 AM": True,
    "11:00 AM": True,
    "2:00 PM": False,
    "3:00 PM": True,
    "5:00 PM": True,
    "6:00 PM": False,
}


def check_availability(
    appointment_date: str,
    appointment_time: str
) -> bool:

    # Check if the requested time exists
    if appointment_time not in AVAILABLE_SLOTS:
        return False

    return AVAILABLE_SLOTS[appointment_time]

