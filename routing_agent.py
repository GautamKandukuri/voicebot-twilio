import os
from google.cloud import bigquery
from datetime import datetime
from utils.email_utils import send_lead_email  # Optional helper

PROJECT = os.getenv("GCP_PROJECT")
DATASET = os.getenv("BQ_DATASET")
TABLE = os.getenv("BQ_TABLE")

bq_client = bigquery.Client(project=PROJECT)
table_ref = f"{PROJECT}.{DATASET}.{TABLE}"

def route_lead(lead):
    """Insert lead back into BigQuery and send notifications"""
    row = {
        "call_id": lead.get("call_id"),
        "lead_id": lead.get("call_id"),  # unique identifier
        "first_name": lead.get("first_name") or "",
        "last_name": lead.get("last_name") or "",
        "phone": lead.get("phone") or "",
        "email": lead.get("email") or "",
        "plan": lead.get("plan") or "",
        "consent": lead.get("consent") or "",
        "timestamp": datetime.utcnow().isoformat()
    }

    # Insert into BigQuery
    errors = bq_client.insert_rows_json(table_ref, [row])
    if errors:
        print(f"❌ BigQuery insert errors: {errors}")
    else:
        print("✅ Lead saved to BigQuery")

    # Send email notifications
    send_lead_email(row)

    # Optional: block calendar slots via Google Calendar API
