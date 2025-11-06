import os
import logging
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from google.cloud import bigquery
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voicebot")

# ---- ENV ----
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
bq_client = bigquery.Client()
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SALES_EMAIL = os.getenv("SALES_EMAIL", EMAIL_SENDER)  # fallback to sender

# ---- Flask ----
app = Flask(__name__)
sessions = {}

# ---- AI Model ----
model = genai.GenerativeModel("gemini-2.0-flash")

# ---- BigQuery helpers ----
def save_to_bq(call_sid, recording_url="", transcript=""):
    """Insert a row into BigQuery. Call this for initial lead and for recording/transcript events.
    This function appends rows (one per event). Customize to update existing rows if you prefer."""
    session = sessions.get(call_sid, {})
    row = {
        "call_id": call_sid,
        "plan": session.get("data", {}).get("plan", ""),
        "consent": session.get("data", {}).get("consent", ""),
        "recording_url": recording_url,
        "transcript": transcript,
        "ts": datetime.utcnow().isoformat()
    }

    table = f"{os.getenv('GCP_PROJECT')}.{os.getenv('BQ_DATASET')}.{os.getenv('BQ_TABLE')}"
    log.info(f"📊 Saving to BQ: {row}")

    errors = bq_client.insert_rows_json(table, [row])
    if errors:
        log.error(f"BigQuery insert errors: {errors}")
    else:
        log.info("✅ BQ insert done")

# ---- Send Email ----
def send_email(to_email, body):
    msg = MIMEText(body)
    msg["Subject"] = "New Voicebot Lead"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    s = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    s.login(EMAIL_SENDER, EMAIL_PASSWORD)
    s.send_message(msg)
    s.quit()
    log.info("📧 Email sent")

# ---- AI reply / state machine ----
def ai_reply(text, call_sid):
    session = sessions.get(call_sid, {"stage": "ask_plan", "data": {}})

    prompt = f"""
You are a telecom outbound sales AI.
User input: {text}
Current stage: {session['stage']}

Stages:
1) ask_plan → ask if customer wants Postpaid / Prepaid / Corporate plan
2) confirm_plan → repeat customer's choice & ask consent
3) capture_consent → proceed only if yes
"""

    response = model.generate_content(prompt)
    reply = response.text.strip()
    log.info(f"🤖 AI: {reply}")

    # Stage transitions
    if session["stage"] == "ask_plan":
        session["data"]["plan"] = text
        session["stage"] = "confirm_plan"

    elif session["stage"] == "confirm_plan":
        if "yes" in text.lower():
            session["data"]["consent"] = "yes"
            session["stage"] = "capture_consent"
        else:
            session["data"]["consent"] = "no"
            session["stage"] = "finished"
            reply = "Okay, no problem. Thank you for your time!"

    if "end" in text.lower() or "bye" in text.lower():
        session["stage"] = "finished"

    sessions[call_sid] = session
    return reply

# ---- Twilio Voice Route ----
@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid")
    speech = request.form.get("SpeechResult", "")

    log.info(f"🎙️ Heard: {speech}")

    reply = ai_reply(speech, call_sid)

    # If final stage → save lead, trigger recording + transcribe
    if sessions[call_sid]["stage"] == "capture_consent":
        session = sessions.get(call_sid, {})
        plan = session.get("data", {}).get("plan", "")
        consent = session.get("data", {}).get("consent", "")

        # Save lead (initial row) to BigQuery
        save_to_bq(call_sid)

        # Prepare an email notifying sales that lead captured (recording/transcript to follow)
        email_body = f"""
📞 New Lead Captured
Call ID: {call_sid}
Plan Interested: {plan}
Consent: {consent}

Recording and transcript (if available) will be posted once Twilio finishes processing.

Thanks,
Voicebot
        """
        send_email(SALES_EMAIL, email_body)

        # Ask the caller a final confirmation then record a short message for quality/transcript
        resp = VoiceResponse()
        resp.say("Thanks — we will record a short confirmation message for quality and compliance.")

        # Record (twilio will transcribe if transcribe=true) — adjust maxLength as needed
        resp.record(max_length=60, transcribe=True, transcribe_callback="/transcription", recording_status_callback="/recording")

        resp.say("Thank you! Goodbye.")
        resp.hangup()
        return Response(str(resp), mimetype="text/xml")

    # Continue conversation
    resp = VoiceResponse()
    gather = Gather(input="speech", action="/voice", speechTimeout="auto")
    gather.say(reply)
    resp.append(gather)
    return Response(str(resp), mimetype="text/xml")

# ---- Endpoint for Twilio recording status callback ----
@app.route("/recording", methods=["POST"])
def recording_webhook():
    recording_sid = request.form.get("RecordingSid")
    recording_url = request.form.get("RecordingUrl")
    call_sid = request.form.get("CallSid")

    log.info(f"🔔 Recording callback. CallSid={call_sid} RecordingSid={recording_sid} URL={recording_url}")

    # Save recording info to BigQuery and notify sales
    save_to_bq(call_sid, recording_url=recording_url)

    email_body = f"""
📥 Recording available
Call ID: {call_sid}
Recording URL: {recording_url}

(Transcript may follow when ready.)
"""
    send_email(SALES_EMAIL, email_body)
    return ("", 204)

# ---- Endpoint for Twilio transcription callback ----
@app.route("/transcription", methods=["POST"])
def transcription_webhook():
    transcription_text = request.form.get("TranscriptionText")
    recording_sid = request.form.get("RecordingSid")
    call_sid = request.form.get("CallSid")

    log.info(f"🔤 Transcription callback. CallSid={call_sid} RecordingSid={recording_sid}")
    log.info(f"Transcription preview: {transcription_text[:200]}")

    # Save transcript to BigQuery and notify sales with the transcript snippet
    save_to_bq(call_sid, transcript=transcription_text)

    email_body = f"""
📝 Transcript received
Call ID: {call_sid}
Transcript (first 1000 chars):
{(transcription_text or '')[:1000]}
"""
    send_email(SALES_EMAIL, email_body)
    return ("", 204)

@app.route("/", methods=["GET"])
def home():
    return "✅ Voicebot Server Running"

if __name__ == "__main__":
    print("🚀 Server: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
