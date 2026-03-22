# Project Documentation

This repository contains the documentation for four core systems used in AI/ML operations and monitoring:

1. *Alerting System** – Email and Microsoft Teams notifications for monitoring alerts
2. *LLM Evaluation Pipeline** – Evaluation for Generative AI and Agentic AI systems using observability and LLM-as-a-judge
3. *Predictive Metrics (EMMS)** – Drift and performance monitoring for predictive models
4. *EMMS Analytics ETL Pipeline** – Data transformation for executive, model owner, and compliance dashboards

---

## 1. Alerting System – Email and Microsoft Teams

### OverviewThis repository implements a cloud-based alerting system that processes monitoring alerts and routes them to Microsoft Teams and Email (SMTP)It is designed to run as Google Cloud Functions triggered by Pub/Sub messages

The system also:
*Logs alert activity to BigQuery
*Dynamically routes alerts using PostgreSQL configuration
*Supports multiple alert formats
*Uses Google Secret Manager for credentials

### High-Level Architecture
```text
Monitoring System
        │
        │ (Alert Payload)
        ▼
     Pub/Sub
        │
        ▼
  Google Cloud Function
        │
        ├──────────► Teams Alert
        │              │
        │              ▼
        │        Microsoft Teams
        │
        └──────────► Email Alert
                       │
                       ▼
                    SMTP Server
                       │
                       ▼
                     Email
```

**Additional Components:**
* **BigQuery**: Alert Logging.
* **PostgreSQL**: Routing Config.
* **Secret Manager**: Credentials.

### Files in the Repository
| File | Purpose |
| :--- | :--- |
| `main.py` | Primary alert processing system. |
| `teams_alerts.py` | Teams alert handler with DB routing. |
| `email_alerts.py` | Email alert handler with DB routing. |

### Alert Data Flow
1.  **Step 1 — Alert Generated**: Monitoring system (e.g., Prometheus Alertmanager, GCP Monitoring, Custom ML system) emits an alert.
2.  **Step 2 — Alert Published to Pub/Sub**: Alert payload is sent as base64 encoded JSON.
3.  **Step 3 — Cloud Function Triggered**: Cloud function receives a `CloudEvent` containing the message data.
4.  **Step 4 — Payload Decoded**: The function performs base64 to JSON conversion.
5.  **Step 5 — Payload Normalized**: Different alert formats are converted into a common Alertmanager v4 schema.
6.  **Step 6 — Alert Processing**: The system performs filtering (only firing alerts), logging to BigQuery, routing, and notification delivery.

### Input Data Formats
#### Primary Input Format (Alertmanager v4)
```json
{
  "version": "4",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "ModelDrift",
        "severity": "critical",
        "category": "ml"
      },
      "annotations": {
        "summary": "Model drift detected",
        "description": "Drift score exceeded threshold",
        "runbook_url": "[https://runbook.link](https://runbook.link)",
        "dashboard_url": "[https://dashboard.link](https://dashboard.link)"
      },
      "startsAt": "2026-01-01T10:00:00Z"
    }
  ]
}
```

#### Legacy Format (Version 1.2)
Legacy formats are automatically converted to version 4.
```json
{
  "version": "1.2",
  "incident": {
    "state": "open",
    "policy_name": "Model Drift Policy",
    "condition_name": "Drift threshold",
    "summary": "Drift detected",
    "started_at": 1710000000,
    "policy_user_labels": {
      "alertname": "ModelDrift",
      "severity": "critical"
    }
  }
}
```

### Output Formats
#### Microsoft Teams (Adaptive Card)
```json
{
 "type": "message",
 "attachments": [
   {
     "contentType": "application/vnd.microsoft.card.adaptive",
     "content": {
       "type": "AdaptiveCard",
       "version": "1.4",
       "body": [
         {
           "type": "TextBlock",
           "text": "Model Drift",
           "size": "Large"
         }
       ]
     }
   }
 ]
}
```

