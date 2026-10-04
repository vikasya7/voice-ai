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


def test_faq_flow():

    session_id = "test_faq_001"

    result = run_message(
        session_id,
        "What are your opening hours?"
    )

    assert result["intent"] == "faq"

    response = result["messages"][-1].content.lower()

    assert "9" in response
    assert "7" in response