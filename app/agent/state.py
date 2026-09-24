from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

    session_id: str

    intent: str

    customer_name: str
    customer_phone:str
    service:str
    appointment_date: str
    appointment_time: str
    booking_in_progress: bool
    awaiting_confirmation: bool
    booking_confirmed: bool
    cancellation_in_progress: bool
    awaiting_cancellation_confirmation: bool
    cancellation_confirmed: bool
    


class AppointmentDetails(BaseModel):
    customer_name: str | None = None
    customer_phone: str | None = None 
    service: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None


