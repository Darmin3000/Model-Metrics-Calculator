"""
EMMS Evidently — Model Configuration

Acts as the dynamic configuration layer.
1. Connects to Cloud SQL to find active models and their GCS metadata URIs.
2. Downloads the JSON metadata from GCS.
3. Parses the JSON into ModelConfig objects for the pipeline to use.

UPDATED: Now also extracts service_name and association_id_column for GCS CSV loading.
"""

import logging
import os
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from google.cloud import storage
from google.cloud.sql.connector import Connector, IPTypes
import sqlalchemy

# ---------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------
GCP_PROJECT = os.environ.get("GCP_PROJECT", "")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "unknown")

# Database Credentials
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME", "")
DB_USER = os.environ.get("DB_USER", "")
DB_PASS = os.environ.get("DB_PASS", "")
DB_NAME = os.environ.get("DB_NAME", "")

@dataclass
class ModelConfig:
    """Configuration dataclass for a single model's drift monitoring."""
    model_id: str
    service_name: str                     # ← NEW: used for GCS path
    model_type: str
    model_subtype: str

    # Data source definitions (now CSV-based)
    reference_path: str                   # kept for backward compatibility
    current_query: str                    # kept for backward compatibility

    # New GCS-based fields
    association_id_column: Optional[str] = None

    # Column mappings defining the schema for Evidently
    target_col: Optional[str]
    prediction_col: Optional[str]
    numerical_features: List[str]
    categorical_features: List[str]
    text_features: List[str]
    drift_share_threshold: float


def _parse_model(model_id: str, service_name: str, metadata: Dict[str, Any]) -> Optional[ModelConfig]:
    """Helper function to map a raw JSON dictionary to the ModelConfig dataclass."""
    try:
        config_json = metadata.get("config", {}) if isinstance(metadata.get("config"), dict) else {}
        
        return ModelConfig(
            model_id=model_id,
            service_name=service_name,
            model_type=metadata.get("model_type", "predictive"),
            model_subtype=metadata.get("model_subtype", "regression"),
            reference_path=metadata.get("reference_data_path", ""),
            current_query=metadata.get("current_query", ""),
            association_id_column=(
                metadata.get("association_id_column")
                or config_json.get("association_id_column")
                or metadata.get("config", {}).get("association_id_column")
            ),
            target_col=metadata.get("target_column"),
            prediction_col=metadata.get("prediction_column"),
            numerical_features=metadata.get("numerical_features", []),
            categorical_features=metadata.get("categorical_features", []),
            text_features=metadata.get("text_features", []),
            drift_share_threshold=metadata.get("drift_share_threshold", 0.5),
        )
    except Exception as e:
        logger.error(f"Error parsing metadata for {model_id}: {e}")
        return None


def load_model_configs() -> List[ModelConfig]:
    """
    Main execution function for configuration.
    Fetches the registry from Cloud SQL, then pulls the JSONs from GCS.
    """
    configs = []
    
    connector = Connector()
    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            ip_type=IPTypes.PUBLIC
        )

    try:
        engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)
    except Exception as e:
        logger.error(f"Failed to initialize database engine: {e}")
        return []

    pointers = []
    try:
        with engine.connect() as conn:
            # UPDATED QUERY: also fetch service_name
            query = sqlalchemy.text(
                "SELECT model_id, service_name, metadata_gcs_uri FROM model_registry WHERE status = 'active'"
            )
            result = conn.execute(query)
            pointers = result.fetchall()
    except Exception as e:
        logger.error(f"Database query failed: {e}")
    finally:
        connector.close()

    if not pointers:
        logger.info("No active models found in the registry.")
        return configs

    storage_client = storage.Client()
    
    for model_id, service_name, gcs_uri in pointers:
        try:
            path_parts = gcs_uri.replace("gs://", "").split("/", 1)
            bucket_name = path_parts[0]
            blob_name = path_parts[1]
            
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            metadata_json = json.loads(blob.download_as_text())
            
            cfg = _parse_model(model_id, service_name, metadata_json)
            if cfg:
                configs.append(cfg)
                
        except Exception as e:
            logger.error(f"Failed to load GCS metadata for {model_id} from {gcs_uri}: {e}")

    logger.info(f"Successfully loaded {len(configs)} model configurations.")
    return configs
