from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class GenerativeMetricsResult(BaseModel):
    """
    Stores evaluation metrics for generative AI responses.
    Includes resource labels (environment, team, region) to match upstream SDK telemetry.
    """
    model_id: str
    trace_id: str
    request_time: datetime
    environment: str = "unknown"
    team_name: Optional[str] = None
    gcp_region: Optional[str] = None

    # LLM quality metrics
    hallucination_score: float
    safety_score: float
    pii_leakage_score: float

    # Token usage (extracted from Langfuse trace - aligns with gen_ai.usage.* in docs)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # Retrieval quality metrics (for RAG systems)
    rag_precision: Optional[float] = None
    rag_recall: Optional[float] = None


class AgenticMetricsResult(BaseModel):
    """
    Stores evaluation metrics for agent workflows.
    """
    model_id: str
    trace_id: str
    request_time: datetime
    environment: str = "unknown"
    team_name: Optional[str] = None
    gcp_region: Optional[str] = None

    goal_completion_time_seconds: float
    goal_success_rate: float

    tool_execution_latency_seconds: float
    error_recovery_rate: float
    human_intervention_rate: float
    unauthorized_action_attempts: int

    model_version: Optional[str] = None
    ingestion_time: datetime
