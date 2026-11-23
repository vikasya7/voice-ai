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
    *,
    event_id: str,
)->dict:
    """Create or recover the event allocated to a pending booking."""

    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")

    if start >= end:
        raise ValueError("end must be later than start")

    service = get_calendar_service()
    events = service.events()
    existing = _find_booking_event(events, calendar_id, event_id)
    if existing is not None:
        return _verify_booking_event(existing, event_id, start, end)

    availability = check_availability(start, end, calendar_id)
    if not availability["available"]:
        if any(conflict["id"] == event_id for conflict in availability["conflicts"]):
            # The event may have appeared between the GET and availability check.
            existing = _find_booking_event(events, calendar_id, event_id)
            return _verify_booking_event(existing, event_id, start, end)
        return {"success": False, "reason": "slot_unavailable", "conflict": availability["conflicts"]}

    event = {
        "id": event_id,
        "summary": f"{service_name}-{customer_name}",
        "description": (
            f"Customer: {customer_name}\n"
            f"Phone: {customer_phone}\n"
            f"Email: {customer_email or 'Not provided'}\n"
            f"Service: {service_name}"
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
    }

    for _ in range(2):
        try:
            created = events.insert(calendarId=calendar_id, body=event).execute()
        except (TimeoutError, ConnectionError):
            created = _find_booking_event(events, calendar_id, event_id)
        except HttpError as exc:
            if exc.resp.status not in {409, 429, 500, 502, 503, 504}:
                raise
            created = _find_booking_event(events, calendar_id, event_id)
        if created is not None:
            return _verify_booking_event(created, event_id, start, end)

    raise RuntimeError("Calendar booking outcome could not be verified")


def _find_booking_event(events, calendar_id: str, event_id: str) -> dict | None:
    try:
        return events.get(calendarId=calendar_id, eventId=event_id).execute()
    except HttpError as exc:
        if exc.resp.status != 404:
            raise
        return None


def _verify_booking_event(event: dict | None, event_id: str, start: datetime, end: datetime) -> dict:
    if event is None or event.get("id") != event_id or event.get("status") == "cancelled":
        raise RuntimeError("Calendar booking event could not be verified")
    for key, expected in (("start", start), ("end", end)):
        value = event.get(key, {}).get("dateTime", "")
        if not value or datetime.fromisoformat(value.replace("Z", "+00:00")) != expected:
            raise RuntimeError("Calendar booking event time differs from the pending booking")
    return {
        "success": True,
        "event_id": event_id,
        "event_link": event.get("htmlLink"),
        "start": event["start"],
        "end": event["end"],
    }



def delete_calendar_event(
    event_id: str,
    calendar_id: str = "primary",
) -> bool:
    """Delete a previously created calendar event."""

    service = get_calendar_service()

    try:
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

        return True

    except HttpError as exc:
        raise RuntimeError(
            f"Google Calendar event deletion failed: {exc}"
        ) from exc


def _patch_event_time(service, calendar_id, event_id, times, etag):
    request = service.events().patch(
        calendarId=calendar_id,
        eventId=event_id,
        body=times,
    )
    request.headers["If-Match"] = etag
    return request.execute()


def move_calendar_event(event_id: str, new_start: datetime, calendar_id: str = "primary"):
    """Move a timed event and return the information needed to restore it."""
    service = get_calendar_service()
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    if event.get("status") == "cancelled":
        raise ValueError("Calendar event is cancelled")

    previous_times = {key: event[key] for key in ("start", "end")}
    old_start = datetime.fromisoformat(previous_times["start"]["dateTime"].replace("Z", "+00:00"))
    old_end = datetime.fromisoformat(previous_times["end"]["dateTime"].replace("Z", "+00:00"))
    new_end = new_start + (old_end - old_start)
    availability = check_availability(new_start, new_end, calendar_id)
    if any(conflict["id"] != event_id for conflict in availability["conflicts"]):
        return None

    times = {
        key: {"dateTime": value.isoformat(), "timeZone": TIMEZONE}
        for key, value in (("start", new_start), ("end", new_end))
    }
    updated = _patch_event_time(service, calendar_id, event_id, times, event["etag"])
    return previous_times, updated["etag"]


def restore_calendar_event_time(event_id, previous_times, etag, calendar_id="primary"):
    """Restore event times if the event has not been edited since the move."""
    _patch_event_time(get_calendar_service(), calendar_id, event_id, previous_times, etag)
