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


def test_invalid_phone_booking():

    session_id = "test_invalid_phone_001"

    # Start booking
    result = run_message(
        session_id,
        "I want to book an appointment"
    )

    assert result["intent"] == "booking"

    # Name
    result = run_message(
        session_id,
        "My name is Test User"
    )

    # Invalid phone number
    result = run_message(
        session_id,
        "12345"
    )

    print("\nSTATE AFTER INVALID PHONE:")
    print(result)

    response = result["messages"][-1].content.lower()

    assert "10-digit" in response
    assert result["booking_in_progress"] is True

    # Valid phone number
    result = run_message(
        session_id,
        "9876543212"
    )

    print("\nSTATE AFTER VALID PHONE:")
    print(result)

    assert result["customer_phone"] == "9876543212"