#### Email Output (HTML)
```html
<h2>🚨 Model Drift</h2>
<p><strong>Severity:</strong> critical</p>
<p>Model drift detected</p>
<p>Drift score exceeded threshold</p>
```

### Configuration
#### Environment Variables
| Variable | Description |
| :--- | :--- |
| `GCP_PROJECT` | GCP Project ID. |
| `SMTP_HOST` | SMTP server. |
| `SMTP_PORT` | SMTP port. |
| `OUTLOOK_SENDER_EMAIL` | Sender email. |
| `OUTLOOK_APP_PASSWORD` | SMTP password. |
| `BQ_ALERTS_TABLE` | BigQuery table. |
| `DB_USER` | PostgreSQL user. |
| `DB_PASS` | PostgreSQL password. |
| `DB_HOST` | PostgreSQL host. |
| `DB_NAME` | PostgreSQL database. |

#### Secret Manager Secrets
| Secret | Purpose |
| :--- | :--- |
| `emms-teams-webhook-url` | Teams webhook URL. |
| `smtp-username` | SMTP username. |
| `smtp-password` | SMTP password. |

### Detailed Code Documentation: `main.py`
**Purpose**: Main engine for alert processing, normalization, and routing.
* **Imports**: Uses `base64`, `json`, `logging`, `os`, and `smtplib` for decoding and delivery.
* **Secret Management**: `def get_secret(secret_id, project_id)` retrieves secrets from Google Secret Manager.
* **Normalization**: `normalize_payload()` converts version 1.2 or 4 formats into a standard structure.
* **Teams Integration**: `format_teams_card()` creates the JSON for Adaptive Cards, mapping severity to colors (critical: attention, warning: warning, info: accent).
* **Email Logic**: `get_recipients()` determines the target list (defaulting to `mlops-team@bhsf.com` or `mlops-oncall@bhsf.com` for critical alerts).
* **Entry Point**: `handle_alert(cloud_event)` manages the full processing lifecycle from decoding to logging success.

---


# 2. LLM Evaluation Pipeline  
## Generative AI and Agentic AI Observability System

This repository implements a **production-style evaluation pipeline for Large Language Model (LLM) systems**.

It evaluates both:

- **Generative AI responses**
- **Agentic AI workflows**

The system collects traces from **Langfuse**, computes evaluation metrics using **Vertex AI** and **Google Cloud DLP**, and writes results to **BigQuery** and the **Langfuse REST API**.

---

# 1. System Overview

Modern AI systems require **continuous monitoring and evaluation**.

This pipeline provides automated evaluation of:

## Generative AI Systems

Examples:

- RAG chatbots
- Document QA systems
- AI assistants

Metrics evaluated:

- Hallucination detection
- Safety policy violations
- PII leakage detection
- RAG retrieval quality

---

## Agentic AI Systems

Examples:

- Autonomous task agents
- Tool-using assistants
- Workflow automation agents

Metrics evaluated:

- Goal completion
- Tool latency
- Error recovery
- Human intervention rate
- Unauthorized actions

---

# 2. Architecture

The system integrates several components.

```
Langfuse
   │
   │ traces
   ▼
Trace Fetcher
(langfuse_reader.py)
   │
   ▼
Evaluation Engine
(main.py)
   │
   ├── Generative Evaluator
   │      (genai.py)
   │
   ├── Agentic Evaluator
   │      (agentic.py)
   │
   └── LLM Judge
          (vertex_judge.py)
   │
   ▼
BigQuery Writer
(writers/bigquery_writer.py)

   │
   ▼
Langfuse Scoring
(writers/langfuse_scorer.py)
```

### External Services Used

- **Langfuse** → Trace observability
- **Vertex AI** → LLM judging
- **Google Cloud DLP** → PII detection
- **BigQuery** → Analytics storage

---

# 3. Pipeline Workflow

The system executes the following pipeline.

## Step 1 — Fetch Recent Traces

```python
langfuse_reader.fetch_recent_traces()
```

---

## Step 2 — Determine Trace Type

