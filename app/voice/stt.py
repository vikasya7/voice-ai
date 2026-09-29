from io import BytesIO
from openai import OpenAI

client = OpenAI()


def speech_to_text(
    audio_bytes: bytes,
    filename: str = "audio.wav"
) -> str:

    audio_file = BytesIO(audio_bytes)
    audio_file.name = filename

    transcription = client.audio.transcriptions.create(
    model="gpt-4o-mini-transcribe",
    file=audio_file,
    language="en",
    prompt=(
        "This is an English telephone conversation between "
        "a customer and a receptionist.\n"
        "Transcribe the caller's speech in English.\n"
        "Do not translate English speech into another language "
        "or script.\n"
        "For people's names, preserve the likely English spelling.\n"
        "For phone numbers, write the digits clearly.\n"
        "Do not invent words."
    ),
)

    return transcription.text