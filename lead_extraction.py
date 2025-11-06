from google.cloud import bigquery
import os

PROJECT = os.getenv("GCP_PROJECT")
DATASET = os.getenv("BQ_DATASET")
TABLE = os.getenv("BQ_TABLE")

bq_client = bigquery.Client(project=PROJECT)

def get_prequalified_leads():
    """Fetch pre-qualified leads from BigQuery"""
    query = f"""
    SELECT *
    FROM `{PROJECT}.{DATASET}.{TABLE}`
    WHERE status='prequalified' AND contacted=FALSE
    """
    results = bq_client.query(query).result()
    leads = [dict(row) for row in results]
    return leads

