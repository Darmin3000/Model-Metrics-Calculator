PREDICTIVE_METRICS = [
    "accuracy","precision_score","recall_score","log_loss",
    "brier_score","ece","mae","rmse","r_squared","mape",
    "drift_score","feature_drift_ratio","target_drift_score",
    "data_quality_score"
]

GENERATIVE_METRICS = [
    "hallucination_score","safety_score","pii_leakage_score",
    "rag_precision","rag_recall","rag_freshness_days",
    "tokens_per_second"
]

AGENTIC_METRICS = [
    "goal_completion_time_seconds","tool_execution_latency_seconds",
    "goal_success_rate","error_recovery_rate",
    "human_intervention_rate","unauthorized_action_attempts"
]
