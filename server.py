import os
import logging
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from google.cloud import bigquery
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# ------------------------------
# Load .env
# ------------------------------
load_dotenv()

PROJECT = os.getenv("GCP_PROJECT")
DATASET = os.getenv("BQ_DATASET")
TABLE = os.getenv("BQ_TABLE")

# ------------------------------
# Logging
# ------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voicebot")

# ------------------------------
# BigQuery Client
# ------------------------------
try:
    bq_client = bigquery.Client(project=PROJECT)
    table_ref = f"{PROJECT}.{DATASET}.{TABLE}"
except Exception as e:
    log.error(f"❌ BigQuery init failed: {e}")
    bq_client = None

# ------------------------------
# Gemini API
# ------------------------------
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
text_model = genai.GenerativeModel("gemini-2.5-flash")
tts_model = "models/gemini-1.5-flash-tts"

# ------------------------------
# Flask App
# ------------------------------
app = Flask(__name__)

# Session Store
sessions = {}

# ------------------------------
# System Prompt
# ------------------------------
SYSTEM_PROMPT = """
You are an outbound telecom sales assistant calling customers in India.
Goal: Capture lead interest in mobile/family data plans.

Flow:
1) Greet & Introduce yourself from telecom provider
2) Confirm first and last name
3) Ask phone number
4) Ask plan requirement (data + minutes)
5) Ask preferred call back time
6) Ask consent to store & share details with sales team

Rules:
- Keep responses short. 1–2 sentences.
- Use friendly tone, Indian English.
- After each user reply, ask next required detail.
- Final message: confirm info + thank user.

Fields to gather:
first_name, last_name, phone, plan details, date/time, consent
"""

# ------------------------------
# Send Email with Transcript + Recording Link
# ------------------------------
def send_lead_email(lead):
    """
    Sends lead details and transcript as email attachment.
    Uses SMTP configuration from environment variables.
    """
    try:
        # Load SMTP and email config from environment
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD")
        mail_from = os.getenv("MAIL_FROM", smtp_user)
        sales_emails = os.getenv("SALES_EMAILS", "")
        recipient_list = [email.strip() for email in sales_emails.split(",") if email.strip()]

        if not recipient_list:
            log.warning("❌ No recipient emails found. Aborting email sending.")
            return

        # Create the email
        msg = MIMEMultipart()
        msg['From'] = mail_from
        msg['To'] = ", ".join(recipient_list)
        msg['Subject'] = f"Voicebot Lead: {lead.get('call_id') or 'Unknown Call ID'}"

        # Email body safely handling missing data
        body_text = f"""
        New lead received from Voicebot.

        Call ID: {lead.get('call_id') or 'N/A'}
        First Name: {lead.get('first_name') or 'N/A'}
        Last Name: {lead.get('last_name') or 'N/A'}
        Phone: {lead.get('phone_e164') or 'N/A'}
        Email: {lead.get('email') or 'N/A'}
        Plan Details: {lead.get('plan_details') or 'N/A'}
        Consent: {lead.get('consent') or 'N/A'}
        Recording URL: {lead.get('recording_url') or 'N/A'}
        """
        msg.attach(MIMEText(body_text, 'plain'))

        # Attach transcript safely
        transcript_text = str(lead.get("transcript") or "")
        transcript_file = MIMEApplication(transcript_text.encode("utf-8"))
        transcript_file.add_header(
            "Content-Disposition",
            "attachment",
            filename=f"transcript_{lead.get('call_id') or 'unknown'}.txt"
        )
        msg.attach(transcript_file)

        # Send the email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        log.info(f"✅ Email sent successfully to: {', '.join(recipient_list)}")

    except Exception as e:
        log.error(f"❌ Email sending failed: {e}")

# ------------------------------
# BigQuery Save
# ------------------------------
def save_to_bigquery(call_sid):
    session = sessions.get(call_sid, {})

    # Join transcript safely
    transcript_text = " | ".join(session.get("transcript", []))

    # Prepare row matching BigQuery schema with safe defaults
    row = {
        "lead_id": call_sid or "",
        "first_name": session.get("first_name") or "",
        "last_name": session.get("last_name") or "",
        "phone_e164": session.get("customer_phone") or "",
        "email": session.get("email") or "",
        "consent_email": True if session.get("consent") and "email" in session.get("consent").lower() else False,
        "consent_call": True if session.get("consent") and "call" in session.get("consent").lower() else False,
        "hot_lead": False,
        "lead_source": "TelecomVoiceBot",
        "created_at": datetime.utcnow().isoformat(),
        "last_contacted": datetime.utcnow().isoformat(),
        "transcript": transcript_text,
        "selected_plan": session.get("plan_details") or "",
        "plan": session.get("plan_details") or "",
        "consent": session.get("consent") or "",
        "timestamp": datetime.utcnow().isoformat(),
        "recording_url": session.get("recording_url") or "",
        "plan_details": session.get("plan_details") or ""
    }

    if not bq_client:
        log.error("❌ BigQuery client unavailable. Cannot save lead.")
        return

    try:
        errors = bq_client.insert_rows_json(table_ref, [row])
        if errors:
            log.error(f"❌ BigQuery error: {errors}")
        else:
            log.info("✅ Lead saved to BigQuery")
            send_lead_email(row)
    except Exception as e:
        log.error(f"❌ Exception saving to BigQuery: {e}")

# ------------------------------
# AI Response
# ------------------------------
def ai_reply(speech, call_sid):
    sessions.setdefault(call_sid, {}).setdefault("transcript", [])
    sessions[call_sid]["transcript"].append(f"Customer: {speech}")

    stage = sessions[call_sid].get("stage", "greeting")

    prompt = f"""
{SYSTEM_PROMPT}
Current Stage: {stage}
User said: {speech}
Session: {sessions[call_sid]}
"""
    reply = ""
    try:
        reply = text_model.generate_content(prompt).text
    except Exception as e:
        log.error(f"❌ Gemini AI error: {e}")
        reply = "Sorry, I didn't get that. Could you repeat?"

    # Stage transitions
    if stage == "greeting":
        sessions[call_sid]["stage"] = "capture_first_name"

    elif stage == "capture_first_name":
        sessions[call_sid]["first_name"] = speech
        sessions[call_sid]["stage"] = "capture_last_name"

    elif stage == "capture_last_name":
        sessions[call_sid]["last_name"] = speech
        sessions[call_sid]["stage"] = "capture_phone"

    elif stage == "capture_phone":
        sessions[call_sid]["customer_phone"] = speech
        sessions[call_sid]["stage"] = "capture_plan"

    elif stage == "capture_plan":
        sessions[call_sid]["plan_details"] = speech
        sessions[call_sid]["stage"] = "capture_datetime"

    elif stage == "capture_datetime":
        sessions[call_sid]["date_time"] = speech
        sessions[call_sid]["stage"] = "capture_consent"

    elif stage == "capture_consent":
        sessions[call_sid]["consent"] = speech
        sessions[call_sid]["stage"] = "complete"
        save_to_bigquery(call_sid)

    sessions[call_sid]["transcript"].append(f"Bot: {reply}")
    return reply

# ------------------------------
# Twilio Voice Webhook
# ------------------------------
@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid")
    speech = request.form.get("SpeechResult", "")
    recording_url = request.form.get("RecordingUrl")

    if recording_url:
        sessions.setdefault(call_sid, {})["recording_url"] = recording_url

    reply = ai_reply(speech, call_sid)

    vr = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice",
        speechTimeout="1"
    )
    gather.say(reply)
    vr.append(gather)
    return Response(str(vr), mimetype="text/xml")

# ------------------------------
# Run Server
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
