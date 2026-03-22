"""
Model Owner Metrics Transformation

Transforms telemetry and monitoring metrics into model-owner
operational dashboards.

Answers:

1. Which models are degrading?
2. Which models require intervention?
3. What alerts should be triggered?

Base Tables Used

telemetry.emms_llm
telemetry.generative_metrics
telemetry.predictive_metrics
telemetry.agentic_metrics
"""

from collections import defaultdict
from utils.bq_client import BigQueryClient
from utils.logger import get_logger
from registry.model_registry_client import ModelRegistryClient

logger = get_logger("model_owner_transform")


class ModelOwnerTransform:

    def __init__(self):

        self.bq = BigQueryClient()
        self.registry = ModelRegistryClient()

    def run(self):

        logger.info("Starting Model Owner Transformation")

        # --------------------------------------
        # Load telemetry base tables
        # --------------------------------------

        llm_rows = self.bq.read_table("telemetry.emms_llm")
        predictive_rows = self.bq.read_table("telemetry.predictive_metrics")
        generative_rows = self.bq.read_table("telemetry.generative_metrics")
        agent_rows = self.bq.read_table("telemetry.agentic_metrics")

        models = self.registry.load_models()

        # --------------------------------------
        # Aggregation structure
        # --------------------------------------

        model_stats = defaultdict(lambda: {
            "requests": 0,
            "latencies": [],
            "errors": 0,
            "drift_scores": [],
            "hallucinations": [],
            "safety_scores": [],
            "agent_success": []
        })

        # --------------------------------------
        # Process LLM telemetry
        # --------------------------------------

        for r in llm_rows:

            model_id = r.get("model_id")

            if not model_id:
                continue

            m = model_stats[model_id]

            m["requests"] += 1

            if r.get("latency_ms") is not None:
                m["latencies"].append(r["latency_ms"])

            if r.get("status") == "error":
                m["errors"] += 1

        # --------------------------------------
        # Predictive model drift
        # --------------------------------------

        for r in predictive_rows:

            model_id = r.get("model_id")

            if not model_id:
                continue

            if r.get("drift_score") is not None:
                model_stats[model_id]["drift_scores"].append(r["drift_score"])

        # --------------------------------------
        # Generative hallucination + safety
        # --------------------------------------

        for r in generative_rows:

            model_id = r.get("model_id")

            if not model_id:
                continue

            if r.get("hallucination_score") is not None:
                model_stats[model_id]["hallucinations"].append(
                    r["hallucination_score"]
                )

            if r.get("safety_score") is not None:
                model_stats[model_id]["safety_scores"].append(
                    r["safety_score"]
                )

        # --------------------------------------
        # Agent metrics
        # --------------------------------------

        for r in agent_rows:

            model_id = r.get("model_id")

            if not model_id:
                continue

            if r.get("goal_success_rate") is not None:
                model_stats[model_id]["agent_success"].append(
                    r["goal_success_rate"]
                )

        # --------------------------------------
        # Build derived rows
        # --------------------------------------

        dashboard_rows = []
        alert_rows = []

        for model_id, m in model_stats.items():

            latency = avg(m["latencies"])
            drift = avg(m["drift_scores"])
            hallucination = avg(m["hallucinations"])
            safety = avg(m["safety_scores"])
            agent_success = avg(m["agent_success"])

            error_rate = m["errors"] / max(m["requests"], 1)

            alert_level = "NONE"

            # --------------------------------------
            # Alert rules
            # --------------------------------------

            if drift is not None and drift > 0.4:
                alert_level = "CRITICAL"

                alert_rows.append({
                    "model_id": model_id,
                    "alert_type": "DRIFT",
                    "severity": "CRITICAL",
                    "message": "Model drift exceeded threshold"
                })

            elif hallucination is not None and hallucination > 0.3:
                alert_level = "WARNING"

                alert_rows.append({
                    "model_id": model_id,
                    "alert_type": "HALLUCINATION",
                    "severity": "WARNING",
                    "message": "Hallucination rate elevated"
                })

            elif safety is not None and safety > 0.5:
                alert_level = "CRITICAL"

                alert_rows.append({
                    "model_id": model_id,
                    "alert_type": "SAFETY",
                    "severity": "CRITICAL",
                    "message": "Unsafe outputs detected"
                })

            dashboard_rows.append({

                "model_id": model_id,
                "owner_team": models.get(model_id, {}).get("owner_team"),

                "request_volume": m["requests"],
                "avg_latency_ms": latency,
                "error_rate": error_rate,

                "avg_drift_score": drift,
                "avg_hallucination_score": hallucination,
                "avg_safety_score": safety,
                "avg_agent_success_rate": agent_success,

                "alert_level": alert_level
            })

        # --------------------------------------
        # Write derived tables
        # --------------------------------------

        self.bq.write_table(
            "analytics.model_owner_dashboard",
            dashboard_rows
        )

        self.bq.write_table(
            "analytics.emms_alerts",
            alert_rows
        )

        logger.info("Model owner transformation complete")


def avg(values):

    if not values:
        return None

    return sum(values) / len(values)


if __name__ == "__main__":
    ModelOwnerTransform().run()
