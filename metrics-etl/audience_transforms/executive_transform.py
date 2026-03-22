"""
Executive Metrics Transformation

Transforms raw telemetry and monitoring metrics into an executive
summary table that answers:

1. How many models are healthy?
2. What is our AI cost?
3. What is system usage and performance?

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

logger = get_logger("executive_transform")


class ExecutiveTransform:

    def __init__(self):

        self.bq = BigQueryClient()
        self.registry = ModelRegistryClient()

    def run(self):

        logger.info("Starting Executive Transformation")

        # --------------------------------------
        # Load base tables from BigQuery
        # --------------------------------------

        llm_rows = self.bq.read_table("telemetry.emms_llm")
        predictive_rows = self.bq.read_table("telemetry.predictive_metrics")
        generative_rows = self.bq.read_table("telemetry.generative_metrics")
        agent_rows = self.bq.read_table("telemetry.agentic_metrics")

        # Load model registry
        models = self.registry.load_models()

        # --------------------------------------
        # Aggregate metrics per model
        # --------------------------------------

        model_stats = defaultdict(lambda: {
            "requests": 0,
            "cost": 0.0,
            "tokens": 0,
            "latencies": [],
            "success": 0,
            "drift_scores": [],
            "hallucinations": [],
            "safety_scores": [],
            "agent_success": []
        })

        # --------------------------------------
        # Process emms_llm telemetry
        # --------------------------------------

        for r in llm_rows:

            model_id = r.get("model_id")

            if not model_id:
                continue

            m = model_stats[model_id]

            m["requests"] += 1
            m["cost"] += r.get("cost_usd", 0) or 0
            m["tokens"] += r.get("total_tokens", 0) or 0

            if r.get("latency_ms"):
                m["latencies"].append(r["latency_ms"])

            if r.get("status") == "success":
                m["success"] += 1

        # --------------------------------------
        # Predictive metrics → drift monitoring
        # --------------------------------------

        for r in predictive_rows:

            model_id = r.get("model_id")

            if not model_id:
                continue

            if r.get("drift_score") is not None:
                model_stats[model_id]["drift_scores"].append(r["drift_score"])

        # --------------------------------------
        # Generative metrics → hallucination + safety
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
        # Agent metrics → success monitoring
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
        # Build derived executive dashboard rows
        # --------------------------------------

        rows = []

        for model_id, m in model_stats.items():

            avg_latency = avg(m["latencies"])
            success_rate = m["success"] / max(m["requests"], 1)

            drift = avg(m["drift_scores"])
            hallucination = avg(m["hallucinations"])
            safety = avg(m["safety_scores"])
            agent_success = avg(m["agent_success"])

            # --------------------------------------
            # Model Health Classification
            # --------------------------------------

            if drift is not None and drift > 0.4:
                health = "CRITICAL"

            elif drift is not None and drift > 0.2:
                health = "DEGRADED"

            elif safety is not None and safety > 0.5:
                health = "CRITICAL"

            else:
                health = "HEALTHY"

            rows.append({

                "model_id": model_id,
                "owner_team": models.get(model_id, {}).get("owner_team"),

                "request_volume": m["requests"],
                "monthly_cost_usd": m["cost"],
                "tokens_used": m["tokens"],

                "avg_latency_ms": avg_latency,
                "success_rate": success_rate,

                "avg_drift_score": drift,
                "avg_hallucination_score": hallucination,
                "avg_safety_score": safety,
                "avg_agent_success_rate": agent_success,

                "model_health_status": health
            })

        # --------------------------------------
        # Write to Executive Dashboard Table
        # --------------------------------------

        self.bq.write_table(
            "analytics.executive_dashboard",
            rows
        )

        logger.info("Executive transformation complete")


def avg(values):

    if not values:
        return None

    return sum(values) / len(values)


if __name__ == "__main__":
    ExecutiveTransform().run()
