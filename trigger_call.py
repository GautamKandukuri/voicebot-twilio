from twilio.rest import Client
import json

# Load config.json
config = json.load(open("config.json"))


def trigger_call():
    # Twilio client
    client = Client(config["twilio_account_sid"], config["twilio_auth_token"])

    call = client.calls.create(
        to=config["twilio_to_number"],        # Destination number
        from_=config["twilio_from_number"],   # Twilio number
        url=f"{config['public_ngrok_url']}/voice",  # Outbound bot entry point (TwiML)
        
        # ✅ REQUIRED: Callback on call end (for storing transcript & email)
        status_callback=f"{config['public_ngrok_url']}/call-ended",
        status_callback_event=["completed"],   # Trigger only when call ends
        status_callback_method="POST"
    )

    print("✅ Outbound call triggered")
    print("📞 Call SID:", call.sid)


if __name__ == "__main__":
    trigger_call()

