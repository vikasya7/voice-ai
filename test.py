from app.voice.tts import text_to_speech
from dotenv import load_dotenv
load_dotenv()

text = "Hello! Your appointment has been confirmed."

audio_bytes = text_to_speech(text)

with open("test_response.mp3", "wb") as f:
    f.write(audio_bytes)

print("TTS generated successfully.")
print(f"Audio size: {len(audio_bytes)} bytes")