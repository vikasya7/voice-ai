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

def route_start(state: AgentState): 
    """ Decide where a new user message should go. If we previously asked for booking confirmation, the new message should go directly to confirmation. Otherwise, start normal intent classification. """ 
    if state.get("awaiting_confirmation", False): 
        return "confirmation" 
    return "intent"

graph_builder.add_conditional_edges(
    START,
    route_start,
    {
        "intent":"intent",
        "confirmation":"confirmation"
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
