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


def test_human_handoff():

    session_id = "test_human_001"

    result = run_message(
        session_id,
        "I want to speak to a human"
    )

    print("\nFINAL HUMAN HANDOFF STATE:")
    print(result)

    assert result["intent"] == "human"

    response = result["messages"][-1].content.lower()

    assert "forwarded" in response
    assert "team" in response