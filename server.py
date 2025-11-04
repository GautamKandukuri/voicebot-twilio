import os
import logging
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from google.cloud import bigquery
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
import smtplib
from email.mime.text import MIMEText


load_dotenv()

PROJECT = os.getenv("GCP_PROJECT")
DATASET = os.getenv("BQ_DATASET")
TABLE = os.getenv("BQ_TABLE")

TABLE_FQN = TABLE if "." in TABLE else f"{PROJECT}.{DATASET}.{TABLE}"
print(f"✅ BigQuery table: {TABLE_FQN}")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
CUSTOMER_EMAIL = os.getenv("CUSTOMER_EMAIL")
SALES_REP_EMAIL = os.getenv("SALES_REP_EMAIL")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

SYSTEM_PROMPT = """
You are a telecom outbound voice assistant.
Rules:
- Never hang up until 3 silence attempts.
- Keep replies short & friendly.
- Ask one question each time.
"""

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voicebot")
bq_client = bigquery.Client()
sessions = {}

def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = MAIL_FROM
        msg["To"] = CUSTOMER_EMAIL

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(MAIL_FROM, [CUSTOMER_EMAIL, SALES_REP_EMAIL], msg.as_string())

        log.info("📧 Email sent")
    except:
        log.exception("Email failed")

def ai_reply(user_text, call_sid):
    if call_sid not in sessions:
        sessions[call_sid] = {"history": [], "retries": 0}

    sessions[call_sid]["history"].append(f"User: {user_text}")

    prompt = SYSTEM_PROMPT + f"\nUser said: {user_text}\nRespond:"
    try:
        chat = model.start_chat(history=[])
        resp = chat.send_message(prompt)
        reply = resp.text
    except:
        log.exception("Gemini error")
        reply = "Apologies, I'm having trouble right now."

    sessions[call_sid]["history"].append(f"Bot: {reply}")
    sessions[call_sid]["retries"] = 0
    return reply

def reprompt_on_silence(call_sid):
    s = sessions.setdefault(call_sid, {"history": [], "retries": 0})
    s["retries"] += 1

    if s["retries"] == 1:
        return "I didn’t hear you. Could you repeat that?"
    elif s["retries"] == 2:
        return "I’m still here. Do you want to explore better mobile plans?"
    else:
        return None

def save_row(call_sid):
    data = sessions.get(call_sid, {})
    row = {
        "lead_id": call_sid,
        "phone_e164": request.form.get("From", ""),
        "created_at": datetime.utcnow().isoformat(),
        "transcript": "\n".join(data.get("history", [])),
        "last_contacted": datetime.utcnow().isoformat(),
    }
    try:
        bq_client.insert_rows_json(TABLE_FQN, [row])
        log.info(f"✅ Saved lead {call_sid}")
    except:
        log.exception("BQ insert failed")

@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid")
    speech = request.form.get("SpeechResult", "").strip()

    if speech:
        reply = ai_reply(speech, call_sid)
        save_row(call_sid)

    else:
        retry = request.args.get("retry")
        if not retry:
            opening = (
                "Hi! This is an AI assistant from your telecom provider. "
                "Are you using prepaid or postpaid services currently?"
            )
            reply = ai_reply(opening, call_sid)
        else:
            reply = reprompt_on_silence(call_sid)
            if reply is None:
                save_row(call_sid)
                vr = VoiceResponse()
                vr.say("Thanks for your time. Goodbye.")
                return Response(str(vr), mimetype="text/xml")

    vr = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/voice",
        method="POST",
        speechTimeout="auto",
        speechModel="experimental_conversations",
        language="en-IN",
        timeout=5
    )
    gather.say(reply)
    vr.append(gather)
    vr.redirect("/voice?retry=1")
    return Response(str(vr), mimetype="text/xml")

@app.route("/call-ended", methods=["POST"])
def call_end():
    sid = request.form.get("CallSid")
    save_row(sid)
    send_email("Telecom Call Summary", f"Lead {sid} call ended")
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
