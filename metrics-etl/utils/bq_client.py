from google.cloud import bigquery
from config.settings import PROJECT_ID

class BigQueryClient:

    def __init__(self):
        self.client = bigquery.Client(project=PROJECT_ID)

    def read_table(self, table):

        query = f"SELECT * FROM `{table}`"
        job = self.client.query(query)

        return [dict(row) for row in job]

    def write_table(self, table, rows):

        if not rows:
            return

        table_ref = self.client.dataset(
            table.split(".")[0]
        ).table(
            table.split(".")[1]
        )

        errors = self.client.insert_rows_json(table_ref, rows)

        if errors:
            raise RuntimeError(errors)

    def write_rows(self, table, rows):
        self.write_table(table, rows)
