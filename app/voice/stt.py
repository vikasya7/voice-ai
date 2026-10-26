
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
        model="gpt-transcribe",
        file=audio_file,
        language="en",
        prompt=(
            "English telephone conversation between a customer "
            "and a receptionist. Transcribe exactly what the "
            "caller says. Preserve names as spoken. Do not add "
            "words that are not audible."
        ),
    )

    print("📝 Recognized transcript:", repr(transcription.text))
    return transcription.text
