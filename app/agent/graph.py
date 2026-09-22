import sqlite3

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agent.state import AgentState

from app.agent.nodes import (
    intent_node,
    receptionist_node,
    extract_appointment_details,
    booking_node,
    confirmation_node,
    confirm_booking_node,
    faq_node,
    lead_node,
    human_node,
    other_node,
    route_intent,
)



graph_builder = StateGraph(AgentState)


# -------------------------
# NODES
# -------------------------

graph_builder.add_node("intent", intent_node)
graph_builder.add_node("receptionist", receptionist_node)
graph_builder.add_node(
    "extract_appointment_details",
    extract_appointment_details
)



graph_builder.add_node("booking", booking_node)
graph_builder.add_node("confirmation",confirmation_node)
graph_builder.add_node("confirm_booking",confirm_booking_node)
graph_builder.add_node("faq", faq_node)

graph_builder.add_node("lead", lead_node)

graph_builder.add_node("human", human_node)

graph_builder.add_node("other", other_node)



# -------------------------
# START → INTENT
# -------------------------


# -------------------------
# START ROUTING
# -------------------------

def route_start(state: AgentState):
    """
    Decide where the customer's new message should go.

    If we are waiting for booking confirmation:
        → confirmation

    If we are still collecting booking details:
        → extract appointment details

    Otherwise:
        → normal intent classification
    """

    # Customer is answering:
    # "Shall I book the appointment?"
    if state.get("awaiting_confirmation", False):
        return "confirmation"

    # Customer is still providing:
    # name / phone / service / date / time
    if state.get("booking_in_progress", False):
        return "extract_appointment_details"

    # Completely new conversation
    return "intent"


graph_builder.add_conditional_edges(
    START,
    route_start,
    {
        "intent": "intent",
        "extract_appointment_details": "extract_appointment_details",
        "confirmation": "confirmation",
    }
)





# -------------------------
# INTENT → WORKFLOW
# -------------------------

graph_builder.add_conditional_edges(
    "intent",
    route_intent,
    {
        "booking": "extract_appointment_details",
        "faq": "faq",
        "lead": "lead",
        "human": "human",
        "other": "other",
    },
)


# -------------------------
# BOOKING WORKFLOW
# -------------------------

graph_builder.add_edge(
    "extract_appointment_details",
    "booking"
)

# booking confirmation

graph_builder.add_edge(
    "booking",
    END
)


def route_confirmation(state:AgentState):
    """ After the customer responds to the confirmation question: Yes → actually book the appointment. No → end the conversation for now. """ 
    if state.get("booking_confirmed", False): 
        return "confirm_booking" 
    return END
   

graph_builder.add_conditional_edges(
    "confirmation",
    route_confirmation,
    {
        "confirm_booking":"confirm_booking",
        END:END
    }
)

# -------------------------
# END
# -------------------------
graph_builder.add_edge(
    "confirm_booking",
    END
)

graph_builder.add_edge(
    "faq",
    END
)

graph_builder.add_edge(
    "lead",
    END
)

graph_builder.add_edge(
    "human",
    END
)

graph_builder.add_edge(
    "other",
    END
)


# SQLite checkpoint
conn = sqlite3.connect(
    "checkpoints.db",
    check_same_thread=False
)

checkpointer = SqliteSaver(conn)

graph = graph_builder.compile(
    checkpointer=checkpointer
)
