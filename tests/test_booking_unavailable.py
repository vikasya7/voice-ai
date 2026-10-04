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


def test_booking_unavailable():

    session_id = "test_booking_unavailable_001"

    result = run_message(
        session_id,
        "I want to book an appointment"
    )

    assert result["intent"] == "booking"

    result = run_message(
        session_id,
        "My name is Test User"
    )

    result = run_message(
        session_id,
        "9876543211"
    )

    result = run_message(
        session_id,
        "Hair Spa"
    )

    result = run_message(
        session_id,
        "October 5"
    )

    result = run_message(
        session_id,
        "8 PM"
    )
    print("\nFINAL STATE:")
    print(result)

    response = result["messages"][-1].content.lower()

    assert "already booked" in response
    assert result.get("awaiting_confirmation", False) is False
    assert result["booking_in_progress"] is True