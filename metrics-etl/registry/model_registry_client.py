from utils.bq_client import BigQueryClient

class ModelRegistryClient:

    def __init__(self):
        self.bq = BigQueryClient()

    def load_models(self):

        rows = self.bq.read_table("telemetry.emms_models")

        models = {}

        for r in rows:

            models[r["model_id"]] = {
                "owner_team": r.get("owner_team"),
                "model_type": r.get("model_type"),
                "monitoring_enabled": r.get("monitoring_enabled", True)
            }

        return models
