from types import SimpleNamespace
from uuid import uuid4

from app.agent import nodes
from app.agent.graph import graph
from langchain_core.messages import HumanMessage


def run_message(session_id: str, message: str):
    config = {
        "configurable": {
            "thread_id": session_id
        }
    }

    result = graph.invoke(
        {
            "messages": [HumanMessage(content=message)],
            "session_id": session_id,
        },
        config=config,
    )

    response = result["messages"][-1].content

    print(f"\nUSER:  {message}")
    print(f"AGENT: {response}")

    return result


def test_human_handoff(monkeypatch):
    monkeypatch.setenv("HANDOFF_NOTIFICATION_EMAIL", "staff@example.test")
    monkeypatch.setattr(
        nodes, "intent_llm",
        SimpleNamespace(invoke=lambda _: nodes.IntentResult(intent="human")),
    )
    saved = []
    sent = []

    def save(request):
        saved.append(request)
        return {"success": True, "handoff_id": 42}

    def send(**notification):
        sent.append(notification)
        return {"success": True}

    monkeypatch.setattr(nodes, "create_human_handoff", SimpleNamespace(invoke=save))
    monkeypatch.setattr(nodes, "send_email", send)

    session_id = f"test-human-{uuid4()}"
    prompt = run_message(session_id, "I want to speak to a human")
    assert prompt["awaiting_handoff_phone"]
    assert not saved and not sent

    result = run_message(session_id, "202-555-0100")
    assert not result["awaiting_handoff_phone"]
    assert "sent your callback request" in result["messages"][-1].content
    assert len(saved) == len(sent) == 1
    assert saved[0]["customer_phone"] == "2025550100"
    assert sent[0]["to_email"] == "staff@example.test"
    assert "2025550100" in sent[0]["body"]
