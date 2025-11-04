from dotenv import load_dotenv
load_dotenv()

from twilio.rest import Client
import os

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)

call = client.calls.create(
    to="+919000383940",
    from_="18787788038",
    url="https://inlaid-unclimbing-sandra.ngrok-free.dev/voice"
)

print(call.sid)
