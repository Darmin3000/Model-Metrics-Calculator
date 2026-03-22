"""
EMMS Drift Computation Job

Runs as a Kubernetes CronJob / Cloud Run Job. For each configured model:
1. Load reference data from GCS (parquet)
2. Load current data from BigQuery
3. Compute drift AND performance (Predictive AI metrics) using Evidently Report
4. Save report JSON to GCS at drift-reports/<model_id>_report.json
5. Notify the Evidently service to refresh its Prometheus metrics

UPDATED (2026-03-19): 
- Now loads training.csv and actuals.csv from GCS using service_name
- Path: gs://gcs-dev-use1-ai-storage-01/AIM_Monitoring/{service_name}/training.csv
- Path: gs://gcs-dev-use1-ai-storage-01/AIM_Monitoring/{service_name}/actuals.csv
- association_id_column is read from the 'config' JSON column in Cloud SQL
"""

import json
import logging
import os
import sys

import pandas as pd
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.cloud import bigquery, storage

from evidently import ColumnMapping
from evidently.metric_preset import (
    DataDriftPreset,
    DataQualityPreset,
    TargetDriftPreset,
    RegressionPreset,
    ClassificationPreset,
)
from evidently.metrics import PredictionStatsMetric
from evidently.report import Report

# ---------------------------------------------------------------------
# Configuration Imports
# Note: load_model_configs now fetches pointers from Cloud SQL 
# and hydrates ModelConfig objects from GCS JSON metadata.
# UPDATED: Now also includes service_name and association_id_column
# ---------------------------------------------------------------------
from config import (
    GCP_PROJECT,
    REFERENCE_DATA_BUCKET,
    ENVIRONMENT,
    VERTEX_LOCATION,
    ModelConfig,
    load_model_configs,
)

# ---------------------------------------------------------------------
# Env var alignment (BQ_DATASET with backward compatibility)
# ---------------------------------------------------------------------
BQ_DATASET = os.environ.get(
    "BQ_DATASET",
    os.environ.get("BIGQUERY_DATASET", "emms_analytics_dev"),
)

# ---------------------------------------------------------------------
# GCS Constants for new CSV-based training/actuals data
# ---------------------------------------------------------------------
GCS_BUCKET = "gcs-dev-use1-ai-storage-01"
GCS_PREFIX = "AIM_Monitoring"

# ---------------------------------------------------------------------
# Logging Configuration
# Preserving your exact format and verbosity levels.
# ---------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("EVIDENTLY_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("EMMS Predictive AI & Drift Computation Job")
logger.info("=" * 60)
logger.info(f"  Environment:     {ENVIRONMENT}")
logger.info(f"  GCP Project:     {GCP_PROJECT}")
logger.info(f"  Vertex Location: {VERTEX_LOCATION}")
logger.info(f"  BQ Dataset:      {BQ_DATASET}")
logger.info(f"  GCS Bucket:      {GCS_BUCKET}/{GCS_PREFIX}")


# ---------------------------------------------------------------------
# Data loading helpers - NEW GCS CSV version
# Preserving the local /tmp/ file handling and explicit path parsing style.
# ---------------------------------------------------------------------
def load_training_data(model_config: ModelConfig) -> pd.DataFrame:
    """
    Load training data from GCS using the new naming convention:
    gs://gcs-dev-use1-ai-storage-01/AIM_Monitoring/{service_name}/training.csv
    Downloads the blob to a local /tmp/ file before reading into pandas.
    """
    blob_path = f"{GCS_PREFIX}/{model_config.service_name}/training.csv"
    logger.info(f"  Downloading training data from gs://{GCS_BUCKET}/{blob_path}")

    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(blob_path)

    local_path = f"/tmp/training_{model_config.model_id}.csv"
    blob.download_to_filename(local_path)

    df = pd.read_csv(local_path)
    logger.info(
        f"  Loaded training data: {len(df)} rows, {len(df.columns)} columns"
    )
    return df


def load_actuals_data(model_config: ModelConfig) -> pd.DataFrame:
    """
    Load actuals data from GCS using the new naming convention:
    gs://gcs-dev-use1-ai-storage-01/AIM_Monitoring/{service_name}/actuals.csv
    Downloads the blob to a local /tmp/ file before reading into pandas.
    """
    blob_path = f"{GCS_PREFIX}/{model_config.service_name}/actuals.csv"
    logger.info(f"  Downloading actuals data from gs://{GCS_BUCKET}/{blob_path}")

    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(blob_path)

    local_path = f"/tmp/actuals_{model_config.model_id}.csv"
    blob.download_to_filename(local_path)

    df = pd.read_csv(local_path)
    logger.info(
        f"  Loaded actuals data: {len(df)} rows, {len(df.columns)} columns"
    )
    return df


