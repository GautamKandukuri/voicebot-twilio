from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()

input_text = texttospeech.SynthesisInput(text="Hola, su solicitud fue recibida.")

voice = texttospeech.VoiceSelectionParams(
    language_code="es-ES",
    name="es-ES-Standard-A"
)

audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3
)

response = client.synthesize_speech(
    input=input_text,
    voice=voice,
    audio_config=audio_config
)

with open("output_es.mp3", "wb") as out:
    out.write(response.audio_content)

print("✅ Audio saved: output_es.mp3")
