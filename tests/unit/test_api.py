import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.agents.supervisor import build_graph
from src.api.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """AsyncClient wired to the FastAPI app with graph state pre-seeded."""
    app.state.graph = build_graph()
    app.state.vector_store = MagicMock()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_claude_clients():
    """Patch the Anthropic client in both diagnostics and recommendation agents."""
    diag_text = json.dumps(
        {
            "failure_mode": "bearing_wear",
            "confidence": 0.85,
            "evidence": ["vibration reading elevated above ISO 10816 zone C threshold"],
            "similar_incidents": ["bearing_wear pattern"],
        }
    )
    rec_text = json.dumps(
        [
            {
                "action": "Replace bearing assembly on PUMP-001",
                "urgency": "scheduled",
                "estimated_downtime_hours": 4.0,
                "cost_of_inaction_eur": 850.0,
            }
        ]
    )

    diag_resp = MagicMock()
    diag_resp.content = [MagicMock(text=diag_text)]
    rec_resp = MagicMock()
    rec_resp.content = [MagicMock(text=rec_text)]

    with (
        patch("src.agents.diagnostics_agent._client") as dc,
        patch("src.agents.recommendation_agent._client") as rc,
    ):
        dc.messages.create = AsyncMock(return_value=diag_resp)
        rc.messages.create = AsyncMock(return_value=rec_resp)
        yield dc, rc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_health_endpoint(client: AsyncClient) -> None:
    """GET /health returns 200 with correct status, agents_count, and mcp_servers_count."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["agents_count"] == 4
    assert data["mcp_servers_count"] == 3


async def test_simulate_normal(client: AsyncClient) -> None:
    """Normal sensor data (no anomaly_type) produces no anomalies and no ticket."""
    response = await client.post(
        "/simulate/PUMP-001",
        json={"equipment_id": "PUMP-001", "reading_count": 100},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["anomalies"] == []
    assert data["ticket_id"] is None


async def test_simulate_bearing_wear(
    client: AsyncClient,
    mock_claude_clients: tuple,
) -> None:
    """Bearing wear anomaly injection causes at least one anomaly to be detected."""
    response = await client.post(
        "/simulate/PUMP-001",
        json={
            "equipment_id": "PUMP-001",
            "anomaly_type": "bearing_wear",
            "reading_count": 100,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["anomalies"]) >= 1


async def test_failure_modes_endpoint(client: AsyncClient) -> None:
    """GET /failure-modes returns the 5 known failure mode definitions."""
    response = await client.get("/failure-modes")

    assert response.status_code == 200
    modes = response.json()
    assert len(modes) == 5
    mode_names = {m["name"] for m in modes}
    assert mode_names == {"bearing_wear", "cavitation", "misalignment", "seal_leakage", "imbalance"}


async def test_invalid_equipment(client: AsyncClient) -> None:
    """Empty equipment_id in request body is rejected with 422 Unprocessable Entity."""
    response = await client.post(
        "/simulate/PUMP-001",
        json={"equipment_id": ""},
    )

    assert response.status_code == 422
