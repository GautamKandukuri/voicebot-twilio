# realtime_server.py
import os
import logging
import base64
import uuid
import asyncio
import json
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import texttospeech_v1 as tts
from google.cloud import bigquery
import google.generativeai as genai
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import aiofiles

# Load environment
load_dotenv()
LOG = logging.getLogger("realtime_voice")
logging.basicConfig(level=logging.INFO)

# Config
PROJECT = os.getenv("GCP_PROJECT")
DATASET = os.getenv("BQ_DATASET")
TABLE = os.getenv("BQ_TABLE")
TABLE_FQN = TABLE if "." in TABLE else f"{PROJECT}.{DATASET}.{TABLE}"
print("BigQuery table:", TABLE_FQN)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Email
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
CUSTOMER_EMAIL = os.getenv("CUSTOMER_EMAIL")
SALES_REP_EMAIL = os.getenv("SALES_REP_EMAIL")

# Clients
speech_client = speech.SpeechClient()
tts_client = tts.TextToSpeechClient()
bq_client = bigquery.Client()
genai.configure(api_key=GEMINI_KEY)

# Gemini model to use (text-based; for realtime voice you'd later swap to Gemini Realtime)
GENIE_MODEL_NAME = "gemini-2.0-flash"  # keep validated name

# FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory call sessions (demo). Production: persistent store.
# Each session holds: buffer bytes, transcript list, retries, call metadata
sessions: Dict[str, Dict[str, Any]] = {}

# audio folder
AUDIO_DIR = "/tmp/voicebot_tts"
os.makedirs(AUDIO_DIR, exist_ok=True)


# ---------------------
# Helpers
# ---------------------
def send_email(subject: str, body: str):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = MAIL_FROM
        msg["To"] = CUSTOMER_EMAIL
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(MAIL_FROM, [CUSTOMER_EMAIL, SALES_REP_EMAIL], msg.as_string())
        LOG.info("Email sent to customer & sales rep")
    except Exception:
        LOG.exception("Failed to send email")


async def save_to_bigquery(call_sid: str):
    s = sessions.get(call_sid, {})
    transcript = "\n".join(s.get("transcript", []))
    row = {
        "lead_id": call_sid,
        "phone_e164": s.get("from", ""),
        "created_at": datetime.utcnow().isoformat(),
        "transcript": transcript,
        "last_contacted": datetime.utcnow().isoformat(),
    }
    try:
        errors = bq_client.insert_rows_json(TABLE_FQN, [row])
        if errors:
            LOG.error("BigQuery insert errors: %s", errors)
        else:
            LOG.info("Inserted call to BigQuery: %s", call_sid)
    except Exception:
        LOG.exception("BigQuery insert failed")


