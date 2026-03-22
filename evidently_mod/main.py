"""
EMMS Evidently Service

Reads drift computation results from GCS and exposes them as Prometheus metrics.
The heavy drift computation is done by compute_drift.py running as a Cloud Run Job.
This service is lightweight — it only reads JSON and serves metrics.
"""

import json
import logging
import os
import time
import threading
from typing import Dict, Any

from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    Counter,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from google.cloud import storage
from google.oauth2 import id_token
from google.auth.transport.requests import Request as GoogleAuthRequest

from config import (
    load_model_configs,
    REFERENCE_DATA_BUCKET,
    ENVIRONMENT,
    VERTEX_LOCATION,
)

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("EVIDENTLY_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logger.info(
    f"Starting EMMS Evidently Service | "
    f"env={ENVIRONMENT} | vertex_location={VERTEX_LOCATION}"
)

# ---------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------
app = FastAPI(title="EMMS Evidently Service", version="2.0.0")

# ---------------------------------------------------------------------
# Prometheus registry
# ---------------------------------------------------------------------
registry = CollectorRegistry()

# --- 1. Dataset & Feature Drift ---
dataset_drift_share = Gauge(
    "emms_dataset_drift_share",
    "Share of drifting features in the dataset",
    ["model_id"],
    registry=registry,
)

dataset_drift_detected = Gauge(
    "emms_dataset_drift_detected",
    "1 if dataset drift is detected, 0 otherwise",
    ["model_id"],
    registry=registry,
)

feature_drift_score = Gauge(
    "emms_feature_drift_score",
    "Drift score (statistical distance) for a specific feature",
    ["model_id", "feature", "method"],
    registry=registry,
)

feature_drift_detected = Gauge(
    "emms_feature_drift_detected",
    "1 if feature drift detected, 0 otherwise",
    ["model_id", "feature"],
    registry=registry,
)

target_drift_score = Gauge(
    "emms_target_drift_score",
    "Drift score for the target column",
    ["model_id", "method"],
    registry=registry,
)

prediction_drift_score = Gauge(
    "emms_prediction_drift_score",
    "Drift score for the prediction column",
    ["model_id", "method"],
    registry=registry,
)

feature_drift_ratio = Gauge(
    "emms_feature_drift_ratio",
    "Ratio of features showing significant drift",
    ["model_id"],
    registry=registry,
)

max_feature_drift = Gauge(
    "emms_max_feature_drift",
    "Highest drift score among all features",
    ["model_id"],
    registry=registry,
)

avg_feature_drift = Gauge(
    "emms_avg_feature_drift",
    "Mean drift score across all features",
    ["model_id"],
    registry=registry,
)

# --- 2. Regression Metrics ---
regression_mae = Gauge("emms_regression_mae", "Mean Absolute Error", ["model_id"], registry=registry)
regression_rmse = Gauge("emms_regression_rmse", "Root Mean Squared Error", ["model_id"], registry=registry)
regression_r_squared = Gauge("emms_regression_r_squared", "R-squared value", ["model_id"], registry=registry)
regression_mean_error = Gauge("emms_regression_mean_error", "Mean Error", ["model_id"], registry=registry)
regression_error_stddev = Gauge("emms_regression_error_stddev", "Error std dev", ["model_id"], registry=registry)

# --- 3. Classification Metrics ---
classification_accuracy = Gauge("emms_classification_accuracy", "Accuracy", ["model_id"], registry=registry)
classification_precision = Gauge("emms_classification_precision", "Precision", ["model_id"], registry=registry)
classification_recall = Gauge("emms_classification_recall", "Recall", ["model_id"], registry=registry)
classification_log_loss = Gauge("emms_classification_log_loss", "Log loss", ["model_id"], registry=registry)
classification_brier_score = Gauge("emms_classification_brier_score", "Brier score", ["model_id"], registry=registry)
classification_ece = Gauge("emms_classification_ece", "Expected calibration error", ["model_id"], registry=registry)

# --- 4. Stability / Health ---
prediction_variance = Gauge("emms_prediction_variance", "Prediction variance", ["model_id"], registry=registry)
missing_prediction_rate = Gauge("emms_missing_prediction_rate", "Missing prediction rate", ["model_id"], registry=registry)
data_quality_score = Gauge("emms_data_quality_score", "Data quality score", ["model_id"], registry=registry)

missing_values_share = Gauge(
    "emms_data_quality_missing_share",
    "Share of missing values",
    ["model_id"],
    registry=registry,
)

# --- 5. Operational ---
drift_report_timestamp = Gauge(
    "emms_drift_report_timestamp",
    "Unix timestamp of latest drift report",
    ["model_id"],
    registry=registry,
)

drift_refresh_total = Counter(
    "emms_drift_refresh_total",
    "Total metric refresh attempts",
    ["status"],
    registry=registry,
)

service_up = Gauge("emms_evidently_up", "Service health", registry=registry)
service_up.set(1)

models_monitored = Gauge(
    "emms_models_monitored",
    "Number of models with drift reports",
    registry=registry,
)

# ---------------------------------------------------------------------
# State
# ---------------------------------------------------------------------
latest_reports: Dict[str, Any] = {}
gcs_client = None


def get_gcs_client():
    global gcs_client
    if gcs_client is None:
        gcs_client = storage.Client()
    return gcs_client


