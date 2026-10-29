from datetime import datetime
from zoneinfo import ZoneInfo

from googleapiclient.errors import HttpError

from google_auth import get_calendar_service

TIMEZONE="Asia/Kolkata"


def check_availability(
    start:datetime,
    end:datetime,
    calendar_id:str="primary"
)->dict:
    """Check whether the requested interval overlaps calendar events"""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone aware")

    if start>=end:
        raise ValueError("end must be later than start")

    service=get_calendar_service()
    try:
        result=service.events().list(
            calendarId=calendar_id,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        conflicts=[
            {
                "id":event.get("id"),
                "summary":event.get("summary","Busy"),
                "start":event.get("start",{}),
                "end":event.get("end",{})
            }
            for event in result.get("items",[])
            if event.get("status")!="cancelled"
        ]

        return {
            "available":len(conflicts)==0,
            "conflicts":conflicts
        }

    except HttpError as exc:
        raise RuntimeError(
            f"Google Calendar availability check failed: {exc}"
        ) from exc


def book_calendar_event(
    customer_name:str,
    service_name:str,
    start:datetime,
    end:datetime,
    customer_phone:str,
    customer_email:str | None=None,
    calendar_id:str="primary",
)->dict:
    """Create a calendar event after checking for conflicts"""

    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")

    if start >= end:
        raise ValueError("end must be later than start")

    availability = check_availability(start, end, calendar_id)

    if not availability["available"]:
        return {
            "success":False,
            "reason":"slot_unavailable",
            "conflict":availability["conflicts"]
        }

    service=get_calendar_service()

    event={
        "summary":f"{service_name}-{customer_name}",
        "description":(
            f"Customer:{customer_name}\n",
            f"Phone: {customer_phone}\n",
            f"Email:{customer_email} or 'Not provided'",
            f"Service: {service_name}"
        ),
        "start":{
            "dateTime":start.isoformat(),
            "timezone":TIMEZONE
        },
        "end":{
            "dateTime":end.isoformat(),
            "timezone":TIMEZONE
        }

    }


    try:
        created=service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()


        return {
            "success":True,
            "event_id":created["id"],
            "event_link":created.get("htmlLink"),
            "start":created["start"],
            "end":created["end"]
        }
    except HttpError as exc:
        raise RuntimeError(
            f"Google Calendar event creation failed: {exc}"
        ) from exc