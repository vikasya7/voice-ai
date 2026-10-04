from app.agent.graph import graph
from langchain_core.messages import HumanMessage


def run_message(session_id:str,message:str):
    config={
        "configurable":{
            "thread_id":session_id
        }
    }

    result=graph.invoke(
        {
            "messages":[HumanMessage(content=message)],
            "session_id":session_id
        },
        config=config
    )

    response = result["messages"][-1].content

    print(f"\nUSER:  {message}")
    print(f"AGENT: {response}")

    return result


def test_reschedule_negative():
    session_id="test_reschedule_negative_001"

    # start rescheduling

    result=run_message(
        session_id,
        "I want to reschedule my appointment"
    )

    assert result["intent"]=="reschedule"

    # provide phone
    result=run_message(
        session_id,
        "1234567890"
    )

    # new date
    result=run_message(
        session_id,
        "tomorrow"
    )

    # new time
    result=run_message(
        session_id,
        "8:30 AM"
    )

    assert result["awaiting_reschedule_confirmation"] is True

    # reject reschedulling
    result=run_message(
        session_id,
        "No i dont want to change it"
    )

    assert result["reschedule_confirmed"] is False
    assert result["awaiting_reschedule_confirmation"] is False

    response = result["messages"][-1].content.lower()

    assert "won't change" in response
