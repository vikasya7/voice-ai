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


def test_reschedule_flow():

    session_id = "test_reschedule_003"

    # 1. Start rescheduling
    result = run_message(
        session_id,
        "I want to reschedule my appointment"
    )

    assert result["intent"] == "reschedule"

    # 2. Provide phone number
    result = run_message(
        session_id,
        "1234567890"
    )

    assert result["customer_phone"] == "1234567890"

    # 3. Provide new date
    result = run_message(
        session_id,
        "tomorrow"
    )

    assert result["appointment_date"]

    # 4. Provide new time
    result = run_message(
        session_id,
        "11 PM"
    )

    print("\nSTATE BEFORE RESCHEDULE CONFIRMATION:")
    print(result)

    assert result["appointment_time"] == "23:00"
    assert result["awaiting_reschedule_confirmation"] is True

    # 5. Confirm reschedule
    result = run_message(
        session_id,
        "Yes"
    )

    print("\nFINAL RESCHEDULE STATE:")
    print(result)

    assert result["reschedule_confirmed"] is True
    assert result["awaiting_reschedule_confirmation"] is False