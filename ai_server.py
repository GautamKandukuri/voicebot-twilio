from flask import Flask, request, jsonify
import google.generativeai as genai
import os

app = Flask(__name__)

# Load GEMINI API KEY from env
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-2.5-pro")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    user_message = data.get("text", "").strip()

    # ✅ Fix: Handle empty speech input from Twilio
    if not user_message:
        return jsonify({
            "reply": "I didn't catch that. Could you please repeat?"
        })

    try:
        response = model.generate_content(user_message)
        bot_reply = response.text.strip()
    except Exception as e:
        print("Gemini Error:", e)
        bot_reply = "Sorry, I had trouble processing your request. Please repeat that."

    return jsonify({"reply": bot_reply})

if __name__ == "__main__":
    print("✅ AI server is running on http://localhost:8000/generate")
    app.run(host="0.0.0.0", port=8000)
