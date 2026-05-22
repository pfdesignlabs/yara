from langgraph.graph import END, START, StateGraph

from app.workflows.guided_journey.nodes import decide_route, extract_facts, plan_next_step, render_reply
from app.workflows.guided_journey.state import GuidedJourneyState


def build_guided_journey_graph():
    graph = StateGraph(GuidedJourneyState)

    graph.add_node("extract_facts", extract_facts)
    graph.add_node("decide_route", decide_route)
    graph.add_node("plan_next_step", plan_next_step)
    graph.add_node("render_reply", render_reply)

    graph.add_edge(START, "extract_facts")
    graph.add_edge("extract_facts", "decide_route")
    graph.add_edge("decide_route", "plan_next_step")
    graph.add_edge("plan_next_step", "render_reply")
    graph.add_edge("render_reply", END)

    return graph.compile()


guided_journey_graph = build_guided_journey_graph()
