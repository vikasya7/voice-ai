
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from app.voice.normalization import normalize_phone
from app.agent.state import AgentState, AppointmentDetails,RescheduleDetails,LeadDetails
from app.agent.tools import (
    check_availability,
    book_appointment,
    find_appointment,
    find_appointments,
    cancel_appointment,
    reschedule_appointment,
    save_lead,
    create_human_handoff
)
from app.rag.knowledge import get_retriever

load_dotenv()


# =========================================================
# LLM
# =========================================================

llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0,
)


# =========================================================
# INTENT CLASSIFICATION
# =========================================================

class IntentResult(BaseModel):
    intent: Literal[
        "booking",
        "assistant",
        "cancel",
        "reschedule",
        "faq",
        "lead",
        "human",
        "other"
    ]


intent_llm = llm.with_structured_output(IntentResult)


class CancellationDetails(BaseModel):
    customer_phone: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None

cancellation_details_llm = llm.with_structured_output(
    CancellationDetails
)


def intent_node(state: AgentState):
    user_message = state["messages"][-1].content

    # Include recent conversation context
    conversation = "\n".join(
        f"{'Customer' if msg.type == 'human' else 'Assistant'}: {msg.content}"
        for msg in state["messages"][-6:]
    )

    result = intent_llm.invoke(
        f"""
You are an intent classifier for a business receptionist.

Classify the customer's LATEST message into exactly ONE category.

Categories:
- booking: Creating a new appointment.
- cancel: Cancelling an existing appointment.
- reschedule: Changing an existing appointment.
- faq: Asking about the business's services, policies, hours, or pricing.
- lead: Expressing interest in the business or its services.
- human: Asking to speak to a human.
- assistant: General knowledge, calculations, web searches, or
  other general-purpose assistance.
- other: Anything that does not fit the categories above.

Important rules:
1. Use the conversation history to understand short replies.
2. If the customer is answering the assistant's previous question,
   classify based on the ongoing conversation.
3. "To gain weight" after a question about calorie goals is
   a continuation of the general assistance conversation: assistant.
4. Never classify a cancellation request as lead.
5. Questions about business services, pricing, and hours are faq.
6. Classify only the latest customer message, not the assistant's message.

Recent conversation:
{conversation}

Latest customer message:
{user_message}
"""
    )

    print("🎯 CLASSIFIED INTENT:", result.intent)

    updates = {
    "intent": result.intent
    }

    if result.intent == "cancel":
        updates["cancellation_date"] = ""
        updates["cancellation_time"] = ""

    return updates



# =========================================================
# RECEPTIONIST
# =========================================================

def receptionist_node(state: AgentState):

    response = llm.invoke(
        state["messages"]
    )

    return {
        "messages": [response]
    }


# =========================================================
# APPOINTMENT DETAIL EXTRACTION
# =========================================================

details_llm = llm.with_structured_output(
    AppointmentDetails
)

