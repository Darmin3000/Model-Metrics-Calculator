import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Structured logging setup (consistent with the rest of the pipeline)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
POLL_MINUTES = int(os.environ.get("LANGFUSE_POLL_MINUTES", "15"))

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.exceptions.RequestException,)),
    reraise=True
)
def fetch_recent_traces() -> List[Dict[str, Any]]:
    """
    Fetch recent traces from Langfuse with retry logic.
    Matches the GenAI/Agentic trace flow described in data-schemas.md and data-flow-documentation.md.
    """
    end = datetime.utcnow()
    start = end - timedelta(minutes=POLL_MINUTES)

    params = {
        "fromTimestamp": start.isoformat() + "Z",
        "toTimestamp": end.isoformat() + "Z",
    }

    logger.info(f"Fetching traces from {start} to {end}")

    response = requests.get(
        f"{LANGFUSE_HOST}/api/public/traces",
        params=params,
        auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]),
        timeout=15,
    )
    response.raise_for_status()
    traces = response.json().get("data", [])
    logger.info(f"Received {len(traces)} traces")
    return traces
