from langgraph.graph import END, StateGraph

from src.agents.diagnostics_agent import diagnose_node
from src.agents.monitor_agent import monitor_node
from src.agents.recommendation_agent import recommend_node
from src.agents.state import AgentState
from src.agents.workflow_agent import workflow_node


def route_after_monitor(state: AgentState) -> str:
    """Route to diagnostics if anomalies were detected, otherwise stop."""
    if state.get("anomalies"):
        return "diagnose"
    return END


def route_after_diagnosis(state: AgentState) -> str:
    """Route to recommendations if confident; retry diagnosis if not and budget allows."""
    diagnosis = state.get("diagnosis")
    confidence = diagnosis.confidence if diagnosis else 0.0
    iteration_count = state.get("iteration_count", 0)

    if confidence > 0.7:
        return "recommend"
    if iteration_count < 2:
        return "retry_diagnosis"
    return "recommend"


def route_after_recommendation(state: AgentState) -> str:
    """Route to ticket creation if any action requires intervention, otherwise stop."""
    actions = state.get("recommended_actions") or []
    if any(a.urgency in {"immediate", "scheduled"} for a in actions):
        return "create_ticket"
    return END


def build_graph() -> StateGraph:
    """Build and compile the LangGraph supervisor graph for the maintenance pipeline."""
    graph = StateGraph(AgentState)

    graph.add_node("monitor", monitor_node)
    graph.add_node("diagnose", diagnose_node)
    graph.add_node("recommend", recommend_node)
    graph.add_node("workflow", workflow_node)

    graph.set_entry_point("monitor")

    graph.add_conditional_edges("monitor", route_after_monitor, {"diagnose": "diagnose", END: END})
    graph.add_conditional_edges(
        "diagnose",
        route_after_diagnosis,
        {"recommend": "recommend", "retry_diagnosis": "diagnose"},
    )
    graph.add_conditional_edges(
        "recommend",
        route_after_recommendation,
        {"create_ticket": "workflow", END: END},
    )

    graph.add_edge("workflow", END)

    return graph.compile()


graph = build_graph()
