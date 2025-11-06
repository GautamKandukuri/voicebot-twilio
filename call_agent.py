import os
from twilio.rest import Client
import google.generativeai as genai

# Configure Twilio
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_FROM_NUMBER")
twilio_client = Client(account_sid, auth_token)

# Configure Gemini AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
TTS_MODEL = "models/gemini-1.5-flash-tts"

def generate_tts(script_text):
    """Generate TTS audio from Gemini"""
    audio = genai.audio.speech.create(
        model=TTS_MODEL,
        input=script_text,
        voice="alloy"
    )
    return audio  # returns binary audio data

def call_prospect(lead):
    """Trigger an outbound call via Twilio"""
    to_number = lead.get("phone")
    script = lead.get("script", "Hello! This is your telecom provider calling.")
    # You can convert script to TTS audio and serve it via Twilio <Play> if needed
    call = twilio_client.calls.create(
        twiml=f"<Response><Say voice='alice'>{script}</Say></Response>",
        to=to_number,
        from_=from_number
    )
    return call.sid
