import json

from mcp.server.fastmcp import FastMCP

from src.data.simulator import SensorSimulator

_KNOWN_EQUIPMENT = {"PUMP-001", "PUMP-002", "PUMP-003"}

mcp = FastMCP("sensor-data")


@mcp.tool()
def get_latest_readings(equipment_id: str, count: int = 50) -> str:
    """Generate the latest sensor readings for a piece of equipment.

    Args:
        equipment_id: The equipment identifier (e.g. PUMP-001).
        count: Number of readings to return (default 50, max 200).
    """
    if equipment_id not in _KNOWN_EQUIPMENT:
        return json.dumps(
            {"error": f"Unknown equipment_id '{equipment_id}'. Valid options: {sorted(_KNOWN_EQUIPMENT)}"}
        )

    count = max(1, min(count, 200))  # clamp to [1, 200]
    sim = SensorSimulator(equipment_id)
    readings = sim.generate(count)

    payload = [
        {
            "equipment_id": r.equipment_id,
            "timestamp": r.timestamp.isoformat(),
            "vibration_mm_s": round(r.vibration_mm_s, 4),
            "temperature_c": round(r.temperature_c, 4),
            "pressure_bar": round(r.pressure_bar, 4),
            "power_kw": round(r.power_kw, 4),
        }
        for r in readings
    ]
    return json.dumps(payload)


@mcp.tool()
def get_equipment_list() -> str:
    """Return the list of monitored equipment with their current status."""
    equipment = [
        {"equipment_id": "PUMP-001", "name": "Centrifugal Pump 1", "status": "online"},
        {"equipment_id": "PUMP-002", "name": "Centrifugal Pump 2", "status": "online"},
        {"equipment_id": "PUMP-003", "name": "Centrifugal Pump 3", "status": "online"},
    ]
    return json.dumps(equipment)


if __name__ == "__main__":
    mcp.run(transport="stdio")
