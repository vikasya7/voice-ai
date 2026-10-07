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


def test_reschedule_unavailable():

    session_id = "test_reschedule_unavailable_001"

    # 1. Start rescheduling
    result = run_message(
        session_id,
        "I want to reschedule my appointment"
    )

    assert result["intent"] == "reschedule"

    # 2. Phone
    result = run_message(
        session_id,
        "1234567890"
    )

    assert result["customer_phone"] == "1234567890"

    # 3. New date
    result = run_message(
        session_id,
        "October 5"
    )

    assert result["appointment_date"] == "2026-10-05"

    # 4. Use a slot that is already occupied
    result = run_message(
        session_id,
        "8 PM"
    )

    print("\nFINAL STATE:")
    print(result)

    response = result["messages"][-1].content.lower()

    # Slot should be rejected
    assert "already booked" in response

    # We should still be in the rescheduling flow
    assert result["reschedule_in_progress"] is True

    # We must NOT ask for confirmation
    assert result.get(
        "awaiting_reschedule_confirmation",
        False
    ) is False