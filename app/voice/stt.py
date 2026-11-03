import os
from io import BytesIO

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
client = SarvamAI(
    api_subscription_key=os.environ["SARVAM_API_KEY"]
)


def speech_to_text(
    audio_bytes: bytes,
    filename: str = "audio.wav"
) -> str:
    audio_file = BytesIO(audio_bytes)
    audio_file.name = filename

    transcription=client.speech_to_text.transcribe(
        file=audio_file,
        model="saaras:v4",
        language_code="hi-IN",
        mode="codemix"
    )


    transcript=transcription.transcript 

    print("📝 Sarvam transcript:", repr(transcript))

    return transcript
