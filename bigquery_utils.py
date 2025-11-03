# project_root/bigquery_utils.py
from google.cloud import bigquery
from typing import List, Dict, Any
import datetime
import os

class BigQueryClient:
    def __init__(self, project: str, dataset: str, table: str):
        self.client = bigquery.Client(project=project)
        self.project = project
        self.dataset = dataset
        self.table = table
        self.table_ref = f"{project}.{dataset}.{table}"

    def fetch_leads(self, consent_call: bool = True, limit: int = 50) -> List[Dict[str, Any]]:
        query = f"""
        SELECT * FROM `{self.table_ref}`
        WHERE consent_call = @consent_call
        ORDER BY created_at ASC
        LIMIT @limit
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("consent_call", "BOOL", consent_call),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
        query_job = self.client.query(query, job_config=job_config)
        rows = [dict(row) for row in query_job.result()]
        return rows

    def update_transcript(self, lead_id: str, transcript: str):
        sql = f"""
        UPDATE `{self.table_ref}`
        SET transcript = @transcript, last_contacted = @now
        WHERE lead_id = @lead_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("transcript", "STRING", transcript),
                bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.datetime.utcnow().isoformat()),
                bigquery.ScalarQueryParameter("lead_id", "STRING", lead_id),
            ]
        )
        self.client.query(sql, job_config=job_config).result()
