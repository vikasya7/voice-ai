from typing import TypedDict,Annotated
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from langgraph.graph.message import add_messages
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage],add_messages]
    intent: str

    customer_name: str
    appointment_date: str
    appointment_time: str


class AppointmentDetails(BaseModel):
    customer_name: str | None = None
    appointment_date:str | None=None
    appointment_time: str | None=None


