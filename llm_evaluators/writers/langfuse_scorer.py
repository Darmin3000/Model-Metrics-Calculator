"""
Langfuse scorer - attaches evaluation scores back to original traces.
"""
import os
import logging
from datetime import datetime
from langfuse import Langfuse
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class LangfuseScorer:
    def __init__(self):
        self.client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ["LANGFUSE_HOST"],
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def score(self, trace_id: str, name: str, value: float, timestamp: datetime = None, comment: str = None):
        """
        Score a trace (with optional timestamp for historical accuracy).
        """
        self.client.score(
            trace_id=trace_id,
            name=name,
            value=value,
            timestamp=timestamp,
            comment=comment,
        )

    def flush(self):
        try:
            self.client.flush()
            logger.info("Langfuse scores flushed")
        except Exception as e:
            logger.warning(f"Langfuse flush failed: {e}")
