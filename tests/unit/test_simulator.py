import pytest

from src.data.simulator import SensorSimulator


@pytest.fixture
def sim() -> SensorSimulator:
    """Default simulator fixture with seed=42."""
    return SensorSimulator("PUMP-001", seed=42)


def test_normal_data_within_baselines(sim: SensorSimulator) -> None:
    """Normal readings should stay within safe operating thresholds."""
    readings = sim.generate(100)
    assert all(r.vibration_mm_s < 4.5 for r in readings)
    assert all(r.temperature_c < 80.0 for r in readings)


def test_bearing_wear_increases_vibration(sim: SensorSimulator) -> None:
    """Bearing wear should ramp vibration significantly by the final reading."""
    readings = sim.generate(100, anomaly_type="bearing_wear")
    assert readings[-1].vibration_mm_s - readings[0].vibration_mm_s > 3.0


def test_bearing_wear_increases_temperature(sim: SensorSimulator) -> None:
    """Bearing wear should ramp temperature significantly by the final reading."""
    readings = sim.generate(100, anomaly_type="bearing_wear")
    assert readings[-1].temperature_c - readings[0].temperature_c > 10.0


def test_cavitation_drops_pressure(sim: SensorSimulator) -> None:
    """Cavitation should push pressure well below the warning threshold of 2.0 bar."""
    readings = sim.generate(100, anomaly_type="cavitation")
    late_readings = readings[60:]  # last 40 % where pattern is active
    assert all(r.pressure_bar < 4.0 for r in late_readings)


def test_misalignment_constant_high_vibration(sim: SensorSimulator) -> None:
    """Misalignment applies a constant +3.5 mm/s offset, so all readings exceed 5.0 mm/s."""
    readings = sim.generate(100, anomaly_type="misalignment")
    assert all(r.vibration_mm_s > 5.0 for r in readings)


def test_correct_count(sim: SensorSimulator) -> None:
    """generate() should return exactly the requested number of readings."""
    assert len(sim.generate(50)) == 50
    assert len(sim.generate(200)) == 200


def test_equipment_id_matches(sim: SensorSimulator) -> None:
    """Every reading must carry the equipment_id the simulator was initialised with."""
    readings = sim.generate(20)
    assert all(r.equipment_id == "PUMP-001" for r in readings)


def test_reproducible_with_seed() -> None:
    """Two simulators with identical seeds must produce identical sensor values.

    Timestamps are excluded — they are derived from wall-clock time, not the RNG,
    so microsecond differences between the two generate() calls are expected.
    """
    a = SensorSimulator("PUMP-TEST", seed=42)
    b = SensorSimulator("PUMP-TEST", seed=42)
    readings_a = a.generate(50)
    readings_b = b.generate(50)
    for ra, rb in zip(readings_a, readings_b):
        assert ra.vibration_mm_s == rb.vibration_mm_s
        assert ra.temperature_c == rb.temperature_c
        assert ra.pressure_bar == rb.pressure_bar
        assert ra.power_kw == rb.power_kw
