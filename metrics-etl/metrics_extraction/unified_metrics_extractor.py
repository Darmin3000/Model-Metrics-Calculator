"""
Unified Metric Extractor
"""

from utils.bq_client import BigQueryClient
from utils.logger import get_logger
from config.metric_registry import *

logger = get_logger("metric_extractor")

class UnifiedMetricExtractor:

    def __init__(self):
        self.bq = BigQueryClient()

    def normalize_metrics(self, rows, metrics, category):

        normalized = []

        for r in rows:

            for m in metrics:

                if r.get(m) is None:
                    continue

                normalized.append({

                    "model_id": r["model_id"],
                    "model_version": r.get("model_version"),

                    "metric_name": m,
                    "metric_value": float(r[m]),

                    "metric_category": category,

                    "event_time": r["event_time"]
                })

        return normalized

    def run(self):

        unified = []

        predictive = self.bq.read_table("telemetry.predictive_metrics")
        unified += self.normalize_metrics(
            predictive,
            PREDICTIVE_METRICS,
            "predictive"
        )

        generative = self.bq.read_table("telemetry.generative_metrics")
        unified += self.normalize_metrics(
            generative,
            GENERATIVE_METRICS,
            "generative"
        )

        agentic = self.bq.read_table("telemetry.agentic_metrics")
        unified += self.normalize_metrics(
            agentic,
            AGENTIC_METRICS,
            "agentic"
        )

        self.bq.write_rows(
            "analytics.unified_model_metrics",
            unified
        )

        logger.info(f"{len(unified)} metrics normalized")
