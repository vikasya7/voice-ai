from io import BytesIO
import os
import base64

from openai import OpenAI

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
client = SarvamAI(
    api_subscription_key=os.environ["SARVAM_API_KEY"]
)


def text_to_speech(
    text: str,
    filename: str = "response.mp3",
) -> bytes:
    """
    Convert Hinglish text into speech using Sarvam Bulbul.
    Returns MP3 audio bytes for the existing Twilio pipeline.
    """

    response = client.text_to_speech.convert(
        model="bulbul:v4-flash",
        language_code="hi-IN",
        speaker="simran_enhi_customer",
        text=text,
        speech_sample_rate=8000,
        output_audio_codec="mp3",
        pace=1.0,
    )

    audio_bytes = base64.b64decode(
        "".join(response.audios)
    )

    print("🔊 Sarvam TTS generated:", len(audio_bytes), "bytes")

    return audio_bytes