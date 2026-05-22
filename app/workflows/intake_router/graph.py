from langgraph.graph import END, START, StateGraph

from app.workflows.intake_router.nodes import decide_entry_path, detect_message_kind, reason_about_intake
from app.workflows.intake_router.state import IntakeRouterState


def build_intake_router_graph():
    graph = StateGraph(IntakeRouterState)

    graph.add_node("detect_message_kind", detect_message_kind)
    graph.add_node("decide_entry_path", decide_entry_path)
    graph.add_node("reason_about_intake", reason_about_intake)

    graph.add_edge(START, "detect_message_kind")
    graph.add_edge("detect_message_kind", "decide_entry_path")
    graph.add_edge("decide_entry_path", "reason_about_intake")
    graph.add_edge("reason_about_intake", END)

    return graph.compile()


intake_router_graph = build_intake_router_graph()