from datetime import datetime
from app.voice.normalization import (
    normalize_phone,
    normalize_time,
    normalize_date,
)
import re
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
def extract_appointment_details(state: AgentState):
    user_message = state["messages"][-1].content

    now = datetime.now()

    current_date = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")
    current_time = now.strftime("%H:%M")

    # ---------------------------------------------------------
    # ONLY EXTRACT FIELDS THAT ARE STILL MISSING
    # ---------------------------------------------------------

    missing_fields = []

    if not state.get("customer_name"):
        missing_fields.append("customer_name")

    if not state.get("customer_phone"):
        missing_fields.append("customer_phone")

    if not state.get("service"):
        missing_fields.append("service")

    if not state.get("appointment_date"):
        missing_fields.append("appointment_date")

    if (not state.get("appointment_time") or state.get("awaiting_new_time",False)):
        missing_fields.append("appointment_time")

    if not state.get("customer_email"):
        missing_fields.append("customer_email")

    print("🔎 Missing appointment fields:", missing_fields)

    # Nothing left to extract
    if not missing_fields:
        print("✅ All appointment details already collected")
        return {}

    # ---------------------------------------------------------
    # BUILD EXTRACTION PROMPT ONLY FOR MISSING FIELDS
    # ---------------------------------------------------------

    fields_text = "\n".join(
        f"- {field}"
        for field in missing_fields
    )
    print("🧠 Sending details extraction to LLM...")
    print("📝 Message:", user_message)
    print("🎯 Fields:", missing_fields)

    result = details_llm.invoke(
        f"""
You extract appointment information from a customer's message.

ONLY extract these missing fields:

{fields_text}

If a value is not provided, return null.

EMAIL RULES:
- Extract the customer's email address if provided.
- Preserve the exact email address.
- Do not guess or invent an email address.
- If no email is provided, return null.

IMPORTANT:
Do NOT invent information.

IMPORTANT PHONE NUMBER RULES:
- Convert spoken digits into numeric digits.
- Keep phone numbers as digits only.
- Do not interpret phone numbers as dates or times.

IMPORTANT TIME RULES:
Convert appointment times into 24-hour HH:MM format.

Examples:
"5 PM" → "17:00"
"5 p.m." → "17:00"
"6 PM" → "18:00"
"six in the evening" → "18:00"
"10 AM" → "10:00"
"10 p.m." → "22:00"
"12 PM" → "12:00"
"12 AM" → "00:00"
"half past 6" → "18:30"
"quarter past 5" → "17:15"
"quarter to 6" → "17:45"

IMPORTANT DATE RULES:
Convert relative dates into YYYY-MM-DD.

Current date: {current_date}
Current day: {current_day}
Current time: {current_time}

Examples:
"today" → today's date
"tomorrow" → tomorrow's date
"Monday" → next Monday
"next Friday" → next Friday

SERVICE EXAMPLES:
"haircut" → "haircut"
"hair spa" → "hair spa"
"hairspa" → "hairspa"

NAME EXAMPLES:
"My name is Vikas" → customer_name = "Vikas"
"I am Vikas Yadav" → customer_name = "Vikas Yadav"

PHONE EXAMPLES:
"My number is 9876543210" → customer_phone = "9876543210"
"one two three four five six seven eight nine zero"
→ customer_phone = "1234567890"

IMPORTANT:
Do not interpret phone-number digits as appointment time.
Do not extract fields that were not requested.

Customer message:
{user_message}
"""
    )

    updates = {}

    # ---------------------------------------------------------
    # CUSTOMER NAME
    # ---------------------------------------------------------

    if (
        "customer_name" in missing_fields
        and result.customer_name
        and not state.get("customer_name")
    ):
        updates["customer_name"] = result.customer_name

    # ---------------------------------------------------------
    # CUSTOMER PHONE
    # ---------------------------------------------------------

    if (
        "customer_phone" in missing_fields
        and result.customer_phone
        and not state.get("customer_phone")
    ):
        normalized_phone = normalize_phone(
            result.customer_phone
        )

        if normalized_phone:
            updates["customer_phone"] = normalized_phone


    # ---------------------------------------------------------
# CUSTOMER EMAIL
# ---------------------------------------------------------

    if (
        "customer_email" in missing_fields
        and result.customer_email
        and not state.get("customer_email")
    ):
        email = result.customer_email.strip()

        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            updates["customer_email"] = email

    # ---------------------------------------------------------
    # SERVICE
    # ---------------------------------------------------------

    if (
        "service" in missing_fields
        and result.service
        and not state.get("service")
    ):
        updates["service"] = result.service

    # ---------------------------------------------------------
    # DATE
    # ---------------------------------------------------------

    if (
        "appointment_date" in missing_fields
        and not state.get("appointment_date")
    ):

        # First try deterministic parsing from
        # the actual customer message.
        normalized_date = normalize_date(
            user_message,
            today=now.date(),
        )

        if normalized_date:
            updates["appointment_date"] = normalized_date

        elif result.appointment_date:

            normalized_date = normalize_date(
                result.appointment_date,
                today=now.date(),
            )

            if normalized_date:
                updates["appointment_date"] = normalized_date

    # ---------------------------------------------------------
    # TIME
    # ---------------------------------------------------------

    if (
        "appointment_time" in missing_fields
    ):

        normalized_time = normalize_time(
            user_message
        )

        print("🕐 TIME DEBUG")
        print("User message:", user_message)
        print("Normalized time:", normalized_time)

        if normalized_time:
            updates["appointment_time"] = normalized_time
            updates["awaiting_new_time"] = False

        elif result.appointment_time:
            normalized_time = normalize_time(
                result.appointment_time
            )

            if normalized_time:
                updates["appointment_time"] = normalized_time
                updates["awaiting_new_time"] = False

    # ---------------------------------------------------------
    # DEBUG
    # ---------------------------------------------------------

    print("📦 EXTRACTION UPDATES:", updates)

    return updates


