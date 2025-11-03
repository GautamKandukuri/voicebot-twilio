# project_root/main.py
"""

Main entrypoint for the outbound voice bot POC (MacBook-friendly) — Twilio integration.
- Reads leads from BigQuery
- Filters consented prospects
- Generates TTS using Gemini-2.5-Flash-TTS and saves MP3 locally
- Initiates outbound call via Twilio using TwiML <Say> (Spanish) as a POC
- Stores transcripts (simulated) and sends email notifications for hot leads / consented prospects
"""

import os
import logging
from dotenv import load_dotenv
from bigquery_utils import BigQueryClient
from vertex_tts import VertexTTS
from twilio_client import TwilioClient
from emailer import Emailer
from transcript_utils import cleanup_transcript

load_dotenv()  # loads .env if present

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("voicebot_poc")

def run_once(limit: int = 50):
    project = os.getenv("GCP_PROJECT")
    dataset = os.getenv("BQ_DATASET", "voicebot_leads")
    table = os.getenv("BQ_TABLE", "leads")

    bq = BigQueryClient(project=project, dataset=dataset, table=table)
    vtts = VertexTTS(model_id=os.getenv("VTX_MODEL_ID"))

    #vtts = VertexTTS(model_id=os.getenv("VTX_MODEL_ID"), location=os.getenv("VTX_LOCATION", "global"))
    twilio = TwilioClient(account_sid=os.getenv("TWILIO_ACCOUNT_SID"), auth_token=os.getenv("TWILIO_AUTH_TOKEN"), from_number=os.getenv("TWILIO_FROM_NUMBER"))
    emailer = Emailer(smtp_host=os.getenv("SMTP_HOST"), smtp_port=int(os.getenv("SMTP_PORT", "587")), username=os.getenv("SMTP_USER"), password=os.getenv("SMTP_PASSWORD"), mail_from=os.getenv("MAIL_FROM"))

    # 1. Fetch leads that haven't been contacted recently and have call consent
    leads = bq.fetch_leads(consent_call=True, limit=limit)
    logger.info("Fetched %d leads to process", len(leads))

    for lead in leads:
        try:
            lead_id = lead["lead_id"]
            phone = lead["phone_e164"]
            name = f'{lead.get("first_name","")} {lead.get("last_name","")}'.strip()
            logger.info("Processing lead %s (%s)", lead_id, phone)

            # 2. Prepare TTS script in Spanish
            tts_text = f"Hola {lead.get('first_name', '')}. Le llamamos de parte de su operador. ¿Tiene un momento para hablar sobre nuestras ofertas?"

            # 3. Generate audio (saved locally for records)
            audio_bytes = vtts.synthesize_text_to_audio(tts_text, output_format="MP3", voice="es-ES-Standard-A")
            audio_filename = f"{lead_id}.mp3"
            with open(audio_filename, "wb") as f:
                f.write(audio_bytes)
            logger.info("Saved TTS audio to %s", audio_filename)

            # 4. Call via Twilio (POC uses TwiML <Say> to speak Spanish text)
            call_result = twilio.start_call(phone_number=phone, text=tts_text)
            logger.info("Twilio call result: %s", call_result)

            # 5. Save transcript if any (POC: call_result may include transcript)
            transcript = call_result.get("transcript") or ""
            cleaned = cleanup_transcript(transcript)
            bq.update_transcript(lead_id=lead_id, transcript=cleaned)

            # 6. If hot lead, send notification
            if lead.get("hot_lead", False):
                subject = f"Lead caliente: {name} ({lead_id})"
                body = f"Se ha detectado un lead caliente.\n\nLead: {name}\nTeléfono: {phone}\nTranscripción: {cleaned}"
                emailer.send_email(os.getenv("SALES_REP_EMAIL"), subject, body)
                logger.info("Sent hot lead email for %s", lead_id)

            # 7. If consent_email true, send email with transcript to the prospect
            if lead.get("consent_email", False) and lead.get("email"):
                subject = "Resumen de la llamada y próxima acción"
                body = f"Hola {lead.get('first_name','')},\n\nGracias por su tiempo. Aquí tiene un resumen de la llamada:\n\n{cleaned}\n\nSaludos."
                emailer.send_email(lead.get("email"), subject, body)
                logger.info("Sent email transcript to prospect %s", lead_id)

        except Exception as e:
            logger.exception("Failed processing lead %s: %s", lead.get("lead_id"), str(e))

if __name__ == "__main__":
    run_once(limit=20)
