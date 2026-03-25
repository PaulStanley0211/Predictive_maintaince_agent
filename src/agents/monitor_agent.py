import numpy as np

from src.agents.state import AgentState, AnomalyAlert, SensorReading

# ISO 10816 vibration severity thresholds (Class III — pumps, motors, generators)
# and engineering-standard limits for temperature, pressure, and power.
THRESHOLDS: dict[str, dict[str, float]] = {
    "vibration": {"warning": 4.5, "critical": 11.2},
    "temperature": {"warning": 85.0, "critical": 105.0},
    "pressure": {"warning_low": 2.0, "warning_high": 8.5, "critical": 10.0},
    "power": {"warning_deviation": 0.20},
}

# Baseline power (kW) used to compute percentage deviation.
_POWER_BASELINE: float = 45.0


def classify_severity(sensor: str, value: float, z_score: float) -> str | None:
    """Return severity level for a sensor reading, or None if within normal range."""
    t = THRESHOLDS[sensor]

    if sensor == "pressure":
        is_critical = value > t["critical"]
        is_warning = value < t["warning_low"] or value > t["warning_high"]
    elif sensor == "power":
        deviation = abs(value - _POWER_BASELINE) / _POWER_BASELINE
        is_critical = deviation > t["warning_deviation"] * 2  # 40% deviation = critical
        is_warning = deviation > t["warning_deviation"]
    else:
        is_critical = value > t["critical"]
        is_warning = value > t["warning"]

    if is_critical or z_score > 3.0:
        return "critical"
    if is_warning or z_score > 2.5:
        return "high"
    if z_score > 2.0:
        return "medium"
    if z_score > 1.5:
        return "low"
    return None


def detect_anomalies(readings: list[SensorReading]) -> list[AnomalyAlert]:
    """Analyse a window of sensor readings and return alerts for the latest reading."""
    if not readings:
        return []

    latest = readings[-1]
    alerts: list[AnomalyAlert] = []

    sensor_values: dict[str, list[float]] = {
        "vibration": [r.vibration_mm_s for r in readings],
        "temperature": [r.temperature_c for r in readings],
        "pressure": [r.pressure_bar for r in readings],
        "power": [r.power_kw for r in readings],
    }
    latest_values: dict[str, float] = {
        "vibration": latest.vibration_mm_s,
        "temperature": latest.temperature_c,
        "pressure": latest.pressure_bar,
        "power": latest.power_kw,
    }

    for sensor, values in sensor_values.items():
        arr = np.array(values, dtype=float)
        std = float(np.std(arr))
        mean = float(np.mean(arr))
        current = latest_values[sensor]

        z_score = (current - mean) / std if std > 0.0 else 0.0
        severity = classify_severity(sensor, current, z_score)

        if severity is not None:
            alerts.append(
                AnomalyAlert(
                    equipment_id=latest.equipment_id,
                    sensor_type=sensor,
                    severity=severity,
                    z_score=round(z_score, 4),
                    description=(
                        f"{sensor} reading {current:.2f} deviates {z_score:+.2f}σ from window mean {mean:.2f}"
                    ),
                )
            )

    return alerts


async def monitor_node(state: AgentState) -> dict:
    """LangGraph node: detect anomalies in the current sensor window and update state."""
    anomalies = detect_anomalies(state["sensor_readings"])
    return {
        "anomalies": anomalies,
        "current_agent": "monitor",
    }
