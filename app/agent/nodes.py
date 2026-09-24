
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage

from app.agent.state import AgentState, AppointmentDetails
from app.agent.tools import (
    check_availability,
    book_appointment,
    find_appointment,
    cancel_appointment
)


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
        "cancel",
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

    result = intent_llm.invoke(
        f"""
You are an intent classifier for a business receptionist.

Classify the customer's message into exactly ONE category.

Categories:

booking:
The customer wants to create or make a NEW appointment.

Examples:
- "I want to book an appointment"
- "Can I schedule a haircut?"
- "I need an appointment tomorrow"

cancel:
The customer wants to CANCEL an EXISTING appointment.

Examples:
- "I want to cancel my appointment"
- "Cancel my booking"
- "I need to cancel my appointment"
- "Please cancel my appointment"
- "I don't want my appointment anymore"
- "Can you cancel my booking?"

faq:
The customer is asking a general question about the business.

Examples:
- "What time do you open?"
- "How much does a haircut cost?"
- "Where are you located?"

lead:
The customer is interested in the business but is NOT asking to book
or cancel an appointment.

Examples:
- "I'm interested in your services"
- "Tell me more about your business"

human:
The customer wants to speak to a human.

Examples:
- "Can I talk to someone?"
- "Connect me to an employee"

other:
Anything that does not fit the categories above.

IMPORTANT:
If the customer says "cancel", "cancel my appointment",
"cancel my booking", or similar language about cancelling
an existing appointment, ALWAYS classify it as "cancel", NOT "lead".

Customer message:
{user_message}
"""
    )

    return {
        "intent": result.intent
    }


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



def extract_appointment_details(
    state: AgentState
):
    user_message = state["messages"][-1].content

    result = details_llm.invoke(
        f"""
You extract appointment information from a customer's message.

Extract:

- customer_name
- customer_phone
- service
- appointment_date
- appointment_time

If a value is not provided, return null.

For relative dates such as:

- tomorrow
- today
- Monday
- next Friday

convert them into a clear date.

Use the current date when interpreting relative dates.

Examples:

"I want a haircut tomorrow at 5 PM"
→ appointment_date = tomorrow's date
→ appointment_time = 17:00
→ service = haircut

"My name is Vikas and I need a haircut"
→ customer_name = Vikas
→ service = haircut

"My number is 9876543210"
→ customer_phone = 9876543210

Customer message:

{user_message}
"""
    )

    updates = {}

    if result.customer_name:
        updates["customer_name"] = result.customer_name

    if result.customer_phone:
        updates["customer_phone"] = result.customer_phone

    if result.service:
        updates["service"] = result.service

    if result.appointment_date:
        updates["appointment_date"] = result.appointment_date

    if result.appointment_time:
        updates["appointment_time"] = result.appointment_time

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

    if not appointment_time:
        return {
            "messages": [
                AIMessage(
                    content="What time would you prefer?"
                )
            ],
            "booking_in_progress": True,
        }

    is_available = check_availability(
        appointment_date,
        appointment_time,
    )

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


def confirm_booking_node(state: AgentState):

    result = book_appointment(
    session_id=state.get("session_id", ""),
    customer_name=state.get("customer_name", "Customer"),
    customer_phone=state.get("customer_phone"),
    appointment_date=state["appointment_date"],
    appointment_time=state["appointment_time"],
    service=state.get("service"),
    )

    if not result["success"]:
        return {
            "awaiting_confirmation": False,
            "booking_confirmed": False,
            "messages": [
                AIMessage(
                    content=result["message"]
                )
            ]
        }

    return {
        "awaiting_confirmation": False,
        "booking_confirmed": False,
        "messages": [
            AIMessage(
                content=(
                    f"Your appointment is confirmed "
                    f"for {state['appointment_date']} "
                    f"at {state['appointment_time']}. "
                    f"Your appointment ID is "
                    f"{result['appointment_id']}."
                )
            )
        ]
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



def extract_cancellation_details(state: AgentState):
    print("🔥 EXTRACT CANCELLATION DETAILS")

    user_message = state["messages"][-1].content

    result = cancellation_details_llm.invoke(
        f"""
Extract the customer's phone number from this message.

Customer message:
{user_message}

If no phone number is present, return null.
"""
    )

    print("🔥 EXTRACTED:", result)

    updates = {}

    if result.customer_phone:
        updates["customer_phone"] = result.customer_phone

    return updates


def cancellation_node(state: AgentState):
    customer_phone = state.get("customer_phone", "")
    appointment_date = state.get("appointment_date", "")
    appointment_time = state.get("appointment_time", "")

    print("🔥 CANCELLATION NODE")
    print("PHONE:", customer_phone)
    print("DATE:", appointment_date)
    print("TIME:", appointment_time)

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

    appointment = find_appointment(
        customer_phone=customer_phone,
        appointment_date=appointment_date or None,
        appointment_time=appointment_time or None,
    )

    if not appointment:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I couldn't find a confirmed appointment "
                        "with those details."
                    )
                )
            ],
            "cancellation_in_progress": False,
        }
    print("🔥 CANCELLATION NODE RETURNING CONFIRMATION")
    return {
        "messages": [
            AIMessage(
                content=(
                    f"I found your appointment for "
                    f"{appointment.appointment_date} at "
                    f"{appointment.appointment_time}. "
                    f"Would you like me to cancel it?"
                )
            )
        ],
        "cancellation_in_progress": False,
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


def confirm_cancellation_node(state: AgentState):
    print("🔥🔥🔥 CONFIRM CANCELLATION NODE EXECUTED")
    customer_phone = state.get("customer_phone", "")
    appointment_date = state.get("appointment_date", "")
    appointment_time = state.get("appointment_time", "")

    appointment = find_appointment(
        customer_phone=customer_phone,
        appointment_date=appointment_date or None,
        appointment_time=appointment_time or None,
    )

    if not appointment:
        return {
            "awaiting_cancellation_confirmation": False,
            "cancellation_confirmed": False,
            "messages": [
                AIMessage(
                    content="I couldn't find that appointment."
                )
            ],
        }

    result = cancel_appointment(appointment.id)

    if not result["success"]:
        return {
            "awaiting_cancellation_confirmation": False,
            "cancellation_confirmed": False,
            "messages": [
                AIMessage(content=result["message"])
            ],
        }

    return {
        "awaiting_cancellation_confirmation": False,
        "cancellation_confirmed": False,
        "messages": [
            AIMessage(
                content=(
                    f"Your appointment for "
                    f"{appointment.appointment_date} at "
                    f"{appointment.appointment_time} "
                    f"has been cancelled successfully."
                )
            )
        ],
    }