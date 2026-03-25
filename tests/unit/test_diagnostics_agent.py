import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.diagnostics_agent import (
    _build_user_message,
    _call_claude,
    _fallback_diagnosis,
    diagnose_node,
)
from src.agents.state import AnomalyAlert, Diagnosis, SensorReading
from src.data.simulator import SensorSimulator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_anomaly(sensor_type: str = "vibration", severity: str = "high") -> AnomalyAlert:
    """Return a minimal AnomalyAlert for use in tests."""
    return AnomalyAlert(
        equipment_id="PUMP-001",
        sensor_type=sensor_type,
        severity=severity,  # type: ignore[arg-type]
        z_score=3.5,
        description=f"{sensor_type} anomaly detected at 3.5 z-score",
    )


def _make_state(anomalies: list[AnomalyAlert] | None = None) -> dict:
    """Return a minimal AgentState dict for diagnose_node."""
    sim = SensorSimulator("PUMP-001", seed=42)
    readings: list[SensorReading] = sim.generate(5)
    return {
        "messages": [],
        "sensor_readings": readings,
        "anomalies": anomalies if anomalies is not None else [],
        "diagnosis": None,
        "recommended_actions": [],
        "ticket_id": None,
        "current_agent": "monitor",
        "iteration_count": 0,
    }


_VALID_DIAGNOSIS_JSON = json.dumps(
    {
        "failure_mode": "bearing_wear",
        "confidence": 0.85,
        "evidence": ["vibration z-score 3.5 above threshold"],
        "similar_incidents": ["bearing_wear_case_1"],
    }
)


# ---------------------------------------------------------------------------
# _build_user_message
# ---------------------------------------------------------------------------

def test_build_user_message_contains_anomaly_descriptions() -> None:
    """User message should include each anomaly description."""
    descriptions = ["vibration spike detected", "temperature elevated"]
    rag_results: list[str] = []
    message = _build_user_message(descriptions, rag_results)
    assert "vibration spike detected" in message
    assert "temperature elevated" in message


def test_build_user_message_no_rag_results() -> None:
    """When RAG returns nothing the message should say so explicitly."""
    message = _build_user_message(["vibration spike"], [])
    assert "No similar incidents found" in message


def test_build_user_message_includes_rag_entries() -> None:
    """RAG results should appear in the assembled message."""
    rag = ["Bearing wear causes gradual vibration rise.", "Check lubrication levels."]
    message = _build_user_message(["vibration spike"], rag)
    assert "Bearing wear causes gradual vibration rise." in message


# ---------------------------------------------------------------------------
# _fallback_diagnosis
# ---------------------------------------------------------------------------

def test_fallback_diagnosis_has_zero_confidence() -> None:
    """Fallback diagnosis must always have confidence 0.0."""
    diag = _fallback_diagnosis("API timeout")
    assert diag.confidence == 0.0


def test_fallback_diagnosis_failure_mode_is_unknown() -> None:
    """Fallback failure mode must be 'unknown'."""
    diag = _fallback_diagnosis("some reason")
    assert diag.failure_mode == "unknown"


def test_fallback_diagnosis_includes_reason_in_evidence() -> None:
    """The reason passed to fallback should appear in evidence."""
    diag = _fallback_diagnosis("connection refused")
    assert any("connection refused" in e for e in diag.evidence)


# ---------------------------------------------------------------------------
# _call_claude — mocked
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_claude_parses_valid_response() -> None:
    """_call_claude should return a Diagnosis when Claude returns valid JSON."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_VALID_DIAGNOSIS_JSON)]

    with patch("src.agents.diagnostics_agent._client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        result = await _call_claude("test message")

    assert isinstance(result, Diagnosis)
    assert result.failure_mode == "bearing_wear"
    assert result.confidence == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_call_claude_returns_fallback_on_invalid_json() -> None:
    """_call_claude should return a fallback Diagnosis when Claude returns invalid JSON."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json {{{")]

    with patch("src.agents.diagnostics_agent._client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        result = await _call_claude("test message")

    assert isinstance(result, Diagnosis)
    assert result.failure_mode == "unknown"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_call_claude_retries_on_api_error() -> None:
    """_call_claude should retry up to _MAX_RETRIES times on APIError then return fallback."""
    import anthropic

    api_error = anthropic.APIStatusError(
        "server error", response=MagicMock(status_code=500, headers={}), body={}
    )

    with patch("src.agents.diagnostics_agent._client") as mock_client:
        with patch("src.agents.diagnostics_agent.asyncio.sleep", new_callable=AsyncMock):
            mock_client.messages.create = AsyncMock(side_effect=api_error)
            result = await _call_claude("test message")

    assert result.failure_mode == "unknown"
    assert mock_client.messages.create.call_count == 3  # _MAX_RETRIES


# ---------------------------------------------------------------------------
# diagnose_node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diagnose_node_increments_iteration_count() -> None:
    """diagnose_node should increment iteration_count by 1."""
    state = _make_state(anomalies=[_make_anomaly()])
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_VALID_DIAGNOSIS_JSON)]

    with patch("src.agents.diagnostics_agent._client") as mock_client:
        with patch("src.agents.diagnostics_agent._vector_store") as mock_store:
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_store.search.return_value = []
            result = await diagnose_node(state)

    assert result["iteration_count"] == 1


@pytest.mark.asyncio
async def test_diagnose_node_returns_fallback_when_no_anomalies() -> None:
    """diagnose_node should return a zero-confidence fallback when anomalies list is empty."""
    state = _make_state(anomalies=[])

    result = await diagnose_node(state)

    assert result["diagnosis"].failure_mode == "unknown"
    assert result["diagnosis"].confidence == 0.0
    assert result["iteration_count"] == 1


@pytest.mark.asyncio
async def test_diagnose_node_returns_diagnosis_pydantic_model() -> None:
    """diagnose_node result['diagnosis'] must be a Diagnosis instance."""
    state = _make_state(anomalies=[_make_anomaly()])
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_VALID_DIAGNOSIS_JSON)]

    with patch("src.agents.diagnostics_agent._client") as mock_client:
        with patch("src.agents.diagnostics_agent._vector_store") as mock_store:
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_store.search.return_value = []
            result = await diagnose_node(state)

    assert isinstance(result["diagnosis"], Diagnosis)


@pytest.mark.asyncio
async def test_diagnose_node_sets_current_agent() -> None:
    """diagnose_node must set current_agent to 'diagnostics'."""
    state = _make_state(anomalies=[_make_anomaly()])
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_VALID_DIAGNOSIS_JSON)]

    with patch("src.agents.diagnostics_agent._client") as mock_client:
        with patch("src.agents.diagnostics_agent._vector_store") as mock_store:
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_store.search.return_value = []
            result = await diagnose_node(state)

    assert result["current_agent"] == "diagnostics"
