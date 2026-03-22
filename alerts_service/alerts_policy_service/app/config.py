# ==========================================================
# DEFAULT THRESHOLDS (Fallbacks)
# ==========================================================

DEFAULT_THRESHOLDS = {

    # =========================
    # GENERATIVE
    # =========================
    "hallucination_score": 0.05,
    "safety_score": 0.1,
    "pii_leakage_score": 0.0,
    "rag_precision": 0.6,
    "rag_recall": 0.6,
    "rag_freshness": 0.7,
    "tokens_per_second": 20,
    "genai_request_duration_seconds": 5,
    "prompt_tokens": 5000,
    "completion_tokens": 5000,

    # =========================
    # PREDICTIVE (QUALITY)
    # =========================
    "accuracy": 0.75,
    "precision": 0.7,
    "recall": 0.7,
    "mae": 10,
    "rmse": 15,
    "r_squared": 0.6,
    "mape": 0.2,

    # =========================
    # OBSERVABILITY (NEW)
    # =========================
    "model_latency_seconds": 2,
    "model_errors_total": 10,
    "model_predictions_total": 100,
    "error_rate": 0.05,

    # =========================
    # DRIFT
    # =========================
    "drift_score": 0.3,
    "data_quality_score": 0.8,

    # =========================
    # AGENTIC
    # =========================
    "tool_execution_latency": 5000,
    "goal_success_rate": 0.7,
    "error_recovery_rate": 0.6,
    "human_intervention_rate": 0.2,
    "unauthorized_action_attempts": 0,
    "goal_duration_seconds": 600,
    "tool_calls_total": 10,
    "tool_latency_seconds": 5,
    "tool_errors_total": 1,
    "human_interventions_total": 1,
    "intervention_wait_seconds": 120,
    "reasoning_steps_total": 10,
    "goal_cleanup_errors_total": 1
}


# ==========================================================
# PROMETHEUS METRIC MAPPING (CRITICAL)
# ==========================================================

METRIC_MAP = {

    # Core
    "model_latency_seconds": "emms_model_latency_seconds",
    "model_errors_total": "emms_model_errors_total",
    "model_predictions_total": "emms_model_predictions_total",

    # Drift
    "drift_score": "emms_model_drift_score",

    # Quality
    "accuracy": "emms_model_quality_score",
    "precision": "emms_model_quality_score",
    "recall": "emms_model_quality_score",

    # GenAI
    "genai_request_duration_seconds": "emms_genai_request_duration_seconds",
    "prompt_tokens": "emms_genai_token_usage_total",
    "completion_tokens": "emms_genai_token_usage_total"
}


# ==========================================================
# METRIC TYPES (Prometheus)
# ==========================================================

METRIC_TYPES = {
    "emms_model_latency_seconds": "histogram",
    "emms_model_errors_total": "counter",
    "emms_model_predictions_total": "counter",
    "emms_model_drift_score": "gauge",
    "emms_model_quality_score": "gauge",
    "emms_genai_request_duration_seconds": "histogram",
    "emms_genai_token_usage_total": "counter"
}