For each trace:

```python
trace["type"]
```

Possible values:

```
generative
agentic
```

---

## Step 3 — Run Evaluation Metrics

### Generative Traces

```python
evaluate_generative_metrics()
```

### Agentic Traces

```
goal_completion_time()
tool_latency()
error_recovery_rate()
human_intervention_rate()
unauthorized_actions()
```

---

## Step 4 — Send Scores to Langfuse

```python
LangfuseScorer.score()
```

---

## Step 5 — Store Results in BigQuery

Tables written:

```
generative_metrics
agentic_metrics
```

---

# 4. Project Structure

```
project/
│
├── main.py
│
├── models.py
│
├── langfuse_reader.py
│
├── evaluators/
│   ├── genai.py
│   ├── agentic.py
│   └── vertex_judge.py
│
├── writers/
│   ├── bigquery_writer.py
│   └── langfuse_scorer.py
```

Each component has a **specific responsibility**.

---

# 5. Input Data Format (Langfuse Traces)

The pipeline expects traces from **Langfuse**.

These traces must follow a **structured format**.

---

# Generative Trace Format

```json
{
  "id": "trace_123",
  "type": "generative",
  "model": "gemini-2.0-flash",
  "timestamp": "2026-03-01T10:15:30",
  
  "input": "What is the capital of France?",
  
  "output": "The capital of France is Paris.",
  
  "retrieved_docs": [
      "doc_12",
      "doc_45"
  ],
  
  "ground_truth_docs": [
      "doc_12"
  ]
}
```

### Fields Explained

| Field | Description |
|------|-------------|
| trace_id | Unique request ID |
| input | User prompt |
| output | Model response |
| retrieved_docs | Documents returned by retriever |
| ground_truth_docs | Correct documents |

---

# Agentic Trace Format

```json
{
  "id": "trace_456",
  "type": "agentic",
  "model": "agent-v1",
  "timestamp": "2026-03-01T10:16:00",
  
  "policy": "Agent must only access authorized tools",
  
  "events": [
      {
          "timestamp": "2026-03-01T10:16:01",
          "event_type": "tool_call",
          "tool_latency": 0.9
      },
      {
          "timestamp": "2026-03-01T10:16:05",
          "event_type": "error",
          "error": true,
          "recovered": true
      }
  ]
}
```

### Fields Explained

| Field | Description |
|------|-------------|
| events | List of agent actions |
| policy | Behavioral policy |
| tool_latency | Tool response time |

---

# 6. Output Data Format (BigQuery Tables)

Two tables are written.

---

# Table 1 — `generative_metrics`

```json
{
  model_id: STRING
  trace_id: STRING
  request_time: TIMESTAMP
  hallucination_score: FLOAT
  safety_score: FLOAT
  pii_leakage_score: FLOAT
  rag_precision: FLOAT
  rag_recall: FLOAT
}
```

### Example Row

```json
{
  "model_id": "gemini-2.0-flash",
  "trace_id": "trace_123",
  "request_time": "2026-03-01T10:15:30",
  "hallucination_score": 0.12,
  "safety_score": 0.01,
  "pii_leakage_score": 0.0,
  "rag_precision": 0.5,
  "rag_recall": 1.0
}
```

---

# Table 2 — `agentic_metrics`

```json
{
  model_id: STRING
  trace_id: STRING
  request_time: TIMESTAMP
  goal_completion_time_seconds: FLOAT
  goal_success_rate: FLOAT
  tool_execution_latency_seconds: FLOAT
  error_recovery_rate: FLOAT
  human_intervention_rate: FLOAT
  unauthorized_action_attempts: INTEGER
  model_version: STRING
  ingestion_time: TIMESTAMP
}
```

---

# 7. Generative AI Metrics

## Hallucination Score

Evaluated using:

```python
VertexJudge.hallucination()
```

Prompt:

```
Evaluate hallucination likelihood (0-1).
```

---

## Safety Score

Evaluates policy violations.

Examples:

