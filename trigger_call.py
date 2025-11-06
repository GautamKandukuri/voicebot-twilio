# trigger_call.py
from twilio.rest import Client
import os, json, sys

# Load config
try:
    config = json.load(open("config.json"))
except FileNotFoundError:
    print("❌ config.json not found")
    sys.exit(1)

# Use .env for PUBLIC_URL fallback
from dotenv import load_dotenv
load_dotenv()

# Twilio credentials
account_sid = config.get("twilio_account_sid")
auth_token = config.get("twilio_auth_token")
from_number = config.get("twilio_from_number")
to_number = config.get("twilio_to_number")

if not all([account_sid, auth_token, from_number, to_number]):
    print("❌ Missing Twilio configuration in config.json")
    sys.exit(1)

client = Client(account_sid, auth_token)

# Public URL (ngrok)
public = os.getenv("PUBLIC_URL") or config.get("public_ngrok_url")
if not public:
    print("❌ PUBLIC_URL not set in .env or config.json")
    sys.exit(1)

twiml_url = f"{public}/voice"

# Trigger call with error handling
try:
    call = client.calls.create(
        to=to_number,
        from_=from_number,
        url=twiml_url
    )
    print("✅ Triggered call:", call.sid)
except Exception as e:
    print(f"❌ Failed to trigger call: {e}")

