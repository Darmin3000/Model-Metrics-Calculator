import smtplib
import time
import logging
import os
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

from google.cloud import bigquery
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


# ==============================================
# Secret Manager (SMTP CONFIG)
# ==============================================

def get_smtp_config():
    """
    Fetch SMTP credentials from GCP Secret Manager.
    Expects a JSON secret like:
    {
        "smtp_host": "...",
        "smtp_user": "...",
        "smtp_password": "...",
        "smtp_mail_from": "...",
        "smtp_port": "587",
        "smtp_starttls": "True",
        "smtp_ssl": "False"
    }
    """

    project_id = os.getenv("PROJECT_ID")
    secret_id = "emms-smtp-credentials"

    client = secretmanager.SecretManagerServiceClient()

    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"

    response = client.access_secret_version(name=name)

    secret_payload = response.payload.data.decode("UTF-8")

    return json.loads(secret_payload)


# ==============================================
# BigQuery Logging
# ==============================================

def log_email_alert(alert):

    table = os.getenv("BQ_ALERTS_TABLE")

    client = bigquery.Client()

    row = [{
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_id": alert["model_id"],
        "metric": alert["metric"],
        "value": float(alert["value"]),
        "severity": alert["severity"],
        "channel": "email"
    }]

    client.insert_rows_json(table, row)


# ==============================================
# Email Sender with Retry
# ==============================================

def send_email(alert, recipients):

    if not recipients:
        return

    # ---------------------------------------------
    # Load SMTP config from Secret Manager
    # ---------------------------------------------
    try:
        smtp_config = get_smtp_config()

        smtp_host = smtp_config.get("smtp_host")
        smtp_port = int(smtp_config.get("smtp_port", 587))
        smtp_user = smtp_config.get("smtp_user")
        smtp_pass = smtp_config.get("smtp_password")
        smtp_from = smtp_config.get("smtp_mail_from")

        use_tls = str(smtp_config.get("smtp_starttls", "True")).lower() == "true"
        use_ssl = str(smtp_config.get("smtp_ssl", "False")).lower() == "true"

    except Exception as e:
        logger.error(f"Failed to load SMTP config: {e}")
        return

    subject = f"[{alert['severity']}] Alert: {alert['metric']}"

    body = f"""
🚨 Model Alert 🚨

Model: {alert['model_id']}
Metric: {alert['metric']}
Value: {alert['value']:.2f}
Threshold: {alert.get('threshold', 'N/A')}

Severity: {alert['severity']}

Generated at: {datetime.now(timezone.utc).isoformat()}
"""

    for attempt in range(3):

        try:

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = smtp_from or smtp_user
            msg["To"] = ", ".join(recipients)

            msg.attach(MIMEText(body, "plain"))

            # ---------------------------------------------
            # SMTP Connection Handling
            # ---------------------------------------------
            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)

            with server:

                if use_tls:
                    server.starttls()

                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)

                server.sendmail(
                    msg["From"],
                    recipients,
                    msg.as_string()
                )

            log_email_alert(alert)

            logger.info(f"Email sent to {len(recipients)} recipients")

            return

        except Exception as e:

            logger.error(f"Email attempt {attempt} failed: {e}")
            time.sleep(2)
