
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage

from app.agent.state import AgentState, AppointmentDetails
from app.agent.tools import (
    check_availability,
    book_appointment,
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
        "faq",
        "lead",
        "human",
        "other",
    ]


intent_llm = llm.with_structured_output(IntentResult)


def intent_node(state: AgentState):

    user_message = state["messages"][-1].content

    result = intent_llm.invoke(
        f"""
You are an intent classifier for a small business AI receptionist.

Classify the customer's CURRENT message into exactly one category.

booking:
Customer wants to book, schedule, reschedule, cancel,
or check availability for an appointment.

faq:
Customer wants general information such as business hours,
location, services, or prices.

lead:
Customer is interested in purchasing a service,
getting a quote, or discussing a potential service.

human:
Customer wants to speak with a human.

other:
Anything else.

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

Customer message:
{user_message}
"""
    )

    updates = {}

    if result.customer_name:
        updates["customer_name"] = result.customer_name

    if result.appointment_date:
        updates["appointment_date"] = result.appointment_date

    if result.appointment_time:
        updates["appointment_time"] = result.appointment_time

    return updates


# =========================================================
# BOOKING NODE
# =========================================================

def booking_node(state: AgentState):

    appointment_date = state.get(
        "appointment_date",
        ""
    )

    appointment_time = state.get(
        "appointment_time",
        ""
    )

    # -----------------------------------------------------
    # Missing date
    # -----------------------------------------------------

    if not appointment_date:

        return {
            "messages": [
                AIMessage(
                    content=(
                        "Sure. What date would you "
                        "like the appointment?"
                    )
                )
            ]
        }


    # -----------------------------------------------------
    # Missing time
    # -----------------------------------------------------

    if not appointment_time:

        return {
            "messages": [
                AIMessage(
                    content="What time would you prefer?"
                )
            ]
        }


    # -----------------------------------------------------
    # Check availability
    # -----------------------------------------------------

    is_available = check_availability(
        appointment_date,
        appointment_time,
    )


    # -----------------------------------------------------
    # Slot unavailable
    # -----------------------------------------------------

    if not is_available:

        return {
            "messages": [
                AIMessage(
                    content=(
                        f"Sorry, {appointment_time} is "
                        f"already booked on "
                        f"{appointment_date}. "
                        f"Would you like another time?"
                    )
                )
            ]
        }


    # -----------------------------------------------------
    # Slot available
    # -----------------------------------------------------

    return {
        "messages": [
            AIMessage(
                content=(
                    f"{appointment_time} is available "
                    f"on {appointment_date}. "
                    f"Would you like me to book it?"
                )
            )
        ],
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
        customer_name=state.get(
            "customer_name",
            "Customer"
        ),
        appointment_date=state["appointment_date"],
        appointment_time=state["appointment_time"],
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



