# Voicebot POC (Gemini-2.5-Flash TTS, BigQuery, Twilio) - MacBook
This repository contains a beginner-friendly POC for an outbound voice bot using:
- Google Vertex AI (Gemini-2.5-Flash TTS)
- BigQuery (lead storage)
- Twilio (outbound call integration - POC)
- Python 3.10+, VS Code on macOS

See the .env.example for required environment variables.

Steps:
1. Install Python 3.10 via Homebrew
2. Create virtualenv and install requirements
3. Configure GOOGLE_APPLICATION_CREDENTIALS and GCP_PROJECT
4. Fill .env with TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER
5. Run `python main.py`
