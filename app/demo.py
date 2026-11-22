"""Local, scripted demo of the voice receptionist's appointment workflows."""

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Rose Salon Receptionist Demo")

BOOKING_EMAIL = "demo@example.test"
HELP = (
    f"Welcome to Rose Salon. Try 'appointments', 'book YYYY-MM-DD HH:MM {BOOKING_EMAIL}', "
    "'reschedule ID YYYY-MM-DD HH:MM', 'cancel ID', or 'callback'."
)


class CallRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=300)


class CallResponse(BaseModel):
    intent: str
    response: str
    spoken_response: str
    sources: list[str] = Field(default_factory=list)


@dataclass
class PendingRequest:
    intent: Literal["booking", "reschedule", "cancel", "human"]
    appointment_id: int | None = None
    slot: datetime | None = None


@dataclass
class Session:
    appointments: dict[int, datetime] = field(default_factory=lambda: {
        1: datetime(2030, 6, 10, 10),
        2: datetime(2030, 6, 10, 11),
    })
    next_appointment_id: int = 3
    pending: PendingRequest | None = None
    callback_requested: bool = False


sessions: dict[str, Session] = {}
sessions_lock = Lock()


def format_slot(slot: datetime) -> str:
    return slot.strftime("%Y-%m-%d at %H:%M")


def slot_is_taken(session: Session, pending: PendingRequest) -> bool:
    return any(
        slot == pending.slot and appointment_id != pending.appointment_id
        for appointment_id, slot in session.appointments.items()
    )


def complete_request(session: Session, pending: PendingRequest) -> str:
    if pending.intent == "human":
        if session.callback_requested:
            return "A demo callback is already queued."
        session.callback_requested = True
        return "Demo callback queued. No email was sent."

    if pending.intent == "cancel":
        del session.appointments[pending.appointment_id]
        return f"Demo appointment {pending.appointment_id} cancelled."

    if slot_is_taken(session, pending):
        return "That demo time is already booked. Please choose another time."

    if pending.intent == "booking":
        appointment_id = session.next_appointment_id
        session.next_appointment_id += 1
        session.appointments[appointment_id] = pending.slot
        return (
            f"Demo appointment {appointment_id} booked for {format_slot(pending.slot)}. "
            f"Confirmation email to {BOOKING_EMAIL} was simulated."
        )

    session.appointments[pending.appointment_id] = pending.slot
    return f"Demo appointment {pending.appointment_id} moved to {format_slot(pending.slot)}."


def respond(session: Session, message: str) -> tuple[str, str]:
    pending = session.pending
    if pending:
        if message in {"yes", "no"}:
            session.pending = None
            response = complete_request(session, pending) if message == "yes" else "Okay, no changes made."
            return pending.intent, response
        return pending.intent, "Please reply 'yes' or 'no' to the pending request."

    if message == "appointments":
        entries = [
            f"{appointment_id}. {format_slot(slot)}"
            for appointment_id, slot in session.appointments.items()
        ]
        return "faq", "\n".join(entries) or "There are no demo appointments."
    if message == "callback":
        session.pending = PendingRequest("human")
        return "human", "Queue a simulated staff callback? Reply 'yes' or 'no'."

    parts = message.split()
    if not parts or parts[0] not in {"book", "reschedule", "cancel"}:
        return "other", HELP

    action = parts[0]
    intent = "booking" if action == "book" else action
    expected_count = {"book": 4, "reschedule": 4, "cancel": 2}
    if len(parts) != expected_count[action]:
        return intent, HELP

    appointment_id = None
    if action != "book":
        try:
            appointment_id = int(parts[1])
        except ValueError:
            return intent, "Enter the numeric appointment ID from 'appointments'."
        if appointment_id not in session.appointments:
            return intent, "That demo appointment was not found. Try 'appointments'."
    if action == "cancel":
        session.pending = PendingRequest("cancel", appointment_id)
        return intent, f"Cancel demo appointment {appointment_id}? Reply 'yes' or 'no'."

    if action == "book" and parts[3] != BOOKING_EMAIL:
        return intent, f"Use {BOOKING_EMAIL} as the confirmation email for the demo."
    date, time = parts[1:3] if action == "book" else parts[2:4]
    try:
        slot = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return intent, "Enter a valid date and time in YYYY-MM-DD HH:MM format."

    pending = PendingRequest(intent, appointment_id, slot)
    if slot_is_taken(session, pending):
        return intent, "That demo time is already booked. Please choose another time."
    session.pending = pending
    operation = "Book a demo appointment for" if action == "book" else f"Move demo appointment {appointment_id} to"
    return intent, f"{operation} {format_slot(slot)}? Reply 'yes' or 'no'."


@app.get("/")
def root():
    return {"message": HELP, "mode": "demo"}


@app.post("/call")
def handle_call(request: CallRequest) -> CallResponse:
    with sessions_lock:
        session = sessions.get(request.session_id)
        if session is None:
            session = sessions[request.session_id] = Session()
        intent, response = respond(session, request.message.strip().lower())
    return CallResponse(intent=intent, response=response, spoken_response=response)
