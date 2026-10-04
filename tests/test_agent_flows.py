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


def test_booking_flow():
    session_id = "test_booking_005"

    # 1. Start booking
    result = run_message(
        session_id,
        "I want to book an appointment tomorrow at 5 am"
    )

    assert result["intent"] == "booking"

    # 2. Provide name
    result = run_message(
        session_id,
        "My name is Vikas Yadav"
    )

    assert result["customer_name"] == "Vikas Yadav"

    # 3. Provide phone
    result = run_message(
        session_id,
        "1234567890"
    )

    assert result["customer_phone"] == "1234567890"

    # 4. Provide service
    result = run_message(
        session_id,
        "Hair Spa"
    )

    assert result["service"].lower() == "hair spa"

    print("\nFINAL STATE AFTER SERVICE:")
    print(result)

    # 5. Agent should ask for confirmation
    assert result["awaiting_confirmation"] is True

    # 6. Confirm
    result = run_message(
        session_id,
        "Yes"
    )
    print("\nFINAL STATE AFTER CONFIRMATION:")
    print(result)

    assert result["booking_confirmed"] is True

    print("\n✅ BOOKING FLOW PASSED")