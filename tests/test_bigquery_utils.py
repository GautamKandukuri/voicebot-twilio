# project_root/tests/test_bigquery_utils.py
import os
import pytest
from bigquery_utils import BigQueryClient

# This is a simple unit test example — uses environment variable to find local emulator or real project.
@pytest.mark.skipif(os.getenv("CI", "false") == "true", reason="Skip in CI unless configured")
def test_fetch_leads_minimal():
    project = os.getenv("GCP_PROJECT")
    dataset = os.getenv("BQ_DATASET", "voicebot_leads")
    table = os.getenv("BQ_TABLE", "leads")
    bq = BigQueryClient(project=project, dataset=dataset, table=table)
    leads = bq.fetch_leads(consent_call=True, limit=1)
    assert isinstance(leads, list)
