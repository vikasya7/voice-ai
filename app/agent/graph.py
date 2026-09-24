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
    extract_cancellation_details,
    cancellation_node,
    cancellation_confirmation_node,
    confirm_cancellation_node,
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
graph_builder.add_node("extract_cancellation_details",extract_cancellation_details)
graph_builder.add_node("cancellation",cancellation_node)
graph_builder.add_node("cancellation_confirmation",cancellation_confirmation_node)
graph_builder.add_node("confirm_cancellation",confirm_cancellation_node)


# -------------------------
# START → INTENT
# -------------------------


# -------------------------
# START ROUTING
# -------------------------

def route_start(state: AgentState):

    print("\n========== ROUTE START ==========")

    print(
        "awaiting_confirmation:",
        state.get("awaiting_confirmation", False)
    )

    print(
        "awaiting_cancellation_confirmation:",
        state.get("awaiting_cancellation_confirmation", False)
    )

    print(
        "booking_in_progress:",
        state.get("booking_in_progress", False)
    )

    print(
        "cancellation_in_progress:",
        state.get("cancellation_in_progress", False)
    )

    print("intent:", state.get("intent"))

    if state.get("awaiting_confirmation", False):
        print("🚦 ROUTING TO: confirmation")
        return "confirmation"

    if state.get("awaiting_cancellation_confirmation", False):
        print("🚦 ROUTING TO: cancellation_confirmation")
        return "cancellation_confirmation"

    if state.get("booking_in_progress", False):
        print("🚦 ROUTING TO: extract_appointment_details")
        return "extract_appointment_details"

    if state.get("cancellation_in_progress", False):
        print("🚦 ROUTING TO: extract_cancellation_details")
        return "extract_cancellation_details"

    print("🚦 ROUTING TO: intent")
    return "intent"


graph_builder.add_conditional_edges(
    START,
    route_start,
    {
        "intent": "intent",
        "extract_appointment_details": "extract_appointment_details",
        "confirmation": "confirmation",
        "extract_cancellation_details": "extract_cancellation_details",
        "cancellation_confirmation": "cancellation_confirmation",
    },
)




# -------------------------
# INTENT → WORKFLOW
# -------------------------

graph_builder.add_conditional_edges(
    "intent",
    route_intent,
    {
        "booking": "extract_appointment_details",
        "cancel": "extract_cancellation_details",
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


def route_cancellation_confirmation(state: AgentState):

    print("🔥🔥 ROUTE CANCELLATION CONFIRMATION")
    print(
        "cancellation_confirmed:",
        state.get("cancellation_confirmed", False)
    )

    if state.get("cancellation_confirmed", False):
        return "confirm_cancellation"

    return END



graph_builder.add_conditional_edges(
    "cancellation_confirmation",
    route_cancellation_confirmation,
    {
        "confirm_cancellation": "confirm_cancellation",
        END: END,
    },
)
graph_builder.add_edge(
    "extract_cancellation_details",
    "cancellation"
)

graph_builder.add_edge(
    "cancellation",
    END
)

graph_builder.add_edge(
    "confirm_cancellation",
    END
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
print("\n========== EDGES ==========")

for edge in graph.get_graph().edges:
    print(edge)

print("===========================\n")
print("\n========== GRAPH STRUCTURE ==========")
print(graph.get_graph().draw_ascii())
print("=====================================\n")