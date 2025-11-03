# project_root/twilio_client.py
"""

Simple Twilio client for POC outbound calling.
This POC uses Twilio's calls.create with inline TwiML <Say> to speak Spanish text.
For production you might prefer hosting MP3 on a public URL and using <Play> or use Twilio Media Streams / Recordings.
"""

import os
import logging
from twilio.rest import Client

logger = logging.getLogger("twilio_client")

class TwilioClient:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.client = Client(account_sid, auth_token) if account_sid and auth_token else None

    def start_call(self, phone_number: str, text: str) -> dict:
        """Start an outbound call that speaks `text` in Spanish using TwiML <Say>.
        Returns a dict with call SID and a simulated transcript (POC).
        """
        if not self.client:
            logger.warning("Twilio client not configured; returning simulated result.")
            return {"success": False, "error": "Twilio not configured", "transcript": ""}

        # Build TwiML to say the text in Spanish (es-ES). Twilio's 'language' supports several locales.
        twiml = f'<Response><Say language="es-ES">{text}</Say></Response>'

        try:
            call = self.client.calls.create(
                to=phone_number,
                from_=self.from_number,
                twiml=twiml
            )
            logger.info("Started Twilio call SID=%s", call.sid)
            # NOTE: For transcript, you would integrate with Twilio Recordings or Voice Insights / Speech to Text.
            # For POC we return a placeholder transcript.
            transcript = "(Transcripción simulada) El cliente no respondió o no estaba disponible."
            return {"success": True, "call_sid": call.sid, "transcript": transcript}
        except Exception as e:
            logger.exception("Twilio call failed: %s", str(e))
            return {"success": False, "error": str(e), "transcript": ""}