# ---------------------------------------------------------------------
# IAM verification (Cloud Run safe)
# ---------------------------------------------------------------------
def verify_request(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header.split(" ", 1)[1]
    audience = os.environ.get("SERVICE_URL")

    try:
        id_token.verify_oauth2_token(
            token,
            GoogleAuthRequest(),
            audience=audience,
        )
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid identity token")


# ---------------------------------------------------------------------
# Report parsing
# ---------------------------------------------------------------------
def parse_evidently_report(model_id: str, report_data: dict):
    metrics = report_data.get("metrics", [])

    for metric in metrics:
        metric_type = metric.get("metric")
        result = metric.get("result", {})

        try:
            if metric_type == "DatasetDriftMetric":
                share = result.get("drift_share", 0.0)
                dataset_drift_share.labels(model_id).set(share)
                dataset_drift_detected.labels(model_id).set(
                    1 if result.get("dataset_drift") else 0
                )
                feature_drift_ratio.labels(model_id).set(share)

                drift_cols = result.get("drift_by_columns", {})
                scores = [v.get("drift_score", 0) for v in drift_cols.values()]
                if scores:
                    max_feature_drift.labels(model_id).set(max(scores))
                    avg_feature_drift.labels(model_id).set(sum(scores) / len(scores))

            elif metric_type == "ColumnDriftMetric":
                col = result.get("column_name")
                method = result.get("stattest_name", "unknown")
                score = result.get("drift_score", 0.0)
                drifted = result.get("drift_detected", False)
                col_type = result.get("column_type")

                if col_type == "target":
                    target_drift_score.labels(model_id, method).set(score)
                elif col_type == "prediction":
                    prediction_drift_score.labels(model_id, method).set(score)
                else:
                    feature_drift_score.labels(model_id, col, method).set(score)
                    feature_drift_detected.labels(model_id, col).set(1 if drifted else 0)

            elif metric_type == "RegressionQualityMetric":
                cur = result.get("current", {})
                regression_mae.labels(model_id).set(cur.get("mean_abs_error", 0.0))
                regression_rmse.labels(model_id).set(cur.get("rmse", 0.0))
                regression_r_squared.labels(model_id).set(cur.get("r2_score", 0.0))
                regression_mean_error.labels(model_id).set(cur.get("mean_error", 0.0))
                regression_error_stddev.labels(model_id).set(cur.get("error_std", 0.0))

            elif metric_type == "ClassificationQualityMetric":
                cur = result.get("current", {})
                classification_accuracy.labels(model_id).set(cur.get("accuracy", 0.0))
                classification_precision.labels(model_id).set(cur.get("precision", 0.0))
                classification_recall.labels(model_id).set(cur.get("recall", 0.0))
                classification_log_loss.labels(model_id).set(cur.get("log_loss", 0.0))

            elif metric_type == "PredictionStatsMetric":
                cur = result.get("current", {})
                std = cur.get("std")
                if std is not None:
                    prediction_variance.labels(model_id).set(std ** 2)
                if "brier_score" in cur:
                    classification_brier_score.labels(model_id).set(cur.get("brier_score", 0.0))
                if "ece" in cur:
                    classification_ece.labels(model_id).set(cur.get("ece", 0.0))

            elif metric_type == "DatasetMissingValuesMetric":
                cur = result.get("current", {})
                share = cur.get("share_of_missing_values", 0.0)
                missing_values_share.labels(model_id).set(share)
                missing_prediction_rate.labels(model_id).set(share)
                data_quality_score.labels(model_id).set(1.0 - share)

        except Exception as e:
            logger.error(f"Error parsing {metric_type} for {model_id}: {e}")


# ---------------------------------------------------------------------
# Refresh logic
# ---------------------------------------------------------------------
def refresh_metrics():
    if not REFERENCE_DATA_BUCKET:
        return

    try:
        bucket = get_gcs_client().bucket(REFERENCE_DATA_BUCKET)
        blobs = bucket.list_blobs(prefix="drift-reports/")
        count = 0

        for blob in blobs:
            if not blob.name.endswith("_report.json"):
                continue

            report = json.loads(blob.download_as_text())
            model_id = blob.name.split("/")[-1].replace("_report.json", "")
            parse_evidently_report(model_id, report)

            drift_report_timestamp.labels(model_id).set(
                blob.updated.timestamp() if blob.updated else time.time()
            )

            latest_reports[model_id] = {
                "report": report,
                "updated_at": blob.updated.isoformat() if blob.updated else None,
            }
            count += 1

        models_monitored.set(count)
        drift_refresh_total.labels("success").inc()

    except Exception as e:
        drift_refresh_total.labels("error").inc()
        logger.error(f"Refresh failed: {e}")


def periodic_refresh(interval: int):
    while True:
        refresh_metrics()
        time.sleep(interval)


# ---------------------------------------------------------------------
# FastAPI lifecycle & endpoints
# ---------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    configs = load_model_configs()
    logger.info(f"Service started with {len(configs)} configured models")

    refresh_metrics()
    interval = int(os.environ.get("REFRESH_INTERVAL_SECONDS", "300"))
    threading.Thread(target=periodic_refresh, args=(interval,), daemon=True).start()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "environment": ENVIRONMENT,
        "models_monitored": len(latest_reports),
    }


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.post("/refresh")
async def trigger_refresh(request: Request, background_tasks: BackgroundTasks):
    verify_request(request)
    background_tasks.add_task(refresh_metrics)
    return {"status": "refresh_triggered"}


@app.get("/api/v1/drift-reports")
async def list_reports():
    return {
        m: {
            "updated_at": d["updated_at"],
            "drift_detected": any(
                x.get("result", {}).get("dataset_drift", False)
                for x in d["report"].get("metrics", [])
                if x.get("metric") == "DatasetDriftMetric"
            ),
        }
        for m, d in latest_reports.items()
    }


@app.get("/api/v1/drift-reports/{model_id}")
async def get_report(model_id: str):
    if model_id not in latest_reports:
        return JSONResponse(status_code=404, content={"status": "not_found"})
    return latest_reports[model_id]
