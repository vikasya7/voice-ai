from fastapi import FastAPI
from pydantic import BaseModel
from app.agent.graph import graph
from langchain_core.messages import HumanMessage


app=FastAPI(title="AI voice agent")

class CallRequest(BaseModel):
    message:str


@app.get("/")
def root():
    return {
        "message": "AI Voice Agent is running"
    }

@app.post("/call")
def handle_call(request:CallRequest):
    result=graph.invoke({
        "messages":[
            HumanMessage(content=request.message)
        ],
        "intent":""
    })

    return {
        "intent":result["intent"]
    }