# =========================================================
# BOOKING NODE
# =========================================================




def booking_node(state: AgentState):

    customer_name = state.get("customer_name", "")
    customer_phone = state.get("customer_phone", "")
    service = state.get("service", "")
    appointment_date = state.get("appointment_date", "")
    appointment_time = state.get("appointment_time", "")

    if not customer_name:
        return {
            "messages": [
                AIMessage(content="Sure. May I have your name?")
            ],
            "booking_in_progress": True,
        }

    if not customer_phone:
        return {
            "messages": [
                AIMessage(
                    content="Thanks. Could you please provide your phone number?"
                )
            ],
            "booking_in_progress": True,
        }

    # Normalize phone number
    normalized_phone = normalize_phone(customer_phone)

    if len(normalized_phone) != 10:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I didn't get the complete phone number. "
                        "Could you please provide your 10-digit phone number?"
                    )
                )
            ],
            "booking_in_progress": True,
        }

    # Store normalized phone number in graph state
    customer_phone = normalized_phone

    if not service:
        return {
            "messages": [
                AIMessage(content="What service would you like to book?")
            ],
            "booking_in_progress": True,
        }

    if not appointment_date:
        return {
            "messages": [
                AIMessage(
                    content="What date would you like the appointment?"
                )
            ],
            "booking_in_progress": True,
        }

    if not state.get("customer_email"):
        return {
        "messages": [
            AIMessage(
                content="Could you please provide your email address "
                        "so I can send your booking confirmation?"
            )
        ],
        "booking_in_progress": True,
        }

    if not appointment_time:
        return {
            "messages": [
                AIMessage(
                    content="What time would you prefer?"
                )
            ],
            "booking_in_progress": True,
        }

    is_available = check_availability.invoke({
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
    })

    if not is_available:
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"Sorry, {appointment_time} is already booked "
                        f"on {appointment_date}. "
                        f"What other time would you prefer?"
                    )
                )
            ],
            "booking_in_progress": True,
            "awaiting_new_time":True,
            "awaiting_confirmation": False,
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Great, {appointment_time} is available "
                    f"on {appointment_date}. "
                    f"I have you down for {service}. "
                    f"Shall I book the appointment?"
                )
            )
        ],
        "customer_phone": customer_phone,
        "booking_in_progress": False,
        "awaiting_confirmation": True,
    }





# =========================================================
# CONFIRMATION CLASSIFIER
# =========================================================

class ConfirmationResult(BaseModel):

    confirmed: bool


confirmation_llm = llm.with_structured_output(
    ConfirmationResult
)



def confirmation_node(state: AgentState):
    user_message = state["messages"][-1].content

    result = confirmation_llm.invoke(
        f"""
Determine whether the customer is confirming
the appointment booking.

Return confirmed=true when the customer clearly
agrees to book.

Examples:
"yes" -> true
"book it" -> true
"confirm" -> true
"go ahead" -> true
"yes please" -> true

Return confirmed=false when the customer declines
or is not clearly confirming.

Examples:
"no" -> false
"not now" -> false
"I don't want it" -> false

Customer message:
{user_message}
"""
    )

    if result.confirmed:
        return {
            "booking_confirmed": True,
        }

    return {
        "booking_confirmed": False,
        "awaiting_confirmation": False,
        "messages": [
            AIMessage(
                content=(
                    "No problem. I won't book it. "
                    "Let me know if you'd like to choose "
                    "another appointment time."
                )
            )
        ],
    }




# =========================================================
# ACTUAL BOOKING
# =========================================================

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.calendar_service import (
    book_calendar_event,
    delete_calendar_event
)
from app.agent.tools import (
    confirm_appointment,
    mark_appointment_failed
)
from app.services.email_service import send_booking_confirmation


