from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

    session_id: str

    intent: str

    customer_name: str
    appointment_date: str
    appointment_time: str
    awaiting_confirmation: bool
    booking_confirmed: bool


class AppointmentDetails(BaseModel):
    customer_name: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None