- Harmful content
- Unsafe advice
- Disallowed instructions

---

## PII Leakage Score

Uses **Google Cloud DLP**.

Detects:

- Email
- Phone
- SSN
- Credit card
- Names

Score:

```
1.0 → PII detected
0.0 → No PII
```

---

## RAG Precision

Measures **retrieval accuracy**.

Formula:

```
precision = relevant_retrieved / retrieved
```

Example:

```
retrieved = [doc1, doc2, doc3]
relevant = [doc1, doc3]

precision = 2 / 3
```

---

## RAG Recall

Measures **retrieval coverage**.

Formula:

```
recall = relevant_retrieved / relevant
```

Example:

```
retrieved = [doc1, doc2]
relevant = [doc1, doc2, doc3]

recall = 2 / 3
```

---

# 8. Agentic AI Metrics

## Goal Completion Time

```python
goal_completion_time(events)
```

Measures **duration between first and last event**.

---

## Tool Latency

```python
tool_latency(events)
```

Average latency of **tool calls**.

---

## Error Recovery Rate

```
recovered_errors / total_errors
```

---

## Human Intervention Rate

```
human_events / total_events
```

---

## Unauthorized Actions

Counts events marked:

```python
event["unauthorized"] == True
```

---

# 9. Module Documentation

## `main.py`

Main pipeline controller.

Responsibilities:

- Fetch traces
- Route evaluation
- Write results

---

## `genai.py`

Handles **Generative AI evaluation**.

Functions:

```python
evaluate_generative_metrics()
```

Computes:

- Hallucination
- Safety
- PII leakage
- RAG precision
- RAG recall

---

## `agentic.py`

Contains **agent workflow metrics**.

Functions:

```python
goal_completion_time()
tool_latency()
error_recovery_rate()
human_intervention_rate()
unauthorized_actions()
```

---

## `vertex_judge.py`

Implements **LLM-as-a-judge evaluation**.

Uses:

```
Vertex AI Gemini model
```

Methods:

```
hallucination()
safety()
judge_agent_goal()
```

---

## `langfuse_reader.py`

Fetches traces from **Langfuse API**.

Time window:

```
last 15 minutes
```

---

## `writers/bigquery_writer.py`

Handles **BigQuery ingestion**.

Writes:

```
generative_metrics
agentic_metrics
```

---

## `writers/langfuse_scorer.py`

Sends evaluation scores back to **Langfuse**.

This enables:

- Observability dashboards
- Trace-level quality analysis

---

# 10. Environment Variables

Required environment variables:

```
LANGFUSE_HOST
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY

GCP_PROJECT
VERTEX_LOCATION

GOOGLE_APPLICATION_CREDENTIALS
```

---

# Predictive Metrics Documentation

This documentation outlines the **EMMS (Evaluation and Monitoring Management System)** — a robust, cloud-native pipeline designed to track the **health, performance, and data integrity of predictive models in production**.

---

# 1. System Overview

The **EMMS monitoring pipeline** is a **decoupled architecture** that separates heavy computation from metric serving.

It utilizes:

- **Evidently** → Drift and performance analysis
- **Google Cloud Storage (GCS)** → Persistence
- **Prometheus** → Observability

---

## The Core Workflow

### Configuration Fetching

Both the **job** and the **service** fetch model metadata from a centralized **Registration API**.

Metadata includes:

- Column mappings
- Thresholds
- Data paths

---

### Drift Computation

A scheduled job (`compute_drift.py`) performs the following:

- Pulls **reference data** from **GCS**
- Pulls **current production data** from **BigQuery**
- Calculates **drift and model performance**

---

### Persistence

The resulting analysis is saved as a **detailed JSON report** in a **GCS bucket**.

---

### Metric Exposure

A lightweight **FastAPI service (`main.py`)**:

- Reads JSON reports from GCS
- Translates results into **Prometheus-compatible metrics**

---

# 2. File Breakdown & Logic

## `config.py` — The Source of Truth

