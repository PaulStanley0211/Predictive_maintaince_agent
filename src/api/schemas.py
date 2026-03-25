from pydantic import BaseModel, Field

from src.agents.state import AnomalyAlert, Diagnosis, MaintenanceAction, SensorReading


class RunRequest(BaseModel):
    """Request body for running the full maintenance agent pipeline."""

    sensor_readings: list[SensorReading]


class RunResponse(BaseModel):
    """Response produced by the multi-agent maintenance pipeline."""

    anomalies: list[AnomalyAlert]
    diagnosis: Diagnosis | None
    actions: list[MaintenanceAction]
    ticket_id: str | None


class HealthResponse(BaseModel):
    """Service health and architecture metadata."""

    status: str
    agents_count: int
    mcp_servers_count: int


class EquipmentMonitorRequest(BaseModel):
    """Request body for a simulated equipment monitoring run."""

    equipment_id: str = Field(..., min_length=1)
    anomaly_type: str | None = None
    reading_count: int = 100
