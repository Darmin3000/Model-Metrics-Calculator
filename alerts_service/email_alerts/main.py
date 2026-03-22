import base64
import json
import logging
import os
import time

from sqlalchemy import create_engine, text

from email_alerts import send_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

alert_cache = {}
COOLDOWN_SECONDS = 600


# ==============================================
# DB
# ==============================================

def get_engine():
    url = (
        f"postgresql+pg8000://{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASS')}@"
        f"{os.getenv('DB_HOST')}/"
        f"{os.getenv('DB_NAME')}"
    )
    return create_engine(url)


# ==============================================
# CONTACTS (EMAIL ONLY)
# ==============================================

def get_email_contacts(model_id):

    if not model_id:
        return []

    engine = get_engine()

    query = text("""
        SELECT alert_contacts
        FROM model_notifications
        WHERE model_id = :model_id
        AND LOWER(alert_method) = 'email'
    """)

    with engine.connect() as conn:
        rows = conn.execute(query, {"model_id": model_id}).fetchall()

    emails = []

    for (contacts,) in rows:
        if contacts:
            emails.extend([c.strip() for c in contacts.split(",")])

    return list(set(emails))


# ==============================================
# DEDUPLICATIOM
# ==============================================

def is_duplicate(key):

    now = time.time()

    if key in alert_cache:
        if now - alert_cache[key] < COOLDOWN_SECONDS:
            return True

    alert_cache[key] = now
    return False


# ==============================================
# ENTRYPOINT (Pub/Sub Trigger)
# ==============================================

def handle_alert(event, context):

    try:
        payload = json.loads(
            base64.b64decode(event["data"]).decode()
        )
    except Exception as e:
        logger.error(f"Failed to decode Pub/Sub message: {e}")
        return

    incident = payload.get("incident", {})

    metric_type = incident.get("metric", {}).get("type", "")
    metric = metric_type.split("/")[-1]

    model_id = incident.get("metric", {}).get("labels", {}).get("model_id")

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
        logger.info("Duplicate alert suppressed")
        return

    emails = get_email_contacts(model_id)

    if not emails:
        logger.info(f"No email recipients for model {model_id}")
        return

    send_email(alert, emails)

    logger.info("Email alert processed")


if __name__ == "__main__":
    logger.info("Email alert service running")