def build_column_mapping(model_config: ModelConfig) -> ColumnMapping:
    """
    Build Evidently ColumnMapping from model configuration.
    Maps targets, predictions, and feature types for statistical tests.
    NEW: Also sets id_column using association_id_column from Cloud SQL config.
    """
    mapping = ColumnMapping()

    if model_config.target_col:
        mapping.target = model_config.target_col
    if model_config.prediction_col:
        mapping.prediction = model_config.prediction_col
    if model_config.association_id_column:
        mapping.id_column = model_config.association_id_column   # ← Critical for joining

    if model_config.numerical_features:
        mapping.numerical_features = model_config.numerical_features
    if model_config.categorical_features:
        mapping.categorical_features = model_config.categorical_features
    if model_config.text_features:
        mapping.text_features = model_config.text_features

    return mapping


# ---------------------------------------------------------------------
# Core computation
# Merged your original robustness with the new multi-model support.
# ---------------------------------------------------------------------
def compute_and_save(model_config: ModelConfig) -> bool:
    """
    Compute drift and performance for a single model and save to GCS.
    Dynamically switches between Regression and Classification presets.
    """
    model_id = model_config.model_id
    logger.info(f"Computing metrics for model: {model_id}")

    try:
        # 1. Fetch Data using new GCS CSV paths
        ref_data = load_training_data(model_config)
        cur_data = load_actuals_data(model_config)
        column_mapping = build_column_mapping(model_config)

        # 2. Base Metrics: Drift + Data Quality
        # drift_share_threshold is now dynamically loaded per model from GCS JSON
        metrics = [
            DataDriftPreset(drift_share=model_config.drift_share_threshold),
            DataQualityPreset(),
        ]

        # 3. Target Drift (Optional based on metadata)
        if model_config.target_col:
            metrics.append(TargetDriftPreset())

        # 4. Predictive AI performance
        # Using getattr for backward compatibility if model_subtype is missing
        model_subtype = getattr(model_config, "model_subtype", "regression").lower()

        if model_config.target_col and model_config.prediction_col:
            if model_subtype == "regression":
                metrics.append(RegressionPreset())
                logger.info(f"  Adding Regression metrics for {model_id}")
            elif model_subtype == "classification":
                metrics.append(ClassificationPreset())
                logger.info(f"  Adding Classification metrics for {model_id}")

        # 5. Stability & calibration (variance, brier, ece)
        metrics.append(PredictionStatsMetric())

        # 6. Run Evidently report
        report = Report(metrics=metrics)
        report.run(
            reference_data=ref_data,
            current_data=cur_data,
            column_mapping=column_mapping,
        )

        report_dict = report.as_dict()

        # 7. Persist report to GCS
        # Using REFERENCE_DATA_BUCKET as the destination for JSON reports
        if not REFERENCE_DATA_BUCKET:
            logger.error("REFERENCE_DATA_BUCKET not set — cannot save report")
            return False

        gcs_client = storage.Client()
        bucket = gcs_client.bucket(REFERENCE_DATA_BUCKET)
        blob_path = f"drift-reports/{model_id}_report.json"
        blob = bucket.blob(blob_path)

        # Use json.dumps with custom defaults to handle datetime/non-serializable types
        blob.upload_from_string(
            json.dumps(report_dict, indent=2, default=str),
            content_type="application/json",
        )

        logger.info(
            f"  Saved full predictive report to gs://{REFERENCE_DATA_BUCKET}/{blob_path}"
        )
        return True

    except Exception as e:
        logger.error(
            f"  Failed to compute metrics for {model_id}: {e}", exc_info=True
        )
        return False


# ---------------------------------------------------------------------
# Service notification (Cloud Run IAM–safe)
# Preserving your exact OIDC token fetching logic.
# ---------------------------------------------------------------------
def notify_service():
    """POST /refresh to the Evidently service (IAM-safe)."""
    service_url = os.environ.get("EVIDENTLY_SERVICE_URL")
    if not service_url:
        logger.warning(
            "EVIDENTLY_SERVICE_URL not set — skipping refresh notification"
        )
        return

    try:
        # Generate identity token for secure communication within Google Cloud
        token = id_token.fetch_id_token(Request(), service_url)
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.post(
            f"{service_url}/refresh",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("Notified Evidently service to refresh metrics")

    except Exception as e:
        logger.warning(f"Failed to notify Evidently service: {e}")


# ---------------------------------------------------------------------
# Entrypoint
# Preserving the exit codes and logging summaries.
# ---------------------------------------------------------------------
def main():
    # Load model configurations (Pointers from Cloud SQL -> Configs from GCS)
    configs = load_model_configs()
    
    if not configs:
        logger.info("No models configured — nothing to compute. Exiting cleanly.")
        sys.exit(0)

    logger.info(f"Computing metrics for {len(configs)} models")

    success = 0
    failed = 0

    # Iterate through each model configuration
    for config in configs:
        if compute_and_save(config):
            success += 1
        else:
            failed += 1

    logger.info(f"Completed: {success} succeeded, {failed} failed")

    # If any model was successful, notify the dashboard service to reload
    if success > 0:
        notify_service()

    # Exit with failure code if any models failed, allowing for automated retries
    if failed > 0:
        logger.warning(f"{failed} models failed computation")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
