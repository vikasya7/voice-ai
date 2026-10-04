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


def test_cancellation_negative():

    session_id = "test_cancel_negative_001"

    # Start cancellation
    result = run_message(
        session_id,
        "I want to cancel my appointment"
    )

    assert result["intent"] == "cancel"

    # Provide phone number
    result = run_message(
        session_id,
        "1234567890"
    )

    assert result["awaiting_cancellation_confirmation"] is True

    # Reject cancellation
    result = run_message(
        session_id,
        "No, don't cancel it"
    )

    print("\nFINAL STATE:")
    print(result)

    assert result["cancellation_confirmed"] is False
    assert result["awaiting_cancellation_confirmation"] is False

    response = result["messages"][-1].content.lower()

    assert "won't cancel" in response