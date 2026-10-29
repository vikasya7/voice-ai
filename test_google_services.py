
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from google_auth import get_calendar_service, get_gmail_service
from calendar_service import check_availability
from email_service import send_email

TZ = ZoneInfo("Asia/Kolkata")


def main():
    print("1. Testing Google OAuth...")

    calendar = get_calendar_service()
    gmail = get_gmail_service()

    print("Calendar and Gmail service clients created.")

    print("\n2. Testing Calendar API...")

    now = datetime.now(TZ)

    result = calendar.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        maxResults=5,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    print(
        f"Calendar API OK. Events found: "
        f"{len(result.get('items', []))}"
    )

    print("\n3. Testing availability helper...")

    availability = check_availability(
        now + timedelta(days=1),
        now + timedelta(days=1, minutes=30),
    )

    print("Availability result:", availability)

    print("\n4. Gmail service client created.")
    print("No email has been sent yet.")

    # Optional: send an email only when explicitly configured.
    recipient = os.getenv("TEST_EMAIL_TO")

    if recipient:
        result = send_email(
            to_email=recipient,
            subject="Voice Agent — Gmail integration test",
            body="This is a test email from your FastAPI voice agent.",
        )
        print("Test email sent. Message ID:", result["message_id"])
    else:
        print(
            "Skipping email test. "
            "Set TEST_EMAIL_TO to send a test email."
        )


if __name__ == "__main__":
    main()
