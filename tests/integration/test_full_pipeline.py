import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.supervisor import graph
from src.data.simulator import SensorSimulator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(text: str) -> MagicMock:
    """Build a minimal Anthropic response mock with a single text content block."""
    content = MagicMock()
    content.text = text
    resp = MagicMock()
    resp.content = [content]
    return resp


def _initial_state(readings: list) -> dict:
    """Return a fully-initialised AgentState dict ready for graph.ainvoke."""
    return {
        "messages": [],
        "sensor_readings": readings,
        "anomalies": [],
        "diagnosis": None,
        "recommended_actions": [],
        "ticket_id": None,
        "current_agent": "",
        "iteration_count": 0,
    }


# ---------------------------------------------------------------------------
# Canned Claude responses
# ---------------------------------------------------------------------------

_DIAGNOSIS_HIGH = json.dumps(
    {
        "failure_mode": "bearing_wear",
        "confidence": 0.92,
        "evidence": [
            "vibration reading 10.2 mm/s exceeds ISO zone C threshold of 7.1 mm/s",
            "temperature elevated to 78°C, trending upward from baseline 62°C",
        ],
        "similar_incidents": ["bearing wear pattern confirmed in knowledge base"],
    }
)

_DIAGNOSIS_LOW = json.dumps(
    {
        "failure_mode": "bearing_wear",
        "confidence": 0.30,
        "evidence": ["vibration slightly above baseline — insufficient data"],
        "similar_incidents": [],
    }
)

_DIAGNOSIS_HIGH_RETRY = json.dumps(
    {
        "failure_mode": "bearing_wear",
        "confidence": 0.85,
        "evidence": [
            "vibration 9.8 mm/s, well above ISO zone C",
            "temperature 76°C and rising",
        ],
        "similar_incidents": ["bearing wear pattern confirmed in knowledge base"],
    }
)

_RECOMMENDATIONS = json.dumps(
    [
        {
            "action": "Replace bearing assembly on PUMP-001",
            "urgency": "scheduled",
            "estimated_downtime_hours": 4.0,
            "cost_of_inaction_eur": 850.0,
        }
    ]
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_full_pipeline_with_bearing_wear() -> None:
    """Full pipeline: bearing_wear anomaly → diagnosis → recommendation → ticket."""
    readings = SensorSimulator("PUMP-001", seed=42).generate(100, anomaly_type="bearing_wear")
    state = _initial_state(readings)

    with (
        patch("src.agents.diagnostics_agent._client") as mock_diag,
        patch("src.agents.recommendation_agent._client") as mock_rec,
        patch("src.agents.diagnostics_agent._vector_store") as mock_vs,
    ):
        mock_diag.messages.create = AsyncMock(return_value=_mock_response(_DIAGNOSIS_HIGH))
        mock_rec.messages.create = AsyncMock(return_value=_mock_response(_RECOMMENDATIONS))
        mock_vs.search.return_value = []

        result = await graph.ainvoke(state)

    assert len(result["anomalies"]) >= 1, "Monitor should detect bearing_wear anomalies"
    assert result["diagnosis"] is not None, "Diagnostics should produce a diagnosis"
    assert result["diagnosis"].failure_mode == "bearing_wear"
    assert result["diagnosis"].confidence > 0.7
    assert len(result["recommended_actions"]) >= 1, "Recommendation agent should produce actions"
    assert result["ticket_id"] is not None, "Workflow agent should create a ticket"


async def test_pipeline_stops_on_normal_data() -> None:
    """Pipeline should halt after the monitor node when no anomalies are detected."""
    readings = SensorSimulator("PUMP-001", seed=42).generate(100)
    state = _initial_state(readings)

    with (
        patch("src.agents.diagnostics_agent._client") as mock_diag,
        patch("src.agents.recommendation_agent._client") as mock_rec,
        patch("src.agents.diagnostics_agent._vector_store") as mock_vs,
    ):
        mock_diag.messages.create = AsyncMock()
        mock_rec.messages.create = AsyncMock()
        mock_vs.search.return_value = []

        result = await graph.ainvoke(state)

    assert len(result["anomalies"]) == 0, "No anomalies expected for normal data"
    assert result["diagnosis"] is None, "No diagnosis should be created"
    assert result["ticket_id"] is None, "No ticket should be created"
    mock_diag.messages.create.assert_not_called()
    mock_rec.messages.create.assert_not_called()


async def test_pipeline_retries_low_confidence() -> None:
    """Supervisor should retry diagnosis once when first confidence is below 0.7."""
    readings = SensorSimulator("PUMP-001", seed=42).generate(100, anomaly_type="bearing_wear")
    state = _initial_state(readings)

    with (
        patch("src.agents.diagnostics_agent._client") as mock_diag,
        patch("src.agents.recommendation_agent._client") as mock_rec,
        patch("src.agents.diagnostics_agent._vector_store") as mock_vs,
    ):
        mock_diag.messages.create = AsyncMock(
            side_effect=[
                _mock_response(_DIAGNOSIS_LOW),  # first call → confidence 0.30
                _mock_response(_DIAGNOSIS_HIGH_RETRY),  # retry  → confidence 0.85
            ]
        )
        mock_rec.messages.create = AsyncMock(return_value=_mock_response(_RECOMMENDATIONS))
        mock_vs.search.return_value = []

        result = await graph.ainvoke(state)

    assert mock_diag.messages.create.call_count == 2, "Expected exactly 2 diagnosis calls"
    assert result["iteration_count"] == 2, "iteration_count should reflect both calls"
    assert result["diagnosis"] is not None
    assert result["diagnosis"].confidence == 0.85
    assert result["ticket_id"] is not None, "High-confidence retry should still produce a ticket"