This module acts as the **configuration layer**, ensuring consistent metadata across the pipeline.

### Registration API Integration

- Fetches model configurations dynamically
- Uses **OIDC-authenticated GET requests**

### Data Models

Defines the **`ModelConfig` dataclass**, which standardizes:

- Model IDs
- Data paths (GCS / BigQuery)
- Column mappings

Column mappings include:

- Target
- Prediction
- Features

### Auth Handling

Implements:

```python
_get_auth_headers()
```

This securely communicates with other **Cloud Run services using Google ID tokens**.

---

## `compute_drift.py` — The Worker (Computation Job)

This script is designed to run as a:

- **Cloud Run Job**
- **Kubernetes CronJob**

It performs the **heavy computation of the pipeline**.

---

### Data Loading

#### Reference Data

Downloaded from **GCS Parquet files**.

#### Current Data

Fetched using **SQL queries from BigQuery**.

---

### Evidently Reports

An **Evidently Report** is built using several presets:

- `DataDriftPreset`
- `DataQualityPreset`
- `TargetDriftPreset`
- Performance presets:
  - `RegressionPreset`
  - `ClassificationPreset`

---

### Stability Metrics

Tracks additional predictive stability metrics such as:

- Prediction variance
- Brier scores
- Expected Calibration Error (ECE)

These are calculated using:

```python
PredictionStatsMetric
```

---

### Notification

Once the JSON report is uploaded to **GCS**, the job triggers:

```
/refresh
```

on the **FastAPI service** so metrics update immediately.

---

## `main.py` — The Metrics Service

A **FastAPI application** that serves as the interface between:

- Stored drift reports
- Monitoring dashboards (e.g., **Grafana**)

---

### Metric Registry

Defines **Prometheus Gauges** for multiple metric categories.

#### Drift Metrics

- Dataset drift share
- Feature-level drift scores

#### Regression Metrics

- MAE
- RMSE
- R²

#### Classification Metrics

- Accuracy
- Precision
- Recall
- Log Loss

---

### Background Refresh

A **daemon thread** periodically scans the **GCS bucket** for new reports and updates the internal metric state.

---

### API Endpoints

| Endpoint | Purpose |
|--------|--------|
| `/metrics` | Exposes metrics in Prometheus format |
| `/api/v1/drift-reports` | JSON summary of monitored models |
| `/health` | Health check with environment metadata |

---

# 3. Data Formats

## Input Formats

The pipeline expects **two datasets** for comparison.

| Data Type | Source | Format | Purpose |
|----------|-------|--------|--------|
| Reference Data | Google Cloud Storage | Parquet | Historical baseline ("gold standard") |
| Current Data | BigQuery | SQL query result | Current production behavior |

---

## Required Columns (via `ColumnMapping`)

| Column | Description |
|------|-------------|
| Target | Ground truth value |
| Prediction | Model output |
| Features | Numerical, Categorical, or Text |

These categories allow appropriate statistical tests to be applied.

---

# Output Formats

The system generates **two output types**.

---

## 1. JSON Report (Internal)

Stored in:

```
gs://{BUCKET}/drift-reports/{model_id}_report.json
```

Contains:

- Raw statistical scores
- Distribution comparisons
- Detailed Evidently analysis

---

## 2. Prometheus Metrics (Public)

Accessible via:

```
/metrics
```

Example metric:

```
emms_feature_drift_score{feature="age", model_id="churn_v1"} 0.04
```

---

# 4. Key Metrics Tracked

The pipeline extracts metrics for monitoring and alerting.

---

## Drift Metrics

- `dataset_drift_share`
- `feature_drift_detected`
- `max_feature_drift`

---

## Performance Metrics (Regression)

- `regression_mae`
- `regression_rmse`
- `regression_r_squared`

---

## Performance Metrics (Classification)

- `classification_accuracy`
- `classification_precision`
- `classification_log_loss`

---

## Data Quality Metrics

- `data_quality_score`
- `missing_values_share`

---

# Metric Calculation Pipeline

