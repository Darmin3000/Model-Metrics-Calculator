# EMMS AI Metrics Transformation Pipeline

## Overview

This repository implements an Enterprise Model Monitoring System (EMMS)
metrics pipeline that converts raw telemetry and monitoring metrics into
audience‑specific analytics tables for executives, governance/compliance
teams, and engineering teams.

Raw telemetry signals are collected in BigQuery tables and transformed
by Python services into summarized tables that power dashboards and
monitoring tools.

Architecture:

Raw Telemetry Tables │ ▼ Metric Transform Services (Python) │ ▼ Audience
Analytics Tables │ ▼ Dashboards / Monitoring / Governance

------------------------------------------------------------------------

# Base Telemetry Tables

## agentic_metrics

Tracks autonomous agent performance.

  | Field                          | Type      | Description                          |
|--------------------------------|-----------|--------------------------------------|
| agent_id                       | STRING    | Unique agent run identifier          |
| model_id                       | STRING    | Registered model identifier          |
| model_version                  | STRING    | Model version                        |
| event_time                     | TIMESTAMP | Agent run time                       |
| goal_completion_time_seconds   | FLOAT     | Time to complete goal                |
| tool_execution_latency_seconds | FLOAT     | Average tool latency                 |
| goal_success_rate              | FLOAT     | LLM judged goal success              |
| error_recovery_rate            | FLOAT     | Fraction of recovered errors         |
| human_intervention_rate        | FLOAT     | Human override frequency             |
| unauthorized_action_attempts   | INTEGER   | Policy violating actions             |
| ingestion_time                 | TIMESTAMP | BigQuery ingestion timestamp         |


## predictive_metrics

 | Field               | Type      | Description                             |
|---------------------|-----------|-----------------------------------------|
| model_id            | STRING    | Model identifier                        |
| model_version       | STRING    | Model version                           |
| model_subtype       | STRING    | classification/regression/time_series   |
| event_time          | TIMESTAMP | Evaluation timestamp                    |
| accuracy            | FLOAT     | Classification accuracy                 |
| precision_score     | FLOAT     | Precision                               |
| recall_score        | FLOAT     | Recall                                  |
| log_loss            | FLOAT     | Log loss                                |
| brier_score         | FLOAT     | Calibration error                       |
| ece                 | FLOAT     | Expected calibration error              |
| mae                 | FLOAT     | Mean absolute error                     |
| rmse                | FLOAT     | Root mean squared error                 |
| r_squared           | FLOAT     | R² score                                |
| mape                | FLOAT     | Mean absolute percentage error          |
| drift_score         | FLOAT     | Dataset drift                           |
| feature_drift_ratio | FLOAT     | Fraction drifting features              |
| target_drift_score  | FLOAT     | Target drift                            |
| data_quality_score  | FLOAT     | Data quality metric                     |
| ingestion_time      | TIMESTAMP | Write timestamp                         |

## generative_metrics

  | Field               | Type      | Description                    |
|---------------------|-----------|--------------------------------|
| prediction_id       | STRING    | Evaluation identifier          |
| model_id            | STRING    | Model identifier               |
| model_version       | STRING    | Model version                  |
| event_time          | TIMESTAMP | Evaluation time                |
| hallucination_score | FLOAT     | Hallucination risk             |
| safety_score        | FLOAT     | Safety violation probability   |
| pii_leakage_score   | FLOAT     | PII leakage detection          |
| rag_precision       | FLOAT     | Retrieval precision            |
| rag_recall          | FLOAT     | Retrieval recall               |
| rag_freshness_days  | INTEGER   | Age of retrieved documents     |
| prompt_tokens       | INTEGER   | Input tokens                   |
| completion_tokens   | INTEGER   | Output tokens                  |
| tokens_per_second   | FLOAT     | Generation speed               |
| ingestion_time      | TIMESTAMP | Write time                     |

## emms_llm

  | Field             | Type      | Description               |
|-------------------|-----------|---------------------------|
| trace_id          | STRING    | Langfuse trace identifier |
| observation_id    | STRING    | Generation ID             |
| timestamp         | TIMESTAMP | Trace start time          |
| model_id          | STRING    | Registered model          |
| model_name        | STRING    | LLM model name            |
| trace_name        | STRING    | Operation name            |
| application       | STRING    | Calling service           |
| user_id           | STRING    | Masked user id            |
| prompt_tokens     | INTEGER   | Input tokens              |
| completion_tokens | INTEGER   | Output tokens             |
| total_tokens      | INTEGER   | Total tokens              |
| cost_usd          | FLOAT     | Estimated inference cost  |
| latency_ms        | FLOAT     | Response latency          |
| status            | STRING    | success / error           |
| level             | STRING    | Observation level         |
| metadata          | JSON      | Extra metadata            |
| ingestion_time    | TIMESTAMP | Write time                |

------------------------------------------------------------------------

# Derived Audience Tables

## Executive AI Summary (analytics.executive_ai_summary)

Answers executive questions: - How many models are healthy? - What is
our AI cost? - How much AI usage do we have?

  Field
  -------

| Field                    |
|--------------------------|
| model_id                 |
| request_volume           |
| monthly_cost_usd         |
| tokens_used              |
| avg_latency_ms           |
| success_rate             |
| avg_drift_score          |
| avg_hallucination_score  |
| avg_safety_score         |
| avg_agent_success_rate   |
| model_health_status      |

## Governance Summary (analytics.ai_governance_summary)

Answers compliance questions: - Which models violate policies? - Where
is drift occurring? - Where is PII risk present?

| Field                          |
|--------------------------------|
| model_id                       |
| model_version                  |
| avg_drift_score                |
| feature_drift_ratio            |
| target_drift_score             |
| avg_hallucination_score        |
| avg_safety_score               |
| pii_leakage_score              |
| rag_precision                  |
| rag_recall                     |
| rag_freshness_days             |
| error_recovery_rate            |
| unauthorized_action_attempts   |
| human_intervention_rate        |
| governance_status              |

## Engineering Metrics (analytics.ai_engineering_metrics)

Answers engineering questions: - Are models performing well? - Are
requests failing? - What is system latency and throughput?

| Field                         |
|-------------------------------|
| model_id                      |
| model_version                 |
| request_count                 |
| total_tokens                  |
| prompt_tokens                 |
| completion_tokens             |
| avg_latency_ms                |
| tokens_per_second             |
| goal_completion_time_seconds  |
| tool_execution_latency_seconds|
| status_success_rate           |
| error_rate                    |
| system_health_status          |

------------------------------------------------------------------------

# Transformation Pipeline

Each audience table is created by a dedicated Python transform service:

executive_transform.py governance_transform.py engineering_transform.py

The transformation process:

1.  Load base telemetry tables from BigQuery
2.  Aggregate metrics per model
3.  Compute derived metrics
4.  Apply business health logic
5.  Write results into analytics tables

Example transformation flow:

read_table("emms_llm") ↓ aggregate metrics ↓ compute averages ↓ apply
health logic ↓ write_table("analytics.executive_ai_summary")

------------------------------------------------------------------------

# Utilities

utils/logger.py Provides structured logging.

utils/bq_client.py Handles reading and writing BigQuery tables.

------------------------------------------------------------------------

# Outcome

The system converts raw AI telemetry into structured analytics tables
used by:

Executives → AI cost and health dashboards\
Compliance → safety and governance audits\
Engineering → performance and reliability monitoring
