"""
Agentic AI evaluation helpers.
Computes metrics for agent workflows (goal time, tool latency, recovery rate, etc.)
as described in data-schemas.md (agent.* attributes).
"""
import logging
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)

def goal_completion_time(events: List[dict]) -> float:
    if not events:
        return 0.0
    try:
        timestamps = [e["timestamp"] for e in events if isinstance(e.get("timestamp"), datetime)]
        return (max(timestamps) - min(timestamps)).total_seconds() if timestamps else 0.0
    except Exception as e:
        logger.warning(f"goal_completion_time failed: {e}")
        return 0.0

def tool_latency(events: List[dict]) -> float:
    latencies = [e.get("tool_latency", 0) for e in events if isinstance(e.get("tool_latency"), (int, float))]
    return sum(latencies) / len(latencies) if latencies else 0.0

def error_recovery_rate(events: List[dict]) -> float:
    errors = [e for e in events if e.get("error")]
    if not errors:
        return 1.0
    recovered = [e for e in errors if e.get("recovered")]
    return len(recovered) / len(errors)

def human_intervention_rate(events: List[dict]) -> float:
    if not events:
        return 0.0
    interventions = [e for e in events if e.get("event_type") == "human_intervention"]
    return len(interventions) / len(events)

def unauthorized_actions(events: List[dict]) -> int:
    return len([e for e in events if e.get("unauthorized")])
