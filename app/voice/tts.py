from io import BytesIO

from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()
client = OpenAI()


def text_to_speech(
    text: str,
    filename: str = "response.mp3",
) -> bytes:
    """
    Convert text into speech audio.
    """

    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text,
        response_format="mp3",
    )

    audio_bytes = response.read()

    return audio_bytes