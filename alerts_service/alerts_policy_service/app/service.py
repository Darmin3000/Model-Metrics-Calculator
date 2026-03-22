import logging

from config import DEFAULT_THRESHOLDS
from database import fetch_thresholds
from monitoring import (
    create_policy,
    ensure_pubsub_topic,
    ensure_notification_channel
)

PROJECT_ID = "your-project"

# 🔥 MUST MATCH ALERT ROUTER SUBSCRIPTION
ALERT_TOPIC = "ml-alerts-topic"

logging.basicConfig(level=logging.INFO)


def resolve_threshold(metric, db_thresholds):

    if metric in db_thresholds:
        return db_thresholds[metric]

    return DEFAULT_THRESHOLDS.get(metric)


def run():

    # ======================================================
    # STEP 1: Create / ensure PubSub topic
    # ======================================================
    topic_path = ensure_pubsub_topic(
        PROJECT_ID,
        ALERT_TOPIC
    )

    # ======================================================
    # STEP 2: Create Monitoring Notification Channel
    # ======================================================
    notification_channel = ensure_notification_channel(
        PROJECT_ID,
        topic_path
    )

    # ======================================================
    # STEP 3: Load thresholds from Cloud SQL
    # ======================================================
    models = fetch_thresholds()

    for model in models:

        model_id = model["model_id"]
        thresholds = model["thresholds"]

        metrics = set(DEFAULT_THRESHOLDS.keys()) | set(thresholds.keys())

        for metric in metrics:

            threshold = resolve_threshold(metric, thresholds)

            try:

                # ======================================================
                # STEP 4: Create alert policy → Pub/Sub
                # ======================================================
                create_policy(
                    PROJECT_ID,
                    model_id,
                    metric,
                    threshold,
                    notification_channel
                )

                logging.info(f"Policy created {model_id}:{metric}")

            except Exception as e:

                logging.error(f"Failed {model_id}:{metric} {e}")


if __name__ == "__main__":
    run()
