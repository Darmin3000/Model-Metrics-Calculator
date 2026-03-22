import base64
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

import functions_framework
import requests
from google.cloud import secretmanager
from sqlalchemy import create_engine, text

from teams_alerts import send_teams

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

alert_cache = {}
COOLDOWN_SECONDS = 600


# ==========================================================
# Secret Manager
# ==========================================================
def get_secret(secret_id: str, project_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


# ==========================================================
# Payload Normalization
# ==========================================================
def normalize_payload(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    version = str(raw_payload.get("version", ""))

    if version == "4":
        return raw_payload

    if version == "1.2":
        incident = raw_payload.get("incident", {})

        if incident.get("state") != "open":
            return {"version": "4", "alerts": []}

        user_labels = incident.get("policy_user_labels", {})
        alertname = user_labels.get("alertname") or incident.get(
            "condition_name", incident.get("policy_name", "UnknownAlert")
        )

        severity = user_labels.get("severity", "warning")
        category = user_labels.get("category", "platform")

        annotations = {}
        if incident.get("summary"):
            annotations["summary"] = incident["summary"]

        doc = incident.get("documentation", {})
        if doc.get("content"):
            annotations["description"] = doc["content"]

        for link in doc.get("links", []):
            if link.get("url"):
                annotations["runbook_url"] = link["url"]
                break

        if incident.get("url"):
            annotations["dashboard_url"] = incident["url"]

        starts_at = ""
        if incident.get("started_at"):
            starts_at = datetime.fromtimestamp(
                incident["started_at"], tz=timezone.utc
            ).isoformat()

        alert = {
            "status": "firing",
            "labels": {
                "alertname": alertname,
                "severity": severity,
                "category": category,
            },
            "annotations": annotations,
            "startsAt": starts_at,
        }

        return {
            "version": "4",
            "status": "firing",
            "groupLabels": {"alertname": alertname},
            "commonLabels": alert["labels"],
            "commonAnnotations": annotations,
            "alerts": [alert],
        }

    return raw_payload


# ==========================================================
# DB ENGINE
# ==========================================================
def get_engine():
    url = (
        f"postgresql+pg8000://{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASS')}@"
        f"{os.getenv('DB_HOST')}/"
        f"{os.getenv('DB_NAME')}"
    )
    return create_engine(url)


# ==========================================================
# CONTACTS (TEAMS ONLY)
# ==========================================================
def get_teams_contacts(model_id: str) -> List[str]:
    engine = get_engine()

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

    return list(set(webhooks))


# ==========================================================
# DEDUPLICATION
# ==========================================================
def is_duplicate(key: str) -> bool:
    now = time.time()

    if key in alert_cache:
        if now - alert_cache[key] < COOLDOWN_SECONDS:
            return True

    alert_cache[key] = now
    return False


# ==========================================================
# ENTRY POINT
# ==========================================================
@functions_framework.cloud_event
def handle_alert(cloud_event):

    project_id = os.environ.get("GCP_PROJECT")
    if not project_id:
        raise RuntimeError("Missing GCP_PROJECT environment variable")

    # Decode Pub/Sub message
    message_data = base64.b64decode(
        cloud_event.data["message"]["data"]
    ).decode()

    raw_payload = json.loads(message_data)
    payload = normalize_payload(raw_payload)

    firing_alerts = [
        a for a in payload.get("alerts", [])
        if a.get("status") == "firing"
    ]

    if not firing_alerts:
        logger.info("No firing alerts - skipping")
        return

    # Extract model_id and build alert (your logic)
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

    key = f"{model_id}:{metric}"

    if is_duplicate(key):
        logger.info(f"Duplicate alert suppressed for {key}")
        return

    # Get Teams webhooks from Cloud SQL (your logic)
    webhooks = get_teams_contacts(model_id)

    if not webhooks:
        logger.warning(f"No Teams contacts found for model {model_id}")
        return

    # Send alerts
    send_teams(alert, webhooks)

    logger.info(f"Teams alerts sent successfully for model {model_id}")
