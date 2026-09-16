
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from app.agent.tools import check_availability
from app.agent.state import AgentState, AppointmentDetails


load_dotenv()


llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0
)


# -------------------------
# INTENT CLASSIFICATION
# -------------------------

class IntentResult(BaseModel):
    intent: Literal[
        "booking",
        "faq",
        "lead",
        "human",
        "other"
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


# -------------------------
# RECEPTIONIST
# -------------------------

def receptionist_node(state: AgentState):

    response = llm.invoke(state["messages"])

    return {
        "messages": [response]
    }


# -------------------------
# APPOINTMENT EXTRACTION
# -------------------------

details_llm = llm.with_structured_output(AppointmentDetails)


def extract_appointment_details(state: AgentState):

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

Today's date should be considered the current date.

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


# -------------------------
# BOOKING
# -------------------------

def booking_node(state: AgentState):

    appointment_date = state.get("appointment_date", "")
    appointment_time = state.get("appointment_time", "")

    if not appointment_date:
        return {
            "messages": [
                AIMessage(
                    content="Sure. What date would you like the appointment?"
                )
            ]
        }

    if not appointment_time:
        return {
            "messages": [
                AIMessage(
                    content="What time would you prefer?"
                )
            ]
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Great. You want an appointment on "
                    f"{appointment_date} at {appointment_time}. "
                    f"Let me check availability for you."
                )
            )
        ]
    }

# -------------------------
# FAQ
# -------------------------

def faq_node(state: AgentState):

    return {
        "messages": [
            AIMessage(
                content="Sure, I can help answer your question."
            )
        ]
    }


# -------------------------
# LEAD
# -------------------------

def lead_node(state: AgentState):

    return {
        "messages": [
            AIMessage(
                content="Sure, I'd be happy to get some details from you."
            )
        ]
    }


# -------------------------
# HUMAN
# -------------------------

def human_node(state: AgentState):

    return {
        "messages": [
            AIMessage(
                content="Sure, I'll connect you with a human representative."
            )
        ]
    }


# -------------------------
# OTHER
# -------------------------

def other_node(state: AgentState):

    return {
        "messages": [
            AIMessage(
                content="I'm sorry, I didn't quite understand that."
            )
        ]
    }


# -------------------------
# ROUTER
# -------------------------

def route_intent(state: AgentState):

    return state["intent"]

