from twilio.rest import Client
import os

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(account_sid, auth_token)

try:
    account = client.api.accounts(account_sid).fetch()
    print("Authenticated! Account name:", account.friendly_name)
except Exception as e:
    print("Failed to authenticate:", e)