def confirm_booking_node(state: AgentState):

    result = book_appointment.invoke({
      "session_id":state.get("session_id",""),
      "customer_name":state.get("customer_name","Customer"),
      "customer_phone":state.get("customer_phone"),
      "customer_email":state.get("customer_email"),
      "appointment_date":state["appointment_date"],
      "appointment_time":state["appointment_time"],
      "service":state["service"],
      "duration_minutes":30
    })

    if not result["success"]:
        return {
            "awaiting_confirmation":False,
            "booking_confirmed":False,
            "messages":[
                AIMessage(content=result["message"])
            ],
        }

    appointment_id=result["appointment_id"]
    calendar_event_id=None

    try:
        # 2 contruct timezone-aware start and end
        timezone=ZoneInfo("Asia/Kolkata")
        start=datetime.strptime(
            f"{state['appointment_date']} {state['appointment_time']}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=timezone)


        end=start + timedelta(minutes=30)

        #3 Create google calendar event 
        calendar_result=book_calendar_event(
            customer_name=state.get("customer_name","Customer"),
            service_name=state.get("service") or "Appointment",
            start=start,
            end=end,
            customer_phone=state.get("customer_phone") or "",
            customer_email=state.get("customer_email")
        )

        if not calendar_result["success"]:
            mark_appointment_failed(appointment_id)

            return {
                "awaiting_confirmation":False,
                "booking_confirmed":False,
                "messages":[
                    AIMessage(
                        content="Sorry, that time slot is unavailable in our calendar. Please choose another time."
                    )
                ]
            }

        calendar_event_id=calendar_result["event_id"]

        #4 Confirm appointment in postgresql
        confirmed=confirm_appointment(
            appointment_id,
            calendar_event_id
        )

        if not confirmed:
            raise RuntimeError(
                "Could not confirm appointment in database"
            )

        # Send confirmation email only if customer provided an email

        email_sent=False
        customer_email = state.get("customer_email")

        if customer_email:
            try:
                email_result=send_booking_confirmation(
                    customer_name=state.get("customer_name", "Customer"),
                    to_email=customer_email,
                    service_name=state.get("service") or "Appointment",
                    appointment_start=(
                       f"{state.get('appointment_date')} "
                       f"at {state.get('appointment_time')}"
                    ),
                )

                email_sent = email_result.get("success", False)
                print("Booking confirmation email sent:", email_result)
            except Exception as email_error:
                print("Booking email failed:", email_error)


        return {
            "awaiting_confirmation":False,
            "booking_confirmed":True,
            "messages":[
                AIMessage(
                    content=(
                        f"Your appointment is confirmed for "
                        f"{state['appointment_date']} at "
                        f"{state['appointment_time']}. "
                        f"Your appointment ID is {appointment_id}."
                    )
                )
            ]
        }
    except Exception as exc:
        print(f"Booking integration error: {exc}")


        # 5 clean calendar event if it was created

        if calendar_event_id:
            try:
                delete_calendar_event(calendar_event_id)
            except Exception as cleanup_error:
                print(f"Calendar cleanup failed: {cleanup_error}")

        mark_appointment_failed(appointment_id)

        return {
            "awaiting_confirmation": False,
            "booking_confirmed": False,
            "messages": [
                AIMessage(
                    content=(
                        "Sorry, we couldn't complete your booking "
                        "because of a technical issue. Please try again."
                    )
                )
            ],
        }
        



# =========================================================
# FAQ
# =========================================================

def faq_node(
    state: AgentState
):

    return {
        "messages": [
            AIMessage(
                content=(
                    "Sure, I can help answer "
                    "your question."
                )
            )
        ]
    }


# =========================================================
# LEAD
# =========================================================

def lead_node(
    state: AgentState
):

    return {
        "messages": [
            AIMessage(
                content=(
                    "Sure, I'd be happy to get "
                    "some details from you."
                )
            )
        ]
    }


# =========================================================
# HUMAN HANDOFF
# =========================================================

def human_node(
    state: AgentState
):

    return {
        "messages": [
            AIMessage(
                content=(
                    "Sure, I'll connect you with "
                    "a human representative."
                )
            )
        ]
    }


# =========================================================
# OTHER
# =========================================================

def other_node(
    state: AgentState
):

    return {
        "messages": [
            AIMessage(
                content=(
                    "I'm sorry, I didn't quite "
                    "understand that."
                )
            )
        ]
    }


# =========================================================
# INTENT ROUTER
# =========================================================

def route_intent(
    state: AgentState
):

    return state["intent"]


from app.voice.normalization import normalize_time
def extract_cancellation_details(state: AgentState):

    print("🔥 EXTRACT CANCELLATION DETAILS")

    user_message = state["messages"][-1].content

    
    result = cancellation_details_llm.invoke(
    f"""
Extract the customer's phone number, appointment date, and appointment time.

Today's date is 2026-11-02.
The business timezone is Asia/Kolkata.

Rules:
- Convert relative dates and dates like "November 3" into YYYY-MM-DD.
- For "November 3", use 2026-11-03.
- Convert time into HH:MM using 24-hour format.
- Return null for information not provided.
- Do not guess missing information.

Customer message:
{user_message}
"""
    )
    print("CUSTOMER MESSAGE:", user_message)
    print("EXTRACTED DATE:", result.appointment_date)
    print("EXTRACTED TIME:", result.appointment_time)

    print("🔥 EXTRACTED:", result)

    updates = {}

    if result.customer_phone:
        updates["customer_phone"] = result.customer_phone

    if result.appointment_date:
        updates["cancellation_date"]  = result.appointment_date

    if result.appointment_time:
        updates["cancellation_time"] = normalize_time(
            result.appointment_time
        )

    print("🔥 CANCELLATION UPDATES:", updates)

    return updates


def cancellation_node(state: AgentState):
    customer_phone = state.get("customer_phone", "")
    appointment_date = state.get("cancellation_date", "")
    appointment_time = state.get("cancellation_time", "")
    print("PHONE:", customer_phone)
    print("CANCELLATION DATE:", appointment_date)
    print("CANCELLATION TIME:", appointment_time)

    

    if not customer_phone:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Sure. Please provide the phone number "
                        "associated with your appointment."
                    )
                )
            ],
            "cancellation_in_progress": True,
        }

    print("FILTERS BEING SENT:", {
    "customer_phone": customer_phone,
    "appointment_date": appointment_date or None,
    "appointment_time": appointment_time or None
    })

    appointments = find_appointments.invoke({
    "customer_phone": customer_phone,
    "appointment_date": appointment_date or None,
    "appointment_time": appointment_time or None,
    })

    if not appointments:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I couldn't find a confirmed appointment with those details. Could you check the phone number, date, or time?"
                    )
                )
            ],
            "cancellation_in_progress": True,
        }

    if len(appointments)>1:
        options="\n".join(
            f"- {a['appointment_date']} at {a['appointment_time']}"
            for a in appointments
        )

        return {
            "messages": [
                AIMessage(
                    content=(
                        "I found multiple appointments associated with your number:\n"
                        f"{options}\n\n"
                        "Which appointment would you like to cancel? "
                        "Please tell me the date and time."
                    )
                )
            ],
            "cancellation_in_progress": True,
            "awaiting_cancellation_confirmation": False,
        }
    # exactly one appointment found
    appointment=appointments[0]


    return {
        "messages": [
            AIMessage(
                content=(
                    f"I found your appointment for "
                    f"{appointment['appointment_date']} at "
                    f"{appointment['appointment_time']}. "
                    "Would you like me to cancel it?"
                )
            )
        ],
        "appointment_date": appointment["appointment_date"],
        "appointment_time": appointment["appointment_time"],
        "cancellation_in_progress": False,
        "selected_appointment_id": appointment["id"],
        "awaiting_cancellation_confirmation": True,
    }

