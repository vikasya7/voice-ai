
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from app.agent.graph import graph


app = FastAPI(title="AI Voice Agent")


class CallRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
def root():
    return {
        "message": "AI Voice Agent is running"
    }


@app.post("/call")
def handle_call(request: CallRequest):

    config = {
        "configurable": {
            "thread_id": request.session_id
        }
    }

    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content=request.message)
            ]
        },
        config=config,
    )

    return {
        "intent": result["intent"],
        "response": result["messages"][-1].content,
    }



