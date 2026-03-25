import asyncio
import json
import logging

import anthropic

from src.agents.state import AgentState, Diagnosis
from src.config.settings import settings
from src.knowledge.vector_store import VectorStore

logger = logging.getLogger(__name__)

DIAGNOSIS_PROMPT = """You are an industrial maintenance diagnostician specialising in centrifugal pumps.

You will receive:
- A list of sensor anomalies detected on a pump (vibration, temperature, pressure, power)
- Relevant excerpts from the maintenance knowledge base describing known failure modes

Your task is to identify the most likely failure mode and respond with a JSON object only — no extra text.

Required JSON format:
{
  "failure_mode": "<name of most likely failure mode>",
  "confidence": <float between 0.0 and 1.0>,
  "evidence": ["<observation supporting the diagnosis>", ...],
  "similar_incidents": ["<matched failure pattern from knowledge base>", ...]
}

Rules:
- confidence above 0.7 means you are highly confident; below 0.4 means insufficient data
- evidence must reference specific sensor readings and their deviation from normal
- similar_incidents must be drawn from the knowledge base excerpts provided, not invented
- If anomalies are ambiguous, return the best guess with a low confidence score
- Always return valid JSON, nothing else"""

_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 1.0

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
_vector_store = VectorStore()


def _build_user_message(anomaly_descriptions: list[str], rag_results: list[str]) -> str:
    """Format anomaly data and RAG results into a single user message."""
    anomaly_block = "\n".join(f"- {desc}" for desc in anomaly_descriptions)
    rag_block = "\n\n---\n\n".join(rag_results) if rag_results else "No similar incidents found."
    return f"## Detected Anomalies\n{anomaly_block}\n\n## Relevant Knowledge Base Entries\n{rag_block}"


def _fallback_diagnosis(reason: str) -> Diagnosis:
    """Return a low-confidence diagnosis used when the API call fails."""
    return Diagnosis(
        failure_mode="unknown",
        confidence=0.0,
        evidence=[f"Diagnosis unavailable: {reason}"],
        similar_incidents=[],
    )


async def _call_claude(user_message: str) -> Diagnosis:
    """Call Claude with retry logic and parse the response into a Diagnosis."""
    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await _client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                system=DIAGNOSIS_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            data = json.loads(raw)
            return Diagnosis(**data)

        except anthropic.APIError as exc:
            last_error = exc
            logger.warning("Claude API error on attempt %d/%d: %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY_SECONDS)

        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning("Failed to parse Claude response on attempt %d/%d: %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY_SECONDS)

    return _fallback_diagnosis(str(last_error))


async def diagnose_node(state: AgentState) -> dict:
    """LangGraph node: diagnose failure mode from anomalies using Claude and RAG."""
    anomalies = state["anomalies"]

    if not anomalies:
        return {
            "diagnosis": _fallback_diagnosis("No anomalies to diagnose"),
            "current_agent": "diagnostics",
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    anomaly_descriptions = [a.description for a in anomalies]

    # RAG: search knowledge base using combined anomaly signals as query
    query = " ".join(a.sensor_type for a in anomalies) + " anomaly pump failure"
    rag_results = _vector_store.search(query, top_k=5)

    user_message = _build_user_message(anomaly_descriptions, rag_results)
    diagnosis = await _call_claude(user_message)

    return {
        "diagnosis": diagnosis,
        "current_agent": "diagnostics",
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
