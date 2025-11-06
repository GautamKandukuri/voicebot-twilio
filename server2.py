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

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voicebot")

# Model
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

# BigQuery
PROJECT = os.getenv("GCP_PROJECT")
DATASET = os.getenv("BQ_DATASET")
TABLE = os.getenv("BQ_TABLE")

bq_client = bigquery.Client(project=PROJECT)

# Session storage
sessions = {}

EXIT_PHRASES = ["bye", "thank you", "stop", "no more", "that is all", "done"]

def ai_reply(user_text, call_sid):
    """LLM — Controlled conversational agent"""
    
    # Initialize session
    if call_sid not in sessions:
        sessions[call_sid] = {"history": [], "stage": "intro"}

    # Detect if user wants to exit
    if any(x in user_text.lower() for x in EXIT_PHRASES):
        return "Thank you for your time. We will contact you soon.", True

    history = sessions[call_sid]["history"]

    prompt = f"""
You are an outbound insurance advisor.
Rules:
- DO NOT end the call unless user clearly ends it.
- ALWAYS ask one question at a time.
- Keep replies short (max 2 sentences).
- Maintain friendly tone.
- If user sounds confused, ask clarifying questions.
- If user interrupts, stop speaking and listen.
- Keep conversation focused on eligibility questions.
- If user gives irrelevant answer, politely redirect.

Conversation history:
{history}

User: {user_text}
Assistant:"""

    try:
        reply = model.generate_content(prompt).text.strip()
    except:
        reply = "Sorry, I didn't catch that. Could you please repeat?"

    # Save memory
    sessions[call_sid]["history"].append({"user": user_text, "assistant": reply})

    return reply, False


@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid")
    user_input = request.form.get("SpeechResult", "")

    reply, should_end = ai_reply(user_input, call_sid)

    response = VoiceResponse()

    if should_end:
        response.say(reply)
        response.hangup()
        return str(response)

    gather = Gather(
        input="speech",
        action="/voice",
        speech_timeout="auto",
        bargeIn="true"  # ✅ INTERRUPT READY
    )
    gather.say(reply)
    response.append(gather)

    return str(response)


@app.route("/save", methods=["POST"])
def save():
    call_sid = request.form.get("CallSid")
    session = sessions.get(call_sid, {})
    history = session.get("history", [])

    transcript = "\n".join([f"User: {h['user']} | Bot: {h['assistant']}" for h in history])

    row = {
        "call_id": call_sid,
        "timestamp": datetime.utcnow().isoformat(),
        "transcript": transcript
    }

    table_id = f"{PROJECT}.{DATASET}.{TABLE}"
    errors = bq_client.insert_rows_json(table_id, [row])

    if not errors:
        log.info("✅ Saved transcript to BigQuery")
    else:
        log.error(f"❌ BQ insert error: {errors}")

    return Response("OK", status=200)
