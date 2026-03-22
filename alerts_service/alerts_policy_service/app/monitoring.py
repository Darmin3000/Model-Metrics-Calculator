from google.cloud import monitoring_v3
from google.cloud import pubsub_v1
from config import METRIC_MAP, METRIC_TYPES
from severity import get_severity

client = monitoring_v3.AlertPolicyServiceClient()
pubsub_client = pubsub_v1.PublisherClient()
channel_client = monitoring_v3.NotificationChannelServiceClient()


# ==========================================================
# PUBSUB
# ==========================================================

def ensure_pubsub_topic(project_id, topic_id):

    topic_path = pubsub_client.topic_path(project_id, topic_id)

    try:
        pubsub_client.get_topic(request={"topic": topic_path})
    except Exception:
        pubsub_client.create_topic(request={"name": topic_path})

    return topic_path


# ==========================================================
# NOTIFICATION CHANNEL
# ==========================================================

def ensure_notification_channel(project_id, topic_path):

    project_name = f"projects/{project_id}"

    channels = channel_client.list_notification_channels(name=project_name)

    for channel in channels:
        if channel.type == "pubsub" and channel.labels.get("topic") == topic_path:
            return channel.name

    new_channel = monitoring_v3.NotificationChannel(
        type="pubsub",
        display_name="ML Alerts PubSub Channel",
        labels={"topic": topic_path}
    )

    created = channel_client.create_notification_channel(
        name=project_name,
        notification_channel=new_channel
    )

    return created.name


# ==========================================================
# FILTER BUILDER (CRITICAL)
# ==========================================================

def build_filter(metric, model_id):

    prometheus_metric = METRIC_MAP.get(metric, metric)
    metric_type = METRIC_TYPES.get(prometheus_metric, "gauge")

    # QUALITY METRICS (accuracy, precision, etc.)
    if metric in ["accuracy", "precision", "recall"]:
        return f'''
        metric.type="prometheus.googleapis.com/{prometheus_metric}/{metric_type}"
        AND metric.label.model_id="{model_id}"
        AND metric.label.metric_name="{metric}"
        '''

    # TOKEN METRICS
    if metric in ["prompt_tokens", "completion_tokens"]:
        token_type = "prompt" if metric == "prompt_tokens" else "completion"
        return f'''
        metric.type="prometheus.googleapis.com/{prometheus_metric}/{metric_type}"
        AND metric.label.model_id="{model_id}"
        AND metric.label.token_type="{token_type}"
        '''

    # DEFAULT
    return f'''
    metric.type="prometheus.googleapis.com/{prometheus_metric}/{metric_type}"
    AND metric.label.model_id="{model_id}"
    '''


# ==========================================================
# CREATE POLICY
# ==========================================================

def create_policy(project_id, model_id, metric, threshold, channel):

    project_name = f"projects/{project_id}"

    severity = get_severity(metric)

    display_name = f"{model_id}_{metric}_{severity}_alert"

    filter_str = build_filter(metric, model_id)

    condition = monitoring_v3.AlertPolicy.Condition(
        display_name=f"{metric} threshold",
        condition_threshold=monitoring_v3.AlertPolicy.Condition.MetricThreshold(
            filter=filter_str,
            threshold_value=float(threshold),
            comparison=monitoring_v3.ComparisonType.COMPARISON_GT,
            duration={"seconds": 60}
        )
    )

    policy = monitoring_v3.AlertPolicy(
        display_name=display_name,
        combiner=monitoring_v3.AlertPolicy.ConditionCombinerType.OR,
        conditions=[condition],

        # 🔥 THIS IS THE PUBSUB CONNECTION
        notification_channels=[channel],

        enabled=True
    )

    client.create_alert_policy(
        name=project_name,
        alert_policy=policy
    )
