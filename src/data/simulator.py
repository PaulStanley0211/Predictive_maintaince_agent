from datetime import UTC, datetime, timedelta

import numpy as np

from src.agents.state import SensorReading

# Sensor baselines for a centrifugal pump (ISO 10816 / engineering standards)
BASELINES: dict[str, float] = {
    "vibration": 2.8,  # mm/s
    "temperature": 62.0,  # °C
    "pressure": 5.5,  # bar
    "power": 45.0,  # kW
}


class SensorSimulator:
    """Generates reproducible synthetic sensor readings for a centrifugal pump."""

    def __init__(self, equipment_id: str, seed: int = 42) -> None:
        """Initialise the simulator with a fixed equipment ID and RNG seed."""
        self.equipment_id = equipment_id
        self._rng = np.random.default_rng(seed)

    def _with_noise(
        self,
        sensor: str,
        index: int,
        total: int,
        anomaly_type: str | None,
    ) -> float:
        """Return a sensor value with Gaussian noise and optional anomaly pattern applied."""
        base = BASELINES[sensor]
        noise = self._rng.normal(0.0, base * 0.03)  # 3% Gaussian noise
        value = base + noise

        if anomaly_type == "bearing_wear":
            # Last 30 % of readings: vibration and temperature ramp upward
            if index >= total * 0.70:
                progress = (index - total * 0.70) / (total * 0.30)  # 0 → 1
                if sensor == "vibration":
                    value += 8.0 * progress
                elif sensor == "temperature":
                    value += 30.0 * progress

        elif anomaly_type == "cavitation":
            # Last 40 % of readings: pressure drops, vibration spikes erratically
            if index >= total * 0.60:
                if sensor == "pressure":
                    value -= 3.0
                elif sensor == "vibration":
                    value += float(self._rng.exponential(scale=2.0))

        elif anomaly_type == "misalignment":
            # All readings: constant vibration offset + 15 % power increase
            if sensor == "vibration":
                value += 3.5
            elif sensor == "power":
                value += BASELINES["power"] * 0.15

        return float(value)

    def generate(
        self,
        count: int = 100,
        anomaly_type: str | None = None,
    ) -> list[SensorReading]:
        """Generate `count` sensor readings, optionally with an injected anomaly pattern."""
        now = datetime.now(UTC)
        readings: list[SensorReading] = []

        for i in range(count):
            timestamp = now - timedelta(minutes=5 * (count - 1 - i))
            readings.append(
                SensorReading(
                    equipment_id=self.equipment_id,
                    timestamp=timestamp,
                    vibration_mm_s=self._with_noise("vibration", i, count, anomaly_type),
                    temperature_c=self._with_noise("temperature", i, count, anomaly_type),
                    pressure_bar=self._with_noise("pressure", i, count, anomaly_type),
                    power_kw=self._with_noise("power", i, count, anomaly_type),
                )
            )

        return readings
