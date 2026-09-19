
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from app.agent.graph import graph

from app.database.database import Base, engine
from app.database import models


# Create database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="AI Voice Agent"
)


class CallRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
def root():
    return {
        "message": "AI Voice Agent is running"
    }


@app.post("/call")
def handle_call(
    request: CallRequest
):

    # Same session_id = same conversation
    config = {
        "configurable": {
            "thread_id": request.session_id
        }
    }

    # Send only the NEW user message.
    # LangGraph loads the previous state automatically
    # using the thread_id.
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=request.message
                )
            ],
            "session_id": request.session_id,
        },
        config=config,
    )

    return {
        "intent": result.get("intent"),
        "response": result["messages"][-1].content,
    }







