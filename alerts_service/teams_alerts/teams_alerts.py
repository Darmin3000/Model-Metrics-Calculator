import base64
import json
import logging
import os
import requests
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

import functions_framework
from google.cloud import bigquery
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================================
# BigQuery Logging
# ==========================================================

def write_to_bigquery(alert_data: dict):
    """
    Logs the alert to BigQuery (matches the original teams_alerts_original.py pattern).
    """
    table_id = os.getenv("BQ_ALERTS_TABLE")
    if not table_id:
        logger.warning("BQ_ALERTS_TABLE not set - skipping BigQuery log")
        return

    client = bigquery.Client()

    row_to_insert = [{
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_id": alert_data.get("model_id"),
        "metric": alert_data.get("metric"),
        "value": float(alert_data.get("value", 0)),
        "severity": alert_data.get("severity"),
        "channel": "teams"
    }]

    errors = client.insert_rows_json(table_id, row_to_insert)
    if errors:
        logger.error(f"BigQuery insert failed: {errors}")
    else:
        logger.info("Alert logged to BigQuery")


# ==========================================================
# ENTRY POINT
# ==========================================================

@functions_framework.cloud_event
def handle_teams_alert(cloud_event):
    """
    Cloud Function entry point for processing Teams alerts.
    """
    try:
        # Decode Pub/Sub message
        data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        payload = json.loads(data)

        # Extract alert details (your original logic)
        incident = payload.get("incident", {}) if "incident" in payload else payload
        metric_type = incident.get("metric", {}).get("type", "")
        metric = metric_type.split("/")[-1] if metric_type else "unknown"

        model_id = incident.get("metric", {}).get("labels", {}).get("model_id")

        if not model_id:
            logger.warning("No model_id found in alert - skipping")
            return

        policy_name = incident.get("policy_name", "").lower()

        severity = "LOW"
        if "critical" in policy_name:
            severity = "CRITICAL"
        elif "high" in policy_name:
            severity = "HIGH"
        elif "medium" in policy_name:
            severity = "MEDIUM"

        alert = {
            "model_id": model_id,
            "metric": metric,
            "value": incident.get("metric_value", 0),
            "threshold": incident.get("metric_threshold", 0),
            "severity": severity
        }

        # Get Teams webhooks from Cloud SQL (your improved multi-webhook logic)
        db_url = f"postgresql+pg8000://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
        engine = create_engine(db_url)

        query = text("""
            SELECT alert_contacts
            FROM model_notifications
            WHERE model_id = :model_id
            AND LOWER(alert_method) = 'microsoft teams'
        """)

        with engine.connect() as conn:
            rows = conn.execute(query, {"model_id": model_id}).fetchall()

        webhooks = []
        for (contacts,) in rows:
            if contacts:
                webhooks.extend([c.strip() for c in contacts.split(",")])

        webhooks = list(set(webhooks))

        if not webhooks:
            logger.warning(f"No Teams contacts found for model {model_id}")
            return

        # Build Adaptive Card
        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"🚨 Alert: {alert.get('metric', 'Unknown')}",
                            "weight": "Bolder",
                            "size": "Large"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Model: {alert.get('model_id', 'Unknown')}"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Severity: {alert.get('severity', 'LOW')}"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Value: {alert.get('value', 0)}"
                        }
                    ]
                }
            }]
        }

        # Send to all webhooks with retry
        for webhook in webhooks:
            for attempt in range(3):
                try:
                    response = requests.post(
                        webhook,
                        json=card,
                        timeout=10
                    )
                    response.raise_for_status()

                    # Log to BigQuery after successful send
                    write_to_bigquery(alert)

                    logger.info(f"Teams alert sent successfully to webhook (attempt {attempt+1})")
                    break

                except Exception as e:
                    logger.error(f"Teams send failed (attempt {attempt+1}/3): {e}")
                    if attempt < 2:
                        time.sleep(2 ** attempt)  # exponential backoff
                    else:
                        logger.error(f"Teams alert permanently failed for webhook: {webhook}")

        logger.info(f"Teams alerts processed successfully for model {model_id}")

    except Exception as e:
        logger.error(f"Teams alert handler failure: {e}")
