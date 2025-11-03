# project_root/vertex_tts.py
"""
Vertex TTS wrapper for Gemini TTS models.
Uses google-cloud-aiplatform where possible. For compatibility, we also include a minimal REST example commented.
"""
from google.cloud import texttospeech

class VertexTTS:
    def __init__(self, model_id="text-to-speech"):
        self.client = texttospeech.TextToSpeechClient()

    def synthesize_text_to_audio(self, text, output_format="MP3", voice="es-ES-Standard-A"):
        input_text = texttospeech.SynthesisInput(text=text)

        voice_params = texttospeech.VoiceSelectionParams(
            language_code=voice.split("-")[0] + "-" + voice.split("-")[1],
            name=voice
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
            if output_format.upper() == "MP3"
            else texttospeech.AudioEncoding.LINEAR16
        )

        response = self.client.synthesize_speech(
            input=input_text,
            voice=voice_params,
            audio_config=audio_config
        )

        return response.audio_content
