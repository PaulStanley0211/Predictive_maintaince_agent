import logging
from datetime import UTC, datetime
from uuid import uuid4

from src.agents.state import AgentState, MaintenanceAction

logger = logging.getLogger(__name__)


def format_ticket_summary(ticket: dict) -> str:
    """Return a human-readable summary string for a maintenance ticket."""
    actions = ticket.get("actions", [])
    action_lines = "\n".join(
        f"  [{i + 1}] {a['action']} | urgency={a['urgency']} | "
        f"downtime={a['estimated_downtime_hours']}h | "
        f"cost of inaction=€{a['cost_of_inaction_eur']}/day"
        for i, a in enumerate(actions)
    )
    return (
        f"╔══ MAINTENANCE TICKET {ticket['ticket_id']} ══\n"
        f"║  Equipment : {ticket['equipment_id']}\n"
        f"║  Failure   : {ticket['failure_mode']} (confidence {ticket['confidence']:.0%})\n"
        f"║  Urgency   : {ticket['urgency']}\n"
        f"║  Status    : {ticket['status']}\n"
        f"║  Created   : {ticket['created_at']}\n"
        f"║  Actions   :\n{action_lines}\n"
        f"╚{'═' * 50}"
    )


def _determine_urgency(actions: list[MaintenanceAction]) -> str:
    """Return the highest urgency across all recommended actions."""
    priority = {"immediate": 2, "scheduled": 1, "monitoring": 0}
    return max(actions, key=lambda a: priority.get(a.urgency, 0)).urgency


def _serialise_action(action: MaintenanceAction) -> dict:
    """Convert a MaintenanceAction to a plain dict for ticket storage."""
    return {
        "action": action.action,
        "urgency": action.urgency,
        "estimated_downtime_hours": action.estimated_downtime_hours,
        "cost_of_inaction_eur": action.cost_of_inaction_eur,
    }


async def workflow_node(state: AgentState) -> dict:
    """LangGraph node: create a maintenance ticket from the diagnosis and recommended actions."""
    diagnosis = state.get("diagnosis")
    actions: list[MaintenanceAction] = state.get("recommended_actions") or []
    sensor_readings = state.get("sensor_readings") or []

    equipment_id = sensor_readings[-1].equipment_id if sensor_readings else "UNKNOWN"
    ticket_id = f"TKT-{uuid4().hex[:8].upper()}"

    ticket = {
        "ticket_id": ticket_id,
        "equipment_id": equipment_id,
        "failure_mode": diagnosis.failure_mode if diagnosis else "unknown",
        "confidence": diagnosis.confidence if diagnosis else 0.0,
        "urgency": _determine_urgency(actions) if actions else "monitoring",
        "actions": [_serialise_action(a) for a in actions],
        "status": "open",
        "created_at": datetime.now(UTC).isoformat(),
    }

    summary = format_ticket_summary(ticket)
    logger.info("Maintenance ticket created:\n%s", summary)

    return {
        "ticket_id": ticket_id,
        "current_agent": "workflow",
    }
