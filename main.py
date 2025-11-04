
from twilio.rest import Client
import json

config = json.load(open("config.json"))

def trigger_call():
    client = Client(config["twilio_account_sid"], config["twilio_auth_token"])
    call = client.calls.create(
        to=config["twilio_to_number"],
        from_=config["twilio_from_number"],
        url="https://inlaid-unclimbing-sandra.ngrok-free.dev/voice"
    )
    print("Call triggered:", call.sid)

if __name__ == "__main__":
    trigger_call()