def cancellation_confirmation_node(state: AgentState):
    user_message = state["messages"][-1].content

    result = confirmation_llm.invoke(
        f"""
Determine whether the customer clearly confirms
that they want to cancel their appointment.

Return confirmed=true for:

"yes"
"cancel it"
"yes please"
"go ahead"
"confirm"

Return confirmed=false for:

"no"
"don't cancel"
"not now"

Customer message:

{user_message}
"""
    )

    if result.confirmed:
        return {
            "cancellation_confirmed": True
        }

    return {
        "cancellation_confirmed": False,
        "awaiting_cancellation_confirmation": False,
        "messages": [
            AIMessage(
                content="No problem. I won't cancel your appointment."
            )
        ],
    }

from app.services.calendar_service import delete_calendar_event
from app.agent.tools import get_appointment_by_id
def confirm_cancellation_node(state: AgentState):

    print("🔥🔥🔥 CONFIRM CANCELLATION NODE EXECUTED")
    appointment_id=state.get("selected_appointment_id")
    customer_phone=state.get("customer_phone")

    # 1 Validate state
    if appointment_id is None or not customer_phone:
        return {
            "awaiting_cancellation_confirming":False,
            "cancellation_confirmed":False,
            "messages": [
                AIMessage(
                    content="I couldn't identify the appointment. Please try again."
                )
            ],
        }

    # 2 Retrieves the exact apoointment by id
    appointment=get_appointment_by_id.invoke({
        "appointment_id":appointment_id,
        "customer_phone":customer_phone
    })

    print("APPOINTMENT FOUND:", appointment)

    if not appointment:
        return {
            "awaiting_cancellation_confirmation":False,
            "cancellation_confirmed":False,
            "messages": [
                AIMessage(
                    content="I couldn't find a confirmed appointment with those details."
                )
            ],
        }
    # Step 3 : Delete google calendar event

    if appointment["calendar_event_id"]:
        try:
            delete_calendar_event(
                appointment["calendar_event_id"]
            )
            print("Google Calendar event deleted successfully")
        except Exception as e:
            print("❌ Google Calendar deletion failed:", repr(e))

            return {
                "awaiting_cancellation_confirmation":False,
                "cancellation_confirmed":False,
                 "messages": [
                    AIMessage(
                        content=(
                            "I couldn't cancel your appointment because "
                            "there was a problem updating Google Calendar. "
                            "Please try again."
                        )
                    )
                ],
            }

    # step 4 updating the database
    result=cancel_appointment.invoke({
            "appointment_id":appointment["id"]
    })

    if not result["success"]:
        return {
            "awaiting_cancellation_confirmation": False,
            "cancellation_confirmed": False,
            "messages": [
                AIMessage(content=result["message"])
            ],
        }
         # Step 5: Return success
    return {
        "awaiting_cancellation_confirmation": False,
        "cancellation_confirmed": True,
        "cancellation_in_progress": False,
        "selected_appointment_id": None,
        "messages": [
            AIMessage(
                content=(
                    f"Your appointment for "
                    f"{appointment['appointment_date']} at "
                    f"{appointment['appointment_time']} "
                    f"has been cancelled successfully."
                )
            )
        ],
    }


