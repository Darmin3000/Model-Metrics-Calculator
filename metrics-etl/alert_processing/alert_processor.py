"""
Alert Processor
"""

from utils.bq_client import BigQueryClient

class AlertProcessor:

    def __init__(self):
        self.bq = BigQueryClient()

    def run(self):

        predictive = self.bq.read_table("telemetry.predictive_metrics")

        alerts = []

        for r in predictive:

            drift = r.get("drift_score")

            if drift and drift > 0.4:

                alerts.append({

                    "model_id": r["model_id"],
                    "event_time": r["event_time"],
                    "alert_type": "DRIFT_DETECTED",
                    "severity": "HIGH"
                })

        self.bq.write_rows(
            "analytics.emms_alerts",
            alerts
        )
