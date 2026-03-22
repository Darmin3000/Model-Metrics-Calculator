"""
Reads RAG document references from Cloud SQL + service_name lookup for GCS training data.
"""
import os
import logging
import psycopg2
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class CloudSQLReader:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.environ["CLOUDSQL_HOST"],
            dbname=os.environ["CLOUDSQL_DB"],
            user=os.environ["CLOUDSQL_USER"],
            password=os.environ["CLOUDSQL_PASSWORD"],
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_service_name(self, model_id: str) -> str:
        """
        Returns service_name from model_registry table (used to build GCS path).
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT service_name FROM model_registry WHERE model_id = %s",
                    (model_id,),
                )
                row = cur.fetchone()
            return row[0] if row else "unknown"
        except Exception as e:
            logger.warning(f"CloudSQL service_name lookup failed for {model_id}: {e}")
            return "unknown"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_ground_truth_docs(self, trace_id: str):
        """
        Legacy method – kept for compatibility (not used after GCS change).
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT document_id FROM rag_ground_truth WHERE trace_id = %s",
                    (trace_id,),
                )
                rows = cur.fetchall()
            return [r[0] for r in rows]
        except Exception as e:
            logger.warning(f"CloudSQL ground truth lookup failed for {trace_id}: {e}")
            return []

    def close(self):
        self.conn.close()
