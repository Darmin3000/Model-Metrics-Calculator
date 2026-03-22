"""
Main evaluation pipeline.

This script:
1. Pulls recent traces from Langfuse
2. Runs evaluation metrics for:
      - Generative AI responses
      - Agentic workflows
3. Writes results to BigQuery
4. Sends scores back to Langfuse for observability

UPDATED: RAG ground truth now loaded from GCS (gs://gcs-dev-use1-ai-storage-01/AIM_Monitoring/{service_name}/training.csv)
service_name is fetched from Cloud SQL.
"""
import os
import logging
from datetime import datetime
import pandas as pd
from google.cloud import storage

from langfuse_reader import fetch_recent_traces
from evaluators.vertex_judge import VertexJudge
from evaluators.genai import evaluate_generative_metrics, DLPDetector
from evaluators.agentic import (
    goal_completion_time,
    tool_latency,
    error_recovery_rate,
    human_intervention_rate,
    unauthorized_actions,
)
from writers.bigquery_writer import BigQueryWriter
from writers.langfuse_scorer import LangfuseScorer
from cloudsql_reader import CloudSQLReader

from models import GenerativeMetricsResult, AgenticMetricsResult

ENVIRONMENT = os.environ.get("ENVIRONMENT", "unknown")
BQ_GENERATIVE_TABLE = os.environ.get("BQ_GENERATIVE_TABLE", "generative_metrics")
BQ_AGENTIC_TABLE = os.environ.get("BQ_AGENTIC_TABLE", "agentic_metrics")
GCS_BUCKET = "gcs-dev-use1-ai-storage-01"
GCS_PREFIX = "AIM_Monitoring"

logger = logging.getLogger(__name__)

def extract_metadata(trace: dict) -> dict:
    """
    Extract resource attributes (model.id, environment, team, region)
    to match the upstream SDK telemetry schema in data-schemas.md.
    """
    meta = trace.get("metadata", {}) or {}
    return {
        "model_id": meta.get("model.id") or meta.get("model_id") or trace.get("model", "unknown"),
        "model_version": meta.get("model.version") or trace.get("model_version"),
        "team_name": meta.get("team.name") or meta.get("team"),
        "gcp_region": meta.get("gcp.region") or meta.get("cloud.region"),
        "environment": meta.get("deployment.environment") or ENVIRONMENT,
    }

def load_training_csv(service_name: str) -> list[str]:
    """
    Load ground-truth documents from GCS: gs://gcs-dev-use1-ai-storage-01/AIM_Monitoring/{service_name}/training.csv
    Returns list of document_ids (assumes column 'document_id' or first column).
    """
    if not service_name or service_name == "unknown":
        logger.warning("No service_name – returning empty ground truth")
        return []

    blob_path = f"{GCS_PREFIX}/{service_name}/training.csv"
    logger.info(f"Loading training data from gs://{GCS_BUCKET}/{blob_path}")

    try:
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(blob_path)
        content = blob.download_as_bytes()
        df = pd.read_csv(pd.compat.BytesIO(content))
        # Use 'document_id' column if present, otherwise first column
        col = "document_id" if "document_id" in df.columns else df.columns[0]
        return df[col].astype(str).tolist()
    except Exception as e:
        logger.error(f"Failed to load training.csv for {service_name}: {e}")
        return []

