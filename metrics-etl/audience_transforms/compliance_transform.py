"""
Compliance Metrics Transformation

Creates compliance and governance dashboards
tracking model registry coverage, monitoring
coverage, and audit readiness.

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

logger = get_logger("compliance_transform")


class ComplianceTransform:

    def __init__(self):

        self.bq = BigQueryClient()
        self.registry = ModelRegistryClient()

    def run(self):

        logger.info("Starting Compliance Transformation")

        llm_rows = self.bq.read_table("telemetry.emms_llm")

        predictive_rows = self.bq.read_table("telemetry.predictive_metrics")

        generative_rows = self.bq.read_table("telemetry.generative_metrics")

        agent_rows = self.bq.read_table("telemetry.agentic_metrics")

        models = self.registry.load_models()

        # --------------------------------------
        # Tracking structures
        # --------------------------------------

        monitored_models = set()
        telemetry_counts = defaultdict(int)

        # --------------------------------------
        # Scan telemetry tables
        # --------------------------------------

        for r in llm_rows:

            model_id = r.get("model_id")

            if model_id:
                monitored_models.add(model_id)
                telemetry_counts[model_id] += 1

        for r in predictive_rows:

            model_id = r.get("model_id")

            if model_id:
                monitored_models.add(model_id)
                telemetry_counts[model_id] += 1

        for r in generative_rows:

            model_id = r.get("model_id")

            if model_id:
                monitored_models.add(model_id)
                telemetry_counts[model_id] += 1

        for r in agent_rows:

            model_id = r.get("model_id")

            if model_id:
                monitored_models.add(model_id)
                telemetry_counts[model_id] += 1

        # --------------------------------------
        # Build compliance records
        # --------------------------------------

        rows = []

        for model_id, meta in models.items():

            owner = meta.get("owner_team")

            monitored = model_id in monitored_models

            event_count = telemetry_counts.get(model_id, 0)

            compliance_status = "COMPLIANT"

            if not monitored:
                compliance_status = "NOT_MONITORED"

            elif event_count < 10:
                compliance_status = "LOW_OBSERVABILITY"

            rows.append({

                "model_id": model_id,
                "owner_team": owner,

                "telemetry_events": event_count,
                "is_monitored": monitored,

                "registry_registered": True,
                "compliance_status": compliance_status
            })

        # --------------------------------------
        # Write derived table
        # --------------------------------------

        self.bq.write_table(
            "analytics.compliance_audit_dashboard",
            rows
        )

        logger.info("Compliance transformation complete")


if __name__ == "__main__":
    ComplianceTransform().run()
