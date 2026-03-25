import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from src.agents.state import AgentState
from src.api.schemas import (
    EquipmentMonitorRequest,
    HealthResponse,
    RunRequest,
    RunResponse,
)
from src.data.simulator import SensorSimulator

router = APIRouter()

_FAILURE_MODES_PATH = Path(__file__).parent.parent / "data" / "failure_modes.json"

_AGENTS_COUNT = 4  # monitor, diagnostics, recommendation, workflow
_MCP_SERVERS_COUNT = 3  # sensor_data_server, knowledge_server, task_server


def _build_initial_state(sensor_readings: list) -> AgentState:
    """Create a clean AgentState from a list of sensor readings."""
    return {
        "messages": [],
        "sensor_readings": sensor_readings,
        "anomalies": [],
        "diagnosis": None,
        "recommended_actions": [],
        "ticket_id": None,
        "current_agent": "monitor",
        "iteration_count": 0,
    }


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return service health and agent/MCP server counts."""
    return HealthResponse(
        status="ok",
        agents_count=_AGENTS_COUNT,
        mcp_servers_count=_MCP_SERVERS_COUNT,
    )


@router.post("/run", response_model=RunResponse)
async def run_pipeline(body: RunRequest, request: Request) -> RunResponse:
    """Accept sensor readings, run the multi-agent pipeline, and return results."""
    if not body.sensor_readings:
        raise HTTPException(status_code=422, detail="sensor_readings must not be empty")

    try:
        graph = request.app.state.graph
        result: AgentState = await graph.ainvoke(_build_initial_state(body.sensor_readings))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RunResponse(
        anomalies=result.get("anomalies", []),
        diagnosis=result.get("diagnosis"),
        actions=result.get("recommended_actions", []),
        ticket_id=result.get("ticket_id"),
    )


@router.post("/simulate/{equipment_id}", response_model=RunResponse)
async def simulate(
    equipment_id: str,
    body: EquipmentMonitorRequest,
    request: Request,
) -> RunResponse:
    """Generate synthetic sensor data for equipment_id and run it through the pipeline."""
    simulator = SensorSimulator(equipment_id)
    readings = simulator.generate(count=body.reading_count, anomaly_type=body.anomaly_type)

    try:
        graph = request.app.state.graph
        result: AgentState = await graph.ainvoke(_build_initial_state(readings))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RunResponse(
        anomalies=result.get("anomalies", []),
        diagnosis=result.get("diagnosis"),
        actions=result.get("recommended_actions", []),
        ticket_id=result.get("ticket_id"),
    )


@router.get("/failure-modes")
async def failure_modes() -> list[dict]:
    """Return all known failure mode definitions from failure_modes.json."""
    try:
        with _FAILURE_MODES_PATH.open() as f:
            data = json.load(f)
        return data["failure_modes"]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="failure_modes.json not found") from exc
