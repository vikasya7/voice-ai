from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from googleapiclient.errors import HttpError
from httplib2 import Response

from app.services import calendar_service

EVENT_ID = "4a8f6dc9661c4d0ba087e66c4253ac13"
START = datetime(2030, 6, 10, 10, tzinfo=timezone.utc)
END = START + timedelta(minutes=30)


def test_calendar_recovers_event_after_insert_response_times_out(monkeypatch):
    events = Mock()
    calendar = Mock()
    calendar.events.return_value = events
    monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: calendar)
    monkeypatch.setattr(calendar_service, "check_availability", lambda *_: {"available": True})
    saved_events = {}

    def get_event(*, calendarId, eventId):
        if eventId not in saved_events:
            raise HttpError(Response({"status": "404"}), b"{}")
        return saved_events[eventId]

    def insert_event(*, calendarId, body):
        saved_events[body["id"]] = body
        raise TimeoutError("response lost after event creation")

    events.get.side_effect = lambda **kwargs: Mock(execute=lambda: get_event(**kwargs))
    events.insert.side_effect = lambda **kwargs: Mock(execute=lambda: insert_event(**kwargs))

    for _ in range(2):
        result = calendar_service.book_calendar_event(
            "Demo caller", "Haircut", START, END, "2025550100",
            "demo@example.test", event_id=EVENT_ID,
        )
        assert result["event_id"] == EVENT_ID

    assert list(saved_events) == [EVENT_ID]
    events.insert.assert_called_once()


def test_calendar_reuses_event_id_when_first_insert_did_not_create_event(monkeypatch):
    events = Mock()
    calendar = Mock()
    calendar.events.return_value = events
    monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: calendar)
    monkeypatch.setattr(calendar_service, "check_availability", lambda *_: {"available": True})
    events.get.return_value.execute.side_effect = HttpError(Response({"status": "404"}), b"{}")
    events.insert.return_value.execute.side_effect = [
        TimeoutError("request timed out before event creation"),
        {"id": EVENT_ID, "start": {"dateTime": START.isoformat()}, "end": {"dateTime": END.isoformat()}},
    ]

    result = calendar_service.book_calendar_event(
        "Demo caller", "Haircut", START, END, "2025550100",
        "demo@example.test", event_id=EVENT_ID,
    )

    assert result["event_id"] == EVENT_ID
    assert [call.kwargs["body"]["id"] for call in events.insert.call_args_list] == [EVENT_ID, EVENT_ID]
