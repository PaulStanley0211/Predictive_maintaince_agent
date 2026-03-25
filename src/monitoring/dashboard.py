"""Streamlit real-time monitoring dashboard for the predictive maintenance system."""

import asyncio

import pandas as pd
import streamlit as st

from src.agents.state import AnomalyAlert, Diagnosis, MaintenanceAction
from src.agents.supervisor import build_graph
from src.data.simulator import SensorSimulator

# ── Constants ─────────────────────────────────────────────────────────────────

_SEV_FN = {"critical": st.error, "high": st.warning, "medium": st.info, "low": st.info}
_URG_ICON = {"immediate": "🔴", "scheduled": "🟠", "monitoring": "🟢"}


# ── Cached resources ──────────────────────────────────────────────────────────


@st.cache_resource
def _graph():
    """Compile the LangGraph supervisor graph once per process."""
    return build_graph()


# ── Pipeline runner ───────────────────────────────────────────────────────────


def _run_pipeline(equipment_id: str, anomaly_type: str | None, reading_count: int) -> tuple:
    """Generate sensor data and run the full agent pipeline.

    Falls back to direct invocation when the FastAPI server is not running.
    """
    readings = SensorSimulator(equipment_id).generate(count=reading_count, anomaly_type=anomaly_type)

    # Try the running FastAPI server first.
    try:
        import httpx

        with httpx.Client(timeout=3.0) as http:
            resp = http.post(
                f"http://localhost:8000/simulate/{equipment_id}",
                json={
                    "equipment_id": equipment_id,
                    "anomaly_type": anomaly_type,
                    "reading_count": reading_count,
                },
            )
            resp.raise_for_status()
            raw = resp.json()
            result = {
                "anomalies": [AnomalyAlert(**a) for a in raw["anomalies"]],
                "diagnosis": Diagnosis(**raw["diagnosis"]) if raw["diagnosis"] else None,
                "recommended_actions": [MaintenanceAction(**a) for a in raw["actions"]],
                "ticket_id": raw["ticket_id"],
            }
            return readings, result
    except Exception:
        pass

    # Direct invocation fallback.
    initial_state = {
        "messages": [],
        "sensor_readings": readings,
        "anomalies": [],
        "diagnosis": None,
        "recommended_actions": [],
        "ticket_id": None,
        "current_agent": "monitor",
        "iteration_count": 0,
    }
    result = asyncio.run(_graph().ainvoke(initial_state))
    return readings, result


# ── Page layout ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="Predictive Maintenance Dashboard", layout="wide")
st.title("Predictive Maintenance Dashboard")

# Sidebar ─────────────────────────────────────────────────────────────────────
st.sidebar.header("Configuration")
equipment_id = st.sidebar.selectbox("Equipment", ["PUMP-001", "PUMP-002", "PUMP-003"])
_raw = st.sidebar.selectbox("Anomaly Type", ["None", "bearing_wear", "cavitation", "misalignment"])
anomaly_type: str | None = None if _raw == "None" else _raw
reading_count = st.sidebar.slider("Reading Count", min_value=50, max_value=500, value=100, step=50)

if not st.button("Run Analysis", type="primary"):
    st.info("Configure equipment in the sidebar and click **Run Analysis** to start.")
    st.stop()

# Run pipeline ─────────────────────────────────────────────────────────────────
with st.spinner("Running analysis pipeline…"):
    readings, result = _run_pipeline(equipment_id, anomaly_type, reading_count)

# 1 ── Sensor Readings ─────────────────────────────────────────────────────────
st.subheader("Sensor Readings")
df = pd.DataFrame(
    [
        {
            "timestamp": r.timestamp,
            "Vibration (mm/s)": r.vibration_mm_s,
            "Temperature (°C)": r.temperature_c,
            "Pressure (bar)": r.pressure_bar,
            "Power (kW)": r.power_kw,
        }
        for r in readings
    ]
).set_index("timestamp")

c1, c2 = st.columns(2)
c3, c4 = st.columns(2)
c1.line_chart(df[["Vibration (mm/s)"]], height=220)
c2.line_chart(df[["Temperature (°C)"]], height=220)
c3.line_chart(df[["Pressure (bar)"]], height=220)
c4.line_chart(df[["Power (kW)"]], height=220)

# 2 ── Anomaly Detection ───────────────────────────────────────────────────────
st.subheader("Anomaly Detection")
anomalies: list[AnomalyAlert] = result.get("anomalies", [])
if not anomalies:
    st.success("✅ No anomalies detected.")
else:
    for a in anomalies:
        msg = (
            f"**{a.sensor_type.upper()}** — {a.description}"
            f" &nbsp; `z = {a.z_score:+.2f}` &nbsp; severity: `{a.severity}`"
        )
        _SEV_FN.get(a.severity, st.info)(msg)

# 3 ── Diagnosis ───────────────────────────────────────────────────────────────
st.subheader("Diagnosis")
diagnosis: Diagnosis | None = result.get("diagnosis")
if diagnosis is None:
    st.info("No diagnosis generated.")
else:
    st.markdown(f"**Failure mode:** `{diagnosis.failure_mode}`")
    st.progress(diagnosis.confidence, text=f"Confidence: {diagnosis.confidence:.0%}")
    st.markdown("**Evidence:**")
    for evidence in diagnosis.evidence:
        st.markdown(f"- {evidence}")
    if diagnosis.similar_incidents:
        with st.expander("Similar incidents"):
            for incident in diagnosis.similar_incidents:
                st.markdown(f"- {incident}")

# 4 ── Recommended Actions ─────────────────────────────────────────────────────
st.subheader("Recommended Actions")
actions: list[MaintenanceAction] = result.get("recommended_actions", [])
if not actions:
    st.info("No actions recommended.")
else:
    st.table(
        pd.DataFrame(
            [
                {
                    "Urgency": f"{_URG_ICON.get(a.urgency, '')} {a.urgency}",
                    "Action": a.action,
                    "Downtime (h)": a.estimated_downtime_hours,
                    "Cost of Inaction (€/day)": a.cost_of_inaction_eur,
                }
                for a in actions
            ]
        )
    )

# 5 ── Maintenance Ticket ──────────────────────────────────────────────────────
st.subheader("Maintenance Ticket")
ticket_id: str | None = result.get("ticket_id")
if ticket_id is None:
    st.info("No ticket created (no actionable findings).")
else:
    st.success(f"Ticket created: **`{ticket_id}`** &nbsp;&nbsp; Status: `open`")