Metrics are computed using a **two-stage process**.

1. **Statistical computation (batch job)** using Evidently.
2. **Metric extraction (service)** converting results to Prometheus gauges.

---

# 5. Metric Calculation Logic (`compute_drift.py`)

Metrics are calculated using **Evidently Presets**.

These presets group multiple statistical tests together.

---

## Base Metrics

```python
metrics = [
    DataDriftPreset(drift_share=model_config.drift_share_threshold),
    DataQualityPreset(),
]
```

These compute:

- Feature distribution drift
- Dataset-level quality statistics

---

## Target Drift

Checks whether the **ground truth distribution has shifted**.

```python
if model_config.target_col:
    metrics.append(TargetDriftPreset())
```

---

## Predictive Performance Metrics

The pipeline dynamically selects performance metrics based on model subtype.

```python
model_subtype = getattr(model_config, "model_subtype", "regression").lower()
```

### Regression Models

```python
metrics.append(RegressionPreset())
```

Calculates:

- MAE
- RMSE
- R²

---

### Classification Models

```python
metrics.append(ClassificationPreset())
```

Calculates:

- Accuracy
- Precision
- Recall
- Log Loss

---

## Stability & Calibration Metrics

```python
metrics.append(PredictionStatsMetric())
```

Tracks:

- Prediction variance
- Brier scores
- Expected Calibration Error

---

## Report Execution

The Evidently statistical computation is executed using:

```python
report = Report(metrics=metrics)

report.run(
    reference_data=ref_data,
    current_data=cur_data,
    column_mapping=column_mapping,
)
```

The **ColumnMapping** ensures the correct statistical tests are applied:

Examples:

- **Kolmogorov–Smirnov** test for numerical features
- **Chi-squared** test for categorical features

---

# 6. Metric Extraction and Scaling (`main.py`)

Once the computation job stores the JSON report, the **metrics service extracts values and converts them into Prometheus gauges**.

---

## Drift Metrics Calculation

Dataset drift and feature drift scores are extracted as follows:

```python
if metric_type == "DatasetDriftMetric":
    share = result.get("drift_share", 0.0)
    dataset_drift_share.labels(model_id).set(share)
    
    drift_cols = result.get("drift_by_columns", {})
    scores = [v.get("drift_score", 0) for v in drift_cols.values()]
    
    if scores:
        max_feature_drift.labels(model_id).set(max(scores))
        avg_feature_drift.labels(model_id).set(sum(scores) / len(scores))
```

This calculates:

- Overall **dataset drift share**
- **Maximum feature drift**
- **Average feature drift**

---

# Regression & Classification Performance

The service maps performance results from the **current production dataset**.

---

## Regression Metrics

```python
elif metric_type == "RegressionQualityMetric":
    cur = result.get("current", {})
    regression_mae.labels(model_id).set(cur.get("mean_abs_error", 0.0))
    regression_rmse.labels(model_id).set(cur.get("rmse", 0.0))
```

---

## Classification Metrics

```python
elif metric_type == "ClassificationQualityMetric":
    cur = result.get("current", {})
    classification_accuracy.labels(model_id).set(cur.get("accuracy", 0.0))
    classification_precision.labels(model_id).set(cur.get("precision", 0.0))
```

---

# Stability and Data Quality Metrics

Additional metrics are derived through custom calculations.

---

## Prediction Variance

Variance is derived from **standard deviation**.

```python
elif metric_type == "PredictionStatsMetric":
    cur = result.get("current", {})
    std = cur.get("std")
    
    if std is not None:
        prediction_variance.labels(model_id).set(std ** 2)
```

---

## Data Quality Score

The pipeline converts missing value share into a **data quality score**.

```python
elif metric_type == "DatasetMissingValuesMetric":
    cur = result.get("current", {})
    share = cur.get("share_of_missing_values", 0.0)
    
    data_quality_score.labels(model_id).set(1.0 - share)
```

This ensures:

```
Higher score → Better data quality
Lower score → More missing data
```

