import json
from datetime import datetime
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

_VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}

# In-memory store — keyed by ticket_id. Replaced by PostgreSQL in production.
_tickets: dict[str, dict] = {}

mcp = FastMCP("task-manager")


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.utcnow().isoformat()


@mcp.tool()
def create_ticket(
    equipment_id: str,
    diagnosis_summary: str,
    actions: list[str],
    urgency: str,
) -> str:
    """Create a new maintenance ticket and store it in memory.

    Args:
        equipment_id: The equipment identifier (e.g. PUMP-001).
        diagnosis_summary: Short description of the diagnosed failure mode.
        actions: List of recommended maintenance action strings.
        urgency: Ticket urgency level ('immediate', 'scheduled', or 'monitoring').
    """
    ticket_id = f"TKT-{uuid4().hex[:8].upper()}"
    now = _now()
    ticket = {
        "ticket_id": ticket_id,
        "equipment_id": equipment_id,
        "diagnosis_summary": diagnosis_summary,
        "actions": actions,
        "urgency": urgency,
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }
    _tickets[ticket_id] = ticket
    return json.dumps({"ticket_id": ticket_id, "status": "open", "created_at": now})


@mcp.tool()
def get_ticket(ticket_id: str) -> str:
    """Retrieve full details of a ticket by its ID.

    Args:
        ticket_id: The ticket identifier returned by create_ticket.
    """
    ticket = _tickets.get(ticket_id)
    if ticket is None:
        return json.dumps({"error": f"Ticket '{ticket_id}' not found."})
    return json.dumps(ticket)


@mcp.tool()
def update_ticket_status(ticket_id: str, new_status: str) -> str:
    """Update the status of an existing ticket.

    Args:
        ticket_id: The ticket identifier to update.
        new_status: One of 'open', 'in_progress', 'resolved', 'closed'.
    """
    if new_status not in _VALID_STATUSES:
        return json.dumps(
            {
                "error": f"Invalid status '{new_status}'.",
                "valid_statuses": sorted(_VALID_STATUSES),
            }
        )

    ticket = _tickets.get(ticket_id)
    if ticket is None:
        return json.dumps({"error": f"Ticket '{ticket_id}' not found."})

    ticket["status"] = new_status
    ticket["updated_at"] = _now()
    return json.dumps(ticket)


@mcp.tool()
def list_tickets(status: str | None = None) -> str:
    """List all tickets, optionally filtered by status.

    Args:
        status: Optional filter — one of 'open', 'in_progress', 'resolved', 'closed'.
                Omit to return all tickets.
    """
    if status is not None and status not in _VALID_STATUSES:
        return json.dumps(
            {
                "error": f"Invalid status filter '{status}'.",
                "valid_statuses": sorted(_VALID_STATUSES),
            }
        )

    tickets = list(_tickets.values())
    if status is not None:
        tickets = [t for t in tickets if t["status"] == status]

    return json.dumps({"tickets": tickets, "count": len(tickets)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
