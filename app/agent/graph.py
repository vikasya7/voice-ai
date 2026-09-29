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
    extract_reschedule_details,
    reschedule_node,
    reschedule_confirmation_node,
    confirm_reschedule_node,
    extract_lead_details
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
graph_builder.add_node("extract_reschedule_details",extract_reschedule_details)
graph_builder.add_node("reschedule",reschedule_node)
graph_builder.add_node(
    "reschedule_confirmation",
    reschedule_confirmation_node
)
graph_builder.add_node(
    "confirm_reschedule",
    confirm_reschedule_node
)


graph_builder.add_node(
    "extract_lead_details",
    extract_lead_details
)
# -------------------------
# START → INTENT
# -------------------------


# -------------------------
# START ROUTING
# -------------------------

def route_start(state: AgentState):

    if state.get("awaiting_confirmation", False):
        return "confirmation"

    if state.get("awaiting_cancellation_confirmation", False):
        return "cancellation_confirmation"

    if state.get("awaiting_reschedule_confirmation", False):
        return "reschedule_confirmation"

    if state.get("booking_in_progress", False):
        return "extract_appointment_details"

    if state.get("cancellation_in_progress", False):
        return "extract_cancellation_details"

    if state.get("reschedule_in_progress", False):
        return "extract_reschedule_details"

    if state.get("lead_in_progress", False):
        return "extract_lead_details"

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
        "extract_reschedule_details": "extract_reschedule_details",
        "reschedule_confirmation": "reschedule_confirmation",
        "extract_lead_details": "extract_lead_details",
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
        "reschedule": "extract_reschedule_details",
        "faq": "faq",
        "lead": "extract_lead_details",
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

graph_builder.add_edge(
    "extract_reschedule_details",
    "reschedule"
)

graph_builder.add_edge(
    "reschedule",
    END
)
graph_builder.add_edge(
    "extract_lead_details",
    "lead"
)

def route_reschedule_confirmation(state: AgentState):
    print("🔥 ROUTE RESCHEDULE CONFIRMATION")
    print(
        "reschedule_confirmed:",
        state.get("reschedule_confirmed", False)
    )

    if state.get("reschedule_confirmed", False):
        return "confirm_reschedule"

    return END


graph_builder.add_conditional_edges(
    "reschedule_confirmation",
    route_reschedule_confirmation,
    {
        "confirm_reschedule": "confirm_reschedule",
        END: END,
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
graph_builder.add_edge(
    "confirm_reschedule",
    END
)
graph_builder.add_edge(
    "extract_lead_details",
    "lead"
)

graph_builder.add_edge(
    "lead",
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
#print(graph.get_graph().draw_mermaid())
print("=====================================\n")

#png = graph.get_graph().draw_mermaid_png()

#with open("graph.png", "wb") as f:
   # f.write(png)