def synthesize_tts_and_save(text: str, call_sid: str, idx: int) -> str:
    """Synthesize text to MP3 with Google TTS and return file path accessible by /audio/{fname}"""
    input_text = tts.SynthesisInput(text=text)
    # Choose a voice suited to locale; keep simple
    voice = tts.VoiceSelectionParams(language_code="en-IN", ssml_gender=tts.SsmlVoiceGender.NEUTRAL)
    audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3)

    response = tts_client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)

    fname = f"tts_{call_sid}_{idx}.mp3"
    fpath = os.path.join(AUDIO_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(response.audio_content)
    LOG.info("Saved TTS to %s", fpath)
    return fname


def call_gemini_reply(text: str, call_sid: str) -> str:
    """Send short system prompt + user text to Gemini via genai lib and return short reply text."""
    system = (
        "You are an outbound telecom sales assistant. Keep replies short (1-2 sentences) "
        "and always ask a relevant follow-up question. Be friendly."
    )
    try:
        chat = genai.GenerativeModel(GENIE_MODEL_NAME)  # create ephemeral model object
        # Use start_chat/send_message pattern (as in user's environment)
        conv = chat.start_chat(history=[])
        resp = conv.send_message(f"{system}\nUser: {text}\nReply briefly and ask a follow-up.")
        return resp.text if hasattr(resp, "text") else str(resp)
    except Exception:
        LOG.exception("Gemini error")
        return "Sorry, I'm having trouble responding right now."


# ---------------------
# Twilio WebSocket (Media Streams)
# ---------------------
@app.websocket("/twilio/media")
async def media_ws(ws: WebSocket):
    """
    Endpoint that Twilio will open a WebSocket to for Media Streams.
    Twilio sends JSON frames containing 'event' (start, media, stop).
    See Twilio Media Streams docs for the format.
    """
    await ws.accept()
    call_sid = None
    tts_count = 0
    LOG.info("WebSocket client connected")

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            event = msg.get("event")
            if event == "start":
                # Twilio start contains connection info
                call_sid = msg.get("start", {}).get("callSid") or str(uuid.uuid4())
                from_num = msg.get("start", {}).get("from")
                LOG.info("Stream start for call %s from %s", call_sid, from_num)
                sessions[call_sid] = {
                    "buffer": bytearray(), "transcript": [], "retries": 0, "from": from_num
                }
                # Optionally say a greeting by generating TTS and instruct Twilio to play it via the TwiML call flow
                # But Twilio Media Streams doesn't push audio to the caller automatically; we'll respond with short messages via Twilio calls or create an audio URL and ask Twilio to play it (see notes).
                continue

            if event == "media":
                # Twilio media payload: base64 audio in msg['media']['payload']
                payload_b64 = msg.get("media", {}).get("payload", "")
                if not payload_b64:
                    continue
                pcm_bytes = base64.b64decode(payload_b64)
                # Append to buffer for the call
                sessions[call_sid]["buffer"].extend(pcm_bytes)

                # When buffer exceeds threshold (approx 1.4s worth at 8kHz 16-bit),
                # run quick STT on chunk and generate a reply.
                # Note: Twilio audio is usually 16-bit PCM, 8k or 16k. We'll assume 8k (narrowband).
                # Buffer threshold: 1.5 seconds => 8000 samples/sec * 2 bytes/sample * 1.5 = 24000 bytes
                CHUNK_BYTES = 24000
                if len(sessions[call_sid]["buffer"]) >= CHUNK_BYTES:
                    # take the chunk and reset buffer
                    chunk = bytes(sessions[call_sid]["buffer"][:CHUNK_BYTES])
                    del sessions[call_sid]["buffer"][:CHUNK_BYTES]

                    # Prepare a short recognition request (synchronous). For lower latency use streaming gRPC
                    try:
                        audio = speech.RecognitionAudio(content=chunk)
                        config = speech.RecognitionConfig(
                            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                            sample_rate_hertz=8000,
                            language_code="en-IN",
                            enable_automatic_punctuation=True,
                        )
                        # This is a short synchronous call. If you need lower latency, use streaming_recognize.
                        resp = speech_client.recognize(config=config, audio=audio, timeout=15)
                        transcript = ""
                        for result in resp.results:
                            transcript += result.alternatives[0].transcript + " "
                        transcript = transcript.strip()
                        LOG.info("Transcribed chunk for %s: %s", call_sid, transcript)
                    except Exception:
                        LOG.exception("STT error")
                        transcript = ""

                    if transcript:
                        # save transcript
                        sessions[call_sid]["transcript"].append(f"User: {transcript}")

                        # call Gemini for reply (text)
                        reply_text = call_gemini_reply(transcript, call_sid)
                        sessions[call_sid]["transcript"].append(f"Bot: {reply_text}")
                        LOG.info("Gemini reply: %s", reply_text)

                        # synthesize reply to MP3 and put into accessible file
                        tts_count += 1
                        fname = synthesize_tts_and_save(reply_text, call_sid, tts_count)
                        audio_url = f"{get_base_url()}/audio/{fname}"

                        # Send an instruction back to Twilio via WebSocket to play the audio file:
                        # Twilio Media Streams doesn't have a direct 'play' control in the same WS channel;
                        # Instead, you can instruct the main TwiML call to fetch the audio URL via <Play>.
                        # If you are controlling call via REST (or TwiML app) you can use the REST API to update Call TwiML to play the generated audio.
                        # For simplicity here, we send a JSON back to whichever client is listening (this is demo).
                        await ws.send_text(json.dumps({"event": "bot_reply", "text": reply_text, "audio_url": audio_url}))
                    else:
                        # silence/no transcript — increment retries and maybe reprompt
                        sessions[call_sid]["retries"] += 1
                        if sessions[call_sid]["retries"] >= 3:
                            # end of conversation due to silence — save and email then break
                            await save_to_bigquery(call_sid)
                            send_email("Call summary", f"Call {call_sid} ended due to silence")
                            LOG.info("Ending call due to silence: %s", call_sid)
                            await ws.send_text(json.dumps({"event": "end_call", "reason": "no_response"}))
                            # notifying Twilio to hangup must be done via Twilio REST API (not in this WS)
                    # end if chunk processed

                continue

            if event == "stop":
                call_sid = msg.get("stop", {}).get("callSid") or call_sid
                LOG.info("Stream stopped for call %s", call_sid)
                # finalize: save to BigQuery, send email
                await save_to_bigquery(call_sid)
                send_email("Telecom Bot Call Summary", f"Call {call_sid} completed")
                # cleanup session
                sessions.pop(call_sid, None)
                # break the loop and close
                await ws.close()
                break

            # If unknown event, just log
            LOG.debug("Unhandled event: %s", msg)

    except WebSocketDisconnect:
        LOG.info("WebSocket disconnected for call %s", call_sid)
    except Exception:
        LOG.exception("WS error")
    finally:
        # cleanup: attempt final save
        if call_sid and call_sid in sessions:
            try:
                await save_to_bigquery(call_sid)
            except Exception:
                LOG.exception("Final save failed")
            sessions.pop(call_sid, None)


# ---------------------
# Static audio serve
# ---------------------
@app.get("/audio/{fname}")
async def serve_audio(fname: str):
    path = os.path.join(AUDIO_DIR, fname)
    if not os.path.exists(path):
        return PlainTextResponse("Not found", status_code=404)
    return FileResponse(path, media_type="audio/mpeg")


# ---------------------
# Utility route: provide TwiML snippet for starting media stream
# ---------------------
@app.post("/twiml/start_media")
async def twiml_start(request: Request):
    """
    Returns TwiML to start a Media Stream (for testing).
    Twilio should POST here for the call; use this TwiML as Voice webhook for the phone number or call.
    """
    # Construct the WebSocket URL Twilio should connect to.
    # Twilio requires a wss URL (ngrok will provide wss on the same https host).
    base = get_base_url()
    wss = base.replace("https://", "wss://").replace("http://", "ws://")
    # Twilio Media Streams docs show how to create the <Start><Stream url="wss://..."/></Start>
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Start>
    <Stream url="{wss}/twilio/media"/>
  </Start>
  <Say>Connecting you to the automated assistant. Please wait.</Say>
  <Pause length="60"/>
  <Say>Goodbye.</Say>
</Response>
"""
    return PlainTextResponse(content=twiml, media_type="application/xml")


# ---------------------
# Helper get_base_url
# ---------------------
def get_base_url() -> str:
    # Prefer NGROK_URL env if set; else guess local
    ngrok = os.getenv("PUBLIC_URL") or os.getenv("NGROK_URL")
    if ngrok:
        return ngrok.rstrip("/")
    # Fallback
    host = os.getenv("HOST_PUBLIC", "https://localhost:5000")
    return host.rstrip("/")

# ---------------------
# Root
# ---------------------
@app.get("/")
async def root():
    return {"status": "ok", "help": "Use /twiml/start_media to get a TwiML snippet, and point Twilio to it."}
