from langchain_openai import ChatOpenAI
from app.agent.state import AgentState
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel
from langchain_core.messages import AIMessage
load_dotenv()

llm=ChatOpenAI(
    model="gpt-5-mini",
    temperature=0
)

class IntentResult(BaseModel):
    intent:Literal[
        "booking",
        "faq",
        "lead",
        "human",
        "other"
    ]

intent_llm=llm.with_structured_output(IntentResult)

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



def receptionist_node(state:AgentState):
    response=llm.invoke(state["messages"])
    return {
        "messages":[response]
    }


def booking_node(state: AgentState):

    return {
        "messages": [
            AIMessage(content="Okay, let's book your appointment.")
        ]
    }

def faq_node(state: AgentState):

    return {
        "messages": [
            AIMessage(content="Sure, I can help answer your question.")
        ]
    }


def lead_node(state: AgentState):

    return {
        "messages": [
            AIMessage(
                content="Sure, I'd be happy to get some details from you."
            )
        ]
    }


def human_node(state: AgentState):

    return {
        "messages": [
            AIMessage(
                content="Sure, I'll connect you with a human representative."
            )
        ]
    }


def other_node(state: AgentState):

    return {
        "messages": [
            AIMessage(
                content="I'm sorry, I didn't quite understand that."
            )
        ]
    }


def route_intent(state:AgentState):
    return state["intent"]