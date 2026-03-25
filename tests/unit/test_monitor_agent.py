import pytest

from src.agents.monitor_agent import detect_anomalies
from src.data.simulator import SensorSimulator


@pytest.fixture
def sim() -> SensorSimulator:
    """Default simulator fixture with seed=42."""
    return SensorSimulator("PUMP-001", seed=42)


def test_detects_bearing_wear(sim: SensorSimulator) -> None:
    """Bearing wear pattern should produce at least one anomaly alert."""
    readings = sim.generate(100, anomaly_type="bearing_wear")
    anomalies = detect_anomalies(readings)
    assert len(anomalies) >= 1


def test_detects_cavitation(sim: SensorSimulator) -> None:
    """Cavitation pattern should produce at least one anomaly alert."""
    readings = sim.generate(100, anomaly_type="cavitation")
    anomalies = detect_anomalies(readings)
    assert len(anomalies) >= 1


def test_no_anomaly_on_normal_data(sim: SensorSimulator) -> None:
    """Normal sensor data should produce zero anomaly alerts."""
    readings = sim.generate(100)
    anomalies = detect_anomalies(readings)
    assert len(anomalies) == 0


def test_severity_levels_correct(sim: SensorSimulator) -> None:
    """Bearing wear vibration anomaly should be classified as high or critical."""
    readings = sim.generate(100, anomaly_type="bearing_wear")
    anomalies = detect_anomalies(readings)
    vibration_alerts = [a for a in anomalies if a.sensor_type == "vibration"]
    assert len(vibration_alerts) >= 1
    assert all(a.severity in {"high", "critical"} for a in vibration_alerts)


def test_misalignment_detected(sim: SensorSimulator) -> None:
    """Misalignment should trigger a vibration anomaly alert."""
    readings = sim.generate(100, anomaly_type="misalignment")
    anomalies = detect_anomalies(readings)
    sensor_types = {a.sensor_type for a in anomalies}
    assert "vibration" in sensor_types
