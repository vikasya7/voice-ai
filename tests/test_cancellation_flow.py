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

    response=result["messages"][-1].content 
    print(f"\nUSER: {message}")
    print(f"AGENT: {response}")

    return result

def test_cancellation_flow():

    session_id="test_cancel_001"

    result=run_message(
        session_id,
        "i want to cancel my appointment"
    )
    assert result["intent"]=="cancel"


    # 2 provide phone number

    assert result["customer_phone"] == "1234567890"

# 3. Select one appointment from the list
    result = run_message(
    session_id,
    "I want to cancel my appointment on 2026-11-03 at 18:00"
)

# Agent should now ask for confirmation
    assert result["awaiting_cancellation_confirmation"] is True

# 4. Confirm cancellation
    result = run_message(
    session_id,
    "Yes"
)

    assert result["cancellation_confirmed"] is True