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


def test_lead_flow():

    session_id = "test_lead_001"

    # 1. Start lead conversation
    result = run_message(
        session_id,
        "I'm interested in hair spa"
    )

    assert result["intent"] == "lead"

    # 2. Provide name
    result = run_message(
        session_id,
        "My name is Vikas"
    )

    assert result["customer_name"] == "Vikas"

    # 3. Provide phone
    result = run_message(
        session_id,
        "My phone number is 9876543210"
    )

    assert result["customer_phone"] == "9876543210"

    # 4. Provide preferred time
    result = run_message(
        session_id,
        "Saturday evening"
    )

    print("\nFINAL LEAD STATE:")
    print(result)

    assert result["preferred_time"] == "Saturday evening"
    assert result["lead_saved"] is True
    assert result["lead_in_progress"] is False

    # 5. Verify response
    response = result["messages"][-1].content

    assert "Vikas" in response
    assert "hair spa" in response.lower()
    assert "9876543210" in response