reschedule_details_llm = llm.with_structured_output(
    RescheduleDetails
)


def extract_reschedule_details(state: AgentState):
    print("🔥 EXTRACT RESCHEDULE DETAILS")

    user_message = state["messages"][-1].content

    result = reschedule_details_llm.invoke(
        f"""
Extract rescheduling information from the customer's message.

Extract:

- customer_phone
- appointment_date
- appointment_time

For appointment_date and appointment_time,
extract the NEW date and NEW time that the customer
wants to reschedule to.

If a value is not provided, return null.

Examples:

"I want to reschedule my appointment"
→ customer_phone = null
→ appointment_date = null
→ appointment_time = null

"My phone number is 9876543210"
→ customer_phone = 9876543210
→ appointment_date = null
→ appointment_time = null

"Move it to tomorrow at 6 PM"
→ appointment_date = tomorrow's date
→ appointment_time = 18:00

"My number is 9876543210, move my appointment
to tomorrow at 6 PM"
→ customer_phone = 9876543210
→ appointment_date = tomorrow's date
→ appointment_time = 18:00

Customer message:
{user_message}
"""
    )

    print("🔥 RESCHEDULE EXTRACTED:", result)

    updates = {}

    if result.customer_phone:
        updates["customer_phone"] = result.customer_phone

    if result.appointment_date:
        updates["appointment_date"] = result.appointment_date

    if result.appointment_time:
        updates["appointment_time"] = result.appointment_time

    return updates