def main():
    """
    Main execution function for the evaluation pipeline.
    """
    traces = fetch_recent_traces()
    vertex = VertexJudge()
    dlp = DLPDetector()
    bq = BigQueryWriter()
    scorer = LangfuseScorer()
    cloudsql = CloudSQLReader()

    generative_rows = []
    agentic_rows = []

    for trace in traces:
        trace_id = trace.get("id")
        if not trace_id:
            continue

        try:
            meta = extract_metadata(trace)
            model_id = meta["model_id"]

            # NEW: Get service_name from Cloud SQL to build GCS path
            service_name = cloudsql.get_service_name(model_id)

            request_time_str = trace.get("timestamp")
            request_time = datetime.fromisoformat(request_time_str.replace("Z", "+00:00")) if request_time_str else datetime.utcnow()

            usage = trace.get("usage", {}) or {}
            trace_type = trace.get("type")

            # =====================================================
            # GENERATIVE AI TRACE EVALUATION
            # =====================================================
            if trace_type == "generative":
                ground_truth_docs = load_training_csv(service_name)

                metrics = evaluate_generative_metrics(
                    prompt=trace.get("input", ""),
                    response=trace.get("output", ""),
                    retrieved_docs=trace.get("retrieved_docs", []),
                    ground_truth_docs=ground_truth_docs,
                    vertex=vertex,
                    dlp=dlp,
                )

                for name, value in [
                    ("hallucination_score", metrics["hallucination_score"]),
                    ("safety_score", metrics["safety_score"]),
                    ("pii_leakage_score", metrics["pii_leakage_score"]),
                ]:
                    scorer.score(trace_id, name, value, timestamp=request_time)

                if metrics.get("rag_precision") is not None:
                    scorer.score(trace_id, "rag_precision", metrics["rag_precision"], timestamp=request_time)
                if metrics.get("rag_recall") is not None:
                    scorer.score(trace_id, "rag_recall", metrics["rag_recall"], timestamp=request_time)

                generative_rows.append(
                    GenerativeMetricsResult(
                        model_id=model_id,
                        trace_id=trace_id,
                        request_time=request_time,
                        environment=meta["environment"],
                        team_name=meta["team_name"],
                        gcp_region=meta["gcp_region"],
                        hallucination_score=metrics["hallucination_score"],
                        safety_score=metrics["safety_score"],
                        pii_leakage_score=metrics["pii_leakage_score"],
                        prompt_tokens=usage.get("prompt_tokens"),
                        completion_tokens=usage.get("completion_tokens"),
                        total_tokens=usage.get("total_tokens"),
                        rag_precision=metrics.get("rag_precision"),
                        rag_recall=metrics.get("rag_recall"),
                    ).model_dump()
                )
                logger.info(f"Processed generative trace {trace_id} for {model_id} (service: {service_name})")

            # =====================================================
            # AGENTIC TRACE EVALUATION
            # =====================================================
            elif trace_type == "agentic":
                events = trace.get("events", [])
                success = vertex.judge_agent_goal(str(events), trace.get("policy", ""))

                scorer.score(trace_id, "goal_success_rate", success, timestamp=request_time)

                agentic_rows.append(
                    AgenticMetricsResult(
                        model_id=model_id,
                        trace_id=trace_id,
                        request_time=request_time,
                        environment=meta["environment"],
                        team_name=meta["team_name"],
                        gcp_region=meta["gcp_region"],
                        goal_completion_time_seconds=goal_completion_time(events),
                        goal_success_rate=success,
                        tool_execution_latency_seconds=tool_latency(events),
                        error_recovery_rate=error_recovery_rate(events),
                        human_intervention_rate=human_intervention_rate(events),
                        unauthorized_action_attempts=unauthorized_actions(events),
                        model_version=meta["model_version"],
                        ingestion_time=datetime.utcnow(),
                    ).model_dump()
                )
                logger.info(f"Processed agentic trace {trace_id} for {model_id}")

        except Exception as e:
            logger.error(f"Failed to process trace {trace_id}: {str(e)}", exc_info=True)
            try:
                scorer.score(trace_id, "eval_error", 1.0, timestamp=datetime.utcnow())
            except:
                pass

    if generative_rows:
        bq.write(BQ_GENERATIVE_TABLE, generative_rows)
    if agentic_rows:
        bq.write(BQ_AGENTIC_TABLE, agentic_rows)

    scorer.flush()
    logger.info("Evaluation pipeline completed successfully")

if __name__ == "__main__":
    main()
