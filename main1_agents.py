from lead_extraction import get_prequalified_leads
from call_agent import call_prospect
from routing_agent import route_lead
import time

def wait_for_consent(call_sid):
    """
    Dummy wait function. Replace with actual logic that waits for consent
    from your Flask / server.py sessions dictionary.
    """
    # For example, poll sessions dict for completed consent
    time.sleep(2)  # placeholder
    return {
        "call_id": call_sid,
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+911234567890",
        "email": "john@example.com",
        "plan": "Family 5GB/Month",
        "consent": "email and call"
    }

def main():
    leads = get_prequalified_leads()
    for lead in leads:
        call_sid = call_prospect(lead)
        # wait for user to give consent via /voice webhook
        completed_lead = wait_for_consent(call_sid)
        route_lead(completed_lead)

if __name__ == "__main__":
    main()
