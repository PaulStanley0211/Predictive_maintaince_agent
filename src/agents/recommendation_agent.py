import asyncio
import json
import logging
from pathlib import Path

import anthropic

from src.agents.state import AgentState, Diagnosis, MaintenanceAction
from src.config.settings import settings

logger = logging.getLogger(__name__)

_FAILURE_MODES_PATH = Path(__file__).parent.parent / "data" / "failure_modes.json"

RECOMMENDATION_PROMPT = """You are a maintenance planning expert for industrial centrifugal pumps.

You will receive:
- A confirmed failure mode diagnosis with confidence score and supporting evidence
- The matching failure mode record from the maintenance knowledge base

Your task is to produce a prioritised list of maintenance actions and respond with a JSON array only — no extra text.

Required JSON format:
[
  {
    "action": "<specific, actionable maintenance task>",
    "urgency": "<immediate | scheduled | monitoring>",
    "estimated_downtime_hours": <float>,
    "cost_of_inaction_eur": <float per day>
  }
]

Rules:
- Return 1 to 3 actions ordered from most to least urgent
- "immediate" means stop the pump within the hour; "scheduled" means plan within days;
  "monitoring" means watch closely but no intervention yet
- action must be a concrete instruction (e.g. "Replace bearing assembly on PUMP-001"), not a vague suggestion
- estimated_downtime_hours is total expected repair time including preparation
- cost_of_inaction_eur is the estimated daily cost of NOT acting (production loss + damage accumulation)
- Adjust urgency upward if confidence is high and severity is critical
- Always return a valid JSON array, nothing else"""

_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 1.0

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _load_failure_modes() -> dict[str, dict]:
    """Load failure_modes.json and return a dict keyed by failure mode name."""
    try:
        with _FAILURE_MODES_PATH.open() as f:
            data = json.load(f)
        return {mode["name"]: mode for mode in data["failure_modes"]}
    except FileNotFoundError:
        logger.error("failure_modes.json not found at %s", _FAILURE_MODES_PATH)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse failure_modes.json: %s", exc)
        return {}


def _default_actions(failure_mode_name: str) -> list[MaintenanceAction]:
    """Return a fallback MaintenanceAction from failure_modes.json when Claude is unavailable."""
    modes = _load_failure_modes()
    mode = modes.get(failure_mode_name) or modes.get("bearing_wear")
    if mode is None:
        logger.error("No fallback failure mode found; returning generic monitoring action")
        return [
            MaintenanceAction(
                action=f"Inspect equipment for '{failure_mode_name}' symptoms",
                urgency="monitoring",
                estimated_downtime_hours=0.0,
                cost_of_inaction_eur=0.0,
            )
        ]
    return [
        MaintenanceAction(
            action=mode["recommended_action"],
            urgency=mode["default_urgency"],
            estimated_downtime_hours=float(mode["typical_downtime_hours"]),
            cost_of_inaction_eur=float(mode["cost_of_inaction_per_day_eur"]),
        )
    ]


def _build_user_message(diagnosis: Diagnosis, mode_record: dict | None) -> str:
    """Combine diagnosis and failure mode record into a user message for Claude."""
    evidence_block = "\n".join(f"- {e}" for e in diagnosis.evidence)
    mode_block = json.dumps(mode_record, indent=2) if mode_record else "No matching record found."
    return (
        f"## Diagnosis\n"
        f"Failure mode: {diagnosis.failure_mode}\n"
        f"Confidence: {diagnosis.confidence:.2f}\n"
        f"Evidence:\n{evidence_block}\n\n"
        f"## Knowledge Base Record\n{mode_block}"
    )


async def _call_claude(user_message: str) -> list[MaintenanceAction] | None:
    """Call Claude and parse the response into a list of MaintenanceAction. Returns None on failure."""
    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await _client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                system=RECOMMENDATION_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            items = json.loads(raw)
            return [MaintenanceAction(**item) for item in items]

        except anthropic.APIError as exc:
            last_error = exc
            logger.warning("Claude API error on attempt %d/%d: %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY_SECONDS)

        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
            logger.warning("Failed to parse Claude response on attempt %d/%d: %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY_SECONDS)

    logger.error("All %d Claude attempts failed: %s", _MAX_RETRIES, last_error)
    return None


async def recommend_node(state: AgentState) -> dict:
    """LangGraph node: generate maintenance recommendations from the current diagnosis."""
    diagnosis: Diagnosis | None = state.get("diagnosis")

    if diagnosis is None:
        return {
            "recommended_actions": [],
            "current_agent": "recommendation",
        }

    modes = _load_failure_modes()
    mode_record = modes.get(diagnosis.failure_mode)

    user_message = _build_user_message(diagnosis, mode_record)
    actions = await _call_claude(user_message)

    if actions is None:
        logger.warning("Falling back to default recommendations for '%s'", diagnosis.failure_mode)
        actions = _default_actions(diagnosis.failure_mode)

    return {
        "recommended_actions": actions,
        "current_agent": "recommendation",
    }
