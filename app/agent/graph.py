from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.nodes import (
    intent_node,
    receptionist_node,
    booking_node,
    faq_node,
    lead_node,
    human_node,
    other_node,
    route_intent
)


graph_builder = StateGraph(AgentState)


graph_builder.add_node("intent", intent_node)
graph_builder.add_node("receptionist", receptionist_node)

graph_builder.add_node("booking", booking_node)
graph_builder.add_node("faq", faq_node)
graph_builder.add_node("lead", lead_node)
graph_builder.add_node("human", human_node)
graph_builder.add_node("other", other_node)


graph_builder.add_edge(
    START,
    "intent"
)

graph_builder.add_conditional_edges(
    "intent",
    route_intent,
    {
        "booking": "booking",
        "faq": "faq",
        "lead": "lead",
        "human": "human",
        "other": "other",
    }
)

graph_builder.add_edge("booking", END)
graph_builder.add_edge("faq", END)
graph_builder.add_edge("lead", END)
graph_builder.add_edge("human", END)
graph_builder.add_edge("other", END)

graph = graph_builder.compile()