def reschedule_node(state:AgentState):
    customer_phone=state.get("customer_phone","")
    new_date=state.get("appointment_date","")
    new_time=state.get("appointment_time","")

    print("🔥 RESCHEDULE NODE")
    print("PHONE:", customer_phone)
    print("NEW DATE:", new_date)
    print("NEW TIME:", new_time)

    # ask for phone number
    if not customer_phone:
        return {
            "messages":[
                AIMessage(
                    content=
                    "Sure. Please provide the phone number "
                        "associated with your appointment."
                )
            ],
            "reschedule_in_progress": True,
        }
    # 2. Ask for new date
    if not new_date:
        return {
            "messages": [
                AIMessage(
                    content="What new date would you like for your appointment?"
                )
            ],
            "reschedule_in_progress": True,
        }

    # 3. Ask for new time
    if not new_time:
        return {
            "messages": [
                AIMessage(
                    content="What new time would you prefer?"
                )
            ],
            "reschedule_in_progress": True,
        }
    # 4. Find existing appointment
    appointment = find_appointment.invoke({
        "customer_phone": customer_phone,
    })

    if not appointment:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I couldn't find a confirmed appointment "
                        "with that phone number."
                    )
                )
            ],
            "reschedule_in_progress": False,
        }

    # 5. Check whether new slot is available
    is_available = check_availability.invoke({
        "appointment_date":new_date,
        "appointment_time":new_time
    })
    if not is_available:
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"Sorry, {new_time} on {new_date} "
                        "is already booked. "
                        "What other time would you prefer?"
                    )
                )
            ],
            "reschedule_in_progress": True,
        }

    # 6. Ask for confirmation
    return {
        "messages": [
            AIMessage(
                content=(
                    f"I found your appointment for "
                    f"{appointment.appointment_date} at "
                    f"{appointment.appointment_time}. "
                    f"Would you like to move it to "
                    f"{new_date} at {new_time}?"
                )
            )
        ],
        "reschedule_in_progress": False,
        "awaiting_reschedule_confirmation": True,
    }


def reschedule_confirmation_node(state:AgentState):
    print("🔥 RESCHEDULE CONFIRMATION NODE")

    user_message = state["messages"][-1].content

    result = confirmation_llm.invoke(
        f"""
Determine whether the customer clearly confirms
that they want to reschedule their appointment.

Return confirmed=true for:
"yes"
"yes please"
"go ahead"
"confirm"
"move it"

Return confirmed=false for:
"no"
"don't change it"
"not now"

Customer message:
{user_message}
"""
    )
    print("🔥 RESCHEDULE CONFIRMATION RESULT:", result)
    if result.confirmed:
        return {
            "reschedule_confirmed":True
        }

    return {
        "reschedule_confirmed": False,
        "awaiting_reschedule_confirmation": False,
        "messages": [
            AIMessage(
                content=(
                    "No problem. I won't change your appointment."
                )
            )
        ],
    }
    

def confirm_reschedule_node(state:AgentState):
    print("🔥 CONFIRM RESCHEDULE")

    customer_phone = state.get("customer_phone", "")
    new_date = state.get("appointment_date", "")
    new_time = state.get("appointment_time", "")

    appointment = find_appointment.invoke({
        "customer_phone": customer_phone,
    })
    if not appointment:
        return {
            "awaiting_reschedule_confirmation": False,
            "reschedule_confirmed": False,
            "messages": [
                AIMessage(
                    content="I couldn't find your appointment."
                )
            ],
        }

    result = reschedule_appointment.invoke({
        "appointment_id":appointment.id,
        "new_date":new_date,
        "new_time":new_time,
    })
    
    if not result["success"]:
        return {
            "awaiting_reschedule_confirmation": False,
            "reschedule_confirmed": False,
            "messages": [
                AIMessage(
                    content=result["message"]
                )
            ],
        }

    return {
        "awaiting_reschedule_confirmation": False,
        "reschedule_confirmed": True,
        "messages": [
            AIMessage(
                content=(
                    f"Your appointment has been rescheduled "
                    f"to {new_date} at {new_time} successfully."
                )
            )
        ],
    }


FAQS = {
    "opening_hours": """
We are open Monday to Saturday from 9 AM to 7 PM.
We are closed on Sundays.
""",

    "location": """
We are located at 123 Main Street.
""",

    "services": """
We provide haircuts, hair styling, beard trimming,
and grooming services.
""",

    "payment": """
We accept cash, UPI, and card payments.
""",
}


