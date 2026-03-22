# ==========================================================
# CRITICAL: Safety / Compliance
# ==========================================================
CRITICAL_METRICS = [
    "pii_leakage_score",
    "safety_score",
    "unauthorized_action_attempts"
]

# ==========================================================
# MEDIUM: Drift + RAG + Hallucination
# ==========================================================
MEDIUM_METRICS = [
    "drift_score",
    "data_quality_score",
    "hallucination_score",
    "rag_precision",
    "rag_recall",
    "rag_freshness"
]

# ==========================================================
# LOW: Operational
# ==========================================================
LOW_METRICS = [
    "model_latency_seconds",
    "genai_request_duration_seconds",
    "throughput",
    "tool_latency_seconds"
]


def is_high_metric(metric):
    return (
        metric not in CRITICAL_METRICS and
        metric not in MEDIUM_METRICS and
        metric not in LOW_METRICS
    )


def get_severity(metric):

    if metric in CRITICAL_METRICS:
        return "CRITICAL"

    if metric in MEDIUM_METRICS:
        return "MEDIUM"

    if metric in LOW_METRICS:
        return "LOW"

    if is_high_metric(metric):
        return "HIGH"

    return "LOW"
