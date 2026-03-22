import json
from sqlalchemy import create_engine, text

DB_URI = "postgresql+pg8000://USER:PASSWORD@/DBNAME?unix_sock=/cloudsql/INSTANCE/.s.PGSQL.5432"

engine = create_engine(DB_URI)


def fetch_thresholds():

    query = """
    SELECT model_id, thresholds
    FROM model_monitoring_config
    """

    with engine.connect() as conn:

        rows = conn.execute(text(query)).fetchall()

    results = []

    for row in rows:

        thresholds = row.thresholds

        if isinstance(thresholds, str):
            thresholds = json.loads(thresholds)

        results.append({
            "model_id": row.model_id,
            "thresholds": thresholds
        })

    return results