---

# EMMS Analytics ETL Pipeline: Technical Documentation

This document provides a **comprehensive technical breakdown** of the **EMMS Analytics ETL (Extract, Transform, Load) pipeline**.

This pipeline serves as the **backbone of the AI Command Center**, converting **raw, high-volume telemetry** into **actionable insights** for multiple stakeholders.

---

# 1. System Architecture & Data Flow

The ETL process follows a **"Hub and Spoke" architecture**.

It pulls from:

- A centralized **Model Registry**
- Multiple **Raw Telemetry Tables**

The pipeline then processes the data through **three specialized transformers** and produces **"Gold Layer" tables** optimized for dashboards.

---

# Data Input Formats (The "Bronze" Layer)

## A. Model Registry (`ModelRegistryClient`)

The **Model Registry** acts as the **system of record for model ownership and metadata**.

It provides a mapping between:

```
model_id → business metadata
```

### Format

Dictionary-like object.

### Key Fields

| Field | Description |
|------|-------------|
| `model_id` | Unique identifier of the model |
| `owner_team` | Responsible team |
| `model_type` | Predictive, GenAI, or Agentic |
| `status` | Model lifecycle status |

---

## B. Base Telemetry Tables (BigQuery)

Telemetry data is ingested from **four primary streams** in the `telemetry` dataset.

Most telemetry follows a **Long/Tidy format**:

```
metric_name → metric_value
```

However, the ETL pipeline supports both **general and specialized metrics**.

### Telemetry Tables

| Table | Primary Data Points |
|------|---------------------|
| `emms_llm` | Cost, tokens (input/output), latency |
| `generative_metrics` | Hallucination, safety, PII leakage |
| `predictive_metrics` | Statistical drift, accuracy, F1-score, RMSE |
| `agentic_metrics` | Goal success, tool latency, intervention rate |

---

# 2. Transformer Deep-Dive

Each transformer is implemented as a **Python class**.

They process the **same base tables**, but each transformer analyzes the data from a **different operational perspective**.

---

# A. Executive Transformer (`executive_transform.py`)

The **Executive Transformer** focuses on **portfolio-level ROI and risk monitoring**.

Primary business question:

> "How much are we spending, and is our AI safe?"

---

## Key Code Logic: Aggregator Pattern

The transformer uses a nested **`defaultdict`** structure to group metrics by `model_id`.

```python
# Data Aggregation Example
for r in llm_rows:
    m = metrics[r["model_id"]]
    m["cost"] += r.get("total_cost_usd", 0)
    m["tokens"] += r.get("total_tokens", 0)
    m["latencies"].append(r.get("latency_ms"))
```

### Explanation

Instead of computing averages **during ingestion** (which is difficult with streaming data), the code:

1. Collects values into lists
2. Aggregates them after ingestion
3. Uses a helper `avg()` function to compute final metrics.

This approach improves **numerical accuracy and processing efficiency**.

---

# Health Scoring Logic

This is the **core business rule** of the pipeline.

It converts **technical signals** into a **traffic-light health status**.

```python
if drift is not None and drift > 0.4:
    health = "CRITICAL"
elif drift is not None and drift > 0.2:
    health = "DEGRADED"
elif safety is not None and safety > 0.5:
    health = "CRITICAL"
else:
    health = "HEALTHY"
```

### Explanation

The scoring prioritizes:

1. **Model Drift**
2. **Safety Violations**

Even if a model is **fast and cheap**, a **high safety violation score** immediately marks it as:

```
CRITICAL
```

This ensures leadership visibility into **risk-heavy models**.

---

# B. Model Owner Transformer (`model_owner_transform.py`)

The **Model Owner Transformer** is designed for **operators and ML engineers**.

Unlike the executive transformer, this component generates **active alerts** rather than just summarizing status.

---

## Key Code Logic: Alert Generation

While computing metrics, the transformer maintains an **`alert_rows` list**.

