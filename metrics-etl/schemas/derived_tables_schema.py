"""
Derived Audience Tables Schema

Defines schemas for all analytics audience tables produced by
the EMMS Metric Transform service.

Audience Layers

1. Executive AI Summary
2. Model Owner Dashboard
3. Compliance Audit Dashboard
4. Alert Monitoring Table
"""

DERIVED_TABLES = {

# =========================================================
# EXECUTIVE TABLE
# =========================================================

"analytics.executive_ai_summary": [

("model_id", "STRING"),

("request_volume", "INTEGER"),
("monthly_cost_usd", "FLOAT"),
("tokens_used", "INTEGER"),

("avg_latency_ms", "FLOAT"),
("success_rate", "FLOAT"),

("avg_drift_score", "FLOAT"),
("avg_hallucination_score", "FLOAT"),
("avg_safety_score", "FLOAT"),
("avg_agent_success_rate", "FLOAT"),

("model_health_status", "STRING")

],


# =========================================================
# MODEL OWNER DASHBOARD
# =========================================================

"analytics.model_owner_dashboard": [

("model_id", "STRING"),
("owner_team", "STRING"),

("request_volume", "INTEGER"),
("avg_latency_ms", "FLOAT"),
("error_rate", "FLOAT"),

("avg_drift_score", "FLOAT"),
("avg_hallucination_score", "FLOAT"),
("avg_safety_score", "FLOAT"),
("avg_agent_success_rate", "FLOAT"),

("alert_level", "STRING")

],


# =========================================================
# ALERTS TABLE
# =========================================================

"analytics.emms_alerts": [

("model_id", "STRING"),

("alert_type", "STRING"),
("severity", "STRING"),

("message", "STRING")

],


# =========================================================
# COMPLIANCE / GOVERNANCE TABLE
# =========================================================

"analytics.compliance_audit_dashboard": [

("model_id", "STRING"),
("owner_team", "STRING"),

("telemetry_events", "INTEGER"),

("is_monitored", "BOOLEAN"),
("registry_registered", "BOOLEAN"),

("compliance_status", "STRING")

]

}
