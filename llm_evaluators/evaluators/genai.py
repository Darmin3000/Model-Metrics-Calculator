"""
Generative AI evaluation module.

This module computes evaluation metrics for LLM responses including:

1. Hallucination score (Vertex AI judge) ← now uses ground-truth documents from GCS
2. Safety score (Vertex AI judge)
3. PII leakage detection (Google Cloud DLP)
4. RAG Precision
5. RAG Recall

All logic is intentionally contained in this file for clarity.
"""

import os
import logging
from typing import List
from google.cloud import dlp_v2
from tenacity import retry, stop_after_attempt, wait_exponential

from evaluators.vertex_judge import VertexJudge

logger = logging.getLogger(__name__)

# -------------------------------------------------------
# GOOGLE CLOUD DLP CLIENT
# -------------------------------------------------------

class DLPDetector:
    """
    Wrapper around Google Cloud Data Loss Prevention API
    used to detect PII in model outputs.
    """

    def __init__(self):
        self.client = dlp_v2.DlpServiceClient()
        self.project_id = os.environ["GCP_PROJECT"]
        self.parent = f"projects/{self.project_id}"
        # Common sensitive information types
        self.info_types = [
            {"name": "EMAIL_ADDRESS"},
            {"name": "PHONE_NUMBER"},
            {"name": "US_SOCIAL_SECURITY_NUMBER"},
            {"name": "CREDIT_CARD_NUMBER"},
            {"name": "PERSON_NAME"},
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def contains_pii(self, text: str) -> bool:
        """
        Checks if text contains sensitive information.
        Uses Google Cloud DLP inspection.
        """
        if not text:
            return False

        try:
            item = {"value": text}
            inspect_config = {
                "info_types": self.info_types,
                "min_likelihood": "POSSIBLE",
            }
            response = self.client.inspect_content(
                request={
                    "parent": self.parent,
                    "inspect_config": inspect_config,
                    "item": item,
                }
            )
            return len(response.result.findings) > 0
        except Exception as e:
            logger.warning(f"DLP inspection failed: {e}")
            return False


# -------------------------------------------------------
# PII LEAKAGE METRIC
# -------------------------------------------------------

def pii_leakage(response: str, dlp: DLPDetector) -> float:
    """
    Detects if the model response leaks PII.

    Metric Definition
    -----------------
    1.0 = PII detected
    0.0 = No PII detected
    """
    return 1.0 if dlp.contains_pii(response) else 0.0


# -------------------------------------------------------
# RAG PRECISION METRIC
# -------------------------------------------------------

def rag_precision(retrieved_docs: List[str], relevant_docs: List[str]) -> float:
    """
    RAG Precision measures how many retrieved documents are actually relevant.

    Formula:
        Precision = Relevant Retrieved Docs / Total Retrieved Docs
    """
    if not retrieved_docs:
        return 0.0
    return len(set(retrieved_docs) & set(relevant_docs)) / len(set(retrieved_docs))


# -------------------------------------------------------
# RAG RECALL METRIC
# -------------------------------------------------------

def rag_recall(retrieved_docs: List[str], relevant_docs: List[str]) -> float:
    """
    RAG Recall measures how many relevant documents were retrieved.

    Formula:
        Recall = Relevant Retrieved Docs / Total Relevant Docs
    """
    if not relevant_docs:
        return 0.0
    return len(set(retrieved_docs) & set(relevant_docs)) / len(set(relevant_docs))


# -------------------------------------------------------
# FULL GENERATIVE EVALUATION PIPELINE
# -------------------------------------------------------

def evaluate_generative_metrics(
    prompt: str,
    response: str,
    retrieved_docs: List[str],
    ground_truth_docs: List[str],
    vertex: VertexJudge,
    dlp: DLPDetector,
) -> dict:
    """
    Executes the full evaluation pipeline for generative AI responses.

    Metrics Computed
    ----------------
    1. Hallucination Score (Vertex AI judge) ← now receives ground_truth_docs from GCS
    2. Safety Score (Vertex AI judge)
    3. PII Leakage Score (Google Cloud DLP)
    4. RAG Precision
    5. RAG Recall
    """
    try:
        return {
            "hallucination_score": vertex.hallucination(prompt, response, ground_truth_docs),
            "safety_score": vertex.safety(response),
            "pii_leakage_score": pii_leakage(response, dlp),
            "rag_precision": rag_precision(retrieved_docs, ground_truth_docs),
            "rag_recall": rag_recall(retrieved_docs, ground_truth_docs),
        }
    except Exception as e:
        logger.error(f"Generative evaluation failed: {e}")
        return {"hallucination_score": 0.0, "safety_score": 0.0, "pii_leakage_score": 0.0, "rag_precision": 0.0, "rag_recall": 0.0}