```python
# Operational Alerting Example
if drift is not None and drift > 0.3:
    alert_level = "WARNING"
    alert_rows.append({
        "model_id": model_id,
        "alert_type": "DRIFT",
        "severity": "WARNING",
        "message": f"Model drift {drift} exceeds threshold"
    })
```

### Explanation

This component acts as a **secondary alerting system**.

Infrastructure monitoring tools track:

- CPU
- RAM
- Infrastructure uptime

But this logic monitors **model behavior**.

If drift exceeds **0.3**, the pipeline writes a record to:

```
emms_alerts
```

This triggers a **UI alert notification** for model operators.

---

# C. Compliance Transformer (`compliance_transform.py`)

The **Compliance Transformer** acts as the **system auditor**.

Its job is to ensure that:

> Models registered in the system are actually being monitored in production.

---

## Key Code Logic: Intersection Check

The transformer compares two sets:

1. **Registered models**
2. **Models generating telemetry**

```python
monitored = model_id in monitored_models
event_count = telemetry_counts.get(model_id, 0)

if not monitored:
    compliance_status = "NOT_MONITORED"
elif event_count < 10:
    compliance_status = "LOW_OBSERVABILITY"
```

### Explanation

Two compliance gaps can occur.

#### NOT_MONITORED

The model exists in the **registry**, but **no telemetry events exist**.

This indicates a **broken monitoring integration**.

#### LOW_OBSERVABILITY

The model is sending telemetry, but the **sample size is too small** to produce reliable metrics.

Threshold used:

```
< 10 events
```

---

# 3. Data Output Formats (The "Gold" Layer)

The final outputs are written to the **`analytics` dataset**.

All tables are **daily-partitioned** to improve query performance and cost efficiency.

---

# Table 1 — `analytics.executive_dashboard`

| Field | Type | Description |
|------|------|-------------|
| `model_id` | STRING | Model identifier |
| `monthly_cost_usd` | FLOAT | Total cost across all calls |
| `success_rate` | FLOAT | Ratio of successful to total inferences |
| `model_health_status` | STRING | HEALTHY, DEGRADED, or CRITICAL |

---

# Table 2 — `analytics.model_owner_dashboard`

| Field | Type | Description |
|------|------|-------------|
| `avg_drift_score` | FLOAT | Mean statistical drift |
| `error_rate` | FLOAT | Total errors divided by total requests |
| `alert_level` | STRING | Highest alert status (CRITICAL, WARNING, INFO) |

---

# Table 3 — `analytics.compliance_audit_dashboard`

| Field | Type | Description |
|------|------|-------------|
| `telemetry_events` | INTEGER | Total telemetry rows detected |
| `is_monitored` | BOOLEAN | True if model appears in telemetry tables |
| `compliance_status` | STRING | COMPLIANT, LOW_OBSERVABILITY, NOT_MONITORED |

---

# 4. Execution Workflow

The ETL pipeline executes in four stages.

---

## 1. Extraction

The **BigQueryClient** executes queries:

```
SELECT *
```

across the **four telemetry tables**.

---

## 2. Registry Load

The **ModelRegistryClient** fetches the current:

```
model_id → owner mappings
```

from the **Model Registry API**.

---

## 3. Transformation

The three transformers run **in parallel**:

- Executive Transformer
- Model Owner Transformer
- Compliance Transformer

Each produces a **specialized analytics dataset**.

---

## 4. Loading

The transformed results are written to **BigQuery analytics tables** using:

```python
bq.write_table()
```

Depending on configuration, the load strategy may be:

- **Overwrite**
- **Append**

---

# Summary

The **EMMS Analytics ETL pipeline** converts **raw AI telemetry** into **business-level intelligence** by:

- Aggregating metrics across AI systems
- Detecting operational risks
- Generating model alerts
- Verifying monitoring coverage
- Producing dashboard-ready datasets

The architecture enables **multi-stakeholder observability**, supporting:

- **Executives** → Portfolio health & cost
- **Model Owners** → Operational alerts
- **Compliance Teams** → Monitoring coverage
