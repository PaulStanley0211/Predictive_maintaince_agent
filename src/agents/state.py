from datetime import datetime
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel


class SensorReading(BaseModel):
    """A single snapshot of sensor values from one piece of equipment."""

    equipment_id: str
    timestamp: datetime
    vibration_mm_s: float
    temperature_c: float
    pressure_bar: float
    power_kw: float


class AnomalyAlert(BaseModel):
    """An anomaly detected by the Monitor Agent for a specific sensor."""

    equipment_id: str
    sensor_type: str
    severity: Literal["low", "medium", "high", "critical"]
    z_score: float
    description: str


class Diagnosis(BaseModel):
    """Failure mode diagnosis produced by the Diagnostics Agent."""

    failure_mode: str
    confidence: float  # 0.0 – 1.0
    evidence: list[str]
    similar_incidents: list[str]


class MaintenanceAction(BaseModel):
    """A recommended maintenance action produced by the Recommendation Agent."""

    action: str
    urgency: Literal["immediate", "scheduled", "monitoring"]
    estimated_downtime_hours: float
    cost_of_inaction_eur: float


class AgentState(TypedDict):
    """Shared state passed between all agents in the LangGraph supervisor graph."""

    messages: Annotated[list[Any], add_messages]
    sensor_readings: list[SensorReading]
    anomalies: list[AnomalyAlert]
    diagnosis: Diagnosis | None
    recommended_actions: list[MaintenanceAction]
    ticket_id: str | None
    current_agent: str
    iteration_count: int
