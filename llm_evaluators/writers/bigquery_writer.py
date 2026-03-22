import os
import logging
from google.cloud import bigquery
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class BigQueryWriter:
    def __init__(self):
        self.client = bigquery.Client()
        self.project = os.environ["GCP_PROJECT"]
        self.dataset = os.environ["BQ_DATASET"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def write(self, table: str, rows: list[dict]):
        """
        Write rows to BigQuery (matches the long-term analytics sink in Storage_layer_handover.md).
        """
        if not rows:
            return
        table_id = f"{self.project}.{self.dataset}.{table}"
        logger.info(f"Writing {len(rows)} rows to {table_id}")
        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
            raise RuntimeError(errors)