retriever = get_retriever()


def faq_node(state: AgentState):
    user_message = state["messages"][-1].content

    docs = retriever.invoke(user_message)

    context = "\n\n".join(
        doc.page_content
        for doc in docs
    )

    response = llm.invoke(
        f"""
You are a helpful receptionist.

Answer the customer's question using ONLY
the following business information.

BUSINESS INFORMATION:
{context}

If the information needed to answer the question
is not available, say:

"I'm sorry, I don't have that information right now."

Do not invent business information.

Customer question:
{user_message}
"""
    )

    return {
        "messages": [
            AIMessage(content=response.content)
        ]
    }


lead_details_llm = llm.with_structured_output(LeadDetails)


def extract_lead_details(state: AgentState):
    print("🔥 EXTRACT LEAD DETAILS")

    user_message = state["messages"][-1].content

    result = lead_details_llm.invoke(
        f"""
Extract lead/customer information from the customer's message.

Extract:
- customer_name
- customer_phone
- service
- preferred_time
- requirement

If a value is not provided, return null.

Examples:

"My name is Vikas"
→ customer_name = Vikas

"My number is 9876543210"
→ customer_phone = 9876543210

"I'm interested in hair spa"
→ service = hair spa

"I want to visit Saturday evening"
→ preferred_time = Saturday evening

"I want to know about hair treatment for damaged hair"
→ requirement = hair treatment for damaged hair

Customer message:
{user_message}
"""
    )

    print("🔥 LEAD EXTRACTED:", result)

    updates = {}

    if result.customer_name:
        updates["customer_name"] = result.customer_name

    if result.customer_phone:
        updates["customer_phone"] = result.customer_phone

    if result.service:
        updates["service"] = result.service

    if result.preferred_time:
        updates["preferred_time"] = result.preferred_time

    if result.requirement:
        updates["requirement"] = result.requirement

    return updates





def lead_node(state: AgentState):
    customer_name = state.get("customer_name", "")
    customer_phone = state.get("customer_phone", "")
    service = state.get("service", "")
    preferred_time = state.get("preferred_time", "")
    requirement = state.get("requirement", "")

    if not customer_name:
        return {
            "messages": [
                AIMessage(content="Sure. May I have your name?")
            ],
            "lead_in_progress": True,
        }

    if not customer_phone:
        return {
            "messages": [
                AIMessage(
                    content="What is the best phone number to reach you?"
                )
            ],
            "lead_in_progress": True,
        }

    if not service:
        return {
            "messages": [
                AIMessage(
                    content="What service are you interested in?"
                )
            ],
            "lead_in_progress": True,
        }

    if not preferred_time:
        return {
            "messages": [
                AIMessage(
                    content="When would you prefer to visit?"
                )
            ],
            "lead_in_progress": True,
        }

    # All required information collected
    result = save_lead.invoke({
    "session_id": state["session_id"],
    "customer_name": customer_name,
    "customer_phone": customer_phone,
    "service": service,
    "preferred_time": preferred_time,
    "requirement": requirement,
    })

    if not result["success"]:
        return {
            "messages": [
                AIMessage(
                    content="I'm sorry, I couldn't save your information. Please try again."
                )
            ],
            "lead_in_progress": False,
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Thanks, {customer_name}. I've noted your interest "
                    f"in {service}. Our team will contact you at "
                    f"{customer_phone}. Your lead reference is "
                    f"{result['lead_id']}."
                )
            )
        ],
        "lead_in_progress": False,
        "lead_saved": True,
    }


def human_node(state:AgentState):
    customer_name=state.get("customer_name","")
    customer_phone=state.get("customer_phone","")

    result=create_human_handoff.invoke({
        "session_id":state["session_id"],
        "customer_name":customer_name,
        "customer_phone":customer_phone,
        "reason": "Customer requested human assistance",
    })
    if not result["success"]:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I'm sorry, I couldn't connect your request "
                        "to our team right now. Please try again."
                    )
                )
            ]
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    "Sure. I've forwarded your request to our team. "
                    "Someone will assist you shortly."
                )
            )
        ]
    }