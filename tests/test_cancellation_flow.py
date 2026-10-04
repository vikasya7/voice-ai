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

    result=run_message(
        session_id,
        "1234567890"
    )

    assert result["customer_phone"]=="1234567890"

    # agent should ask for confirmation

    assert result["awaiting_cancellation_confirmation"] is True

    result=run_message(
        session_id,
        "Yes"
    )
     # 4. Cancellation should succeed
    assert result["cancellation_confirmed"] is True


