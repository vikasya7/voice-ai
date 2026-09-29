import base64
import audioop
import wave
from io import BytesIO

from pydub import AudioSegment


def twilio_ulaw_to_pcm(payload: str) -> bytes:
    ulaw_audio = base64.b64decode(payload)

    return audioop.ulaw2lin(
        ulaw_audio,
        2
    )


def pcm_to_wav(pcm_audio: bytes) -> bytes:
    buffer = BytesIO()

    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(pcm_audio)

    return buffer.getvalue()


def is_speech(
    pcm_audio: bytes,
    threshold: int = 1000
) -> bool:

    if not pcm_audio:
        return False

    rms = audioop.rms(
        pcm_audio,
        2
    )

    return rms > threshold


def mp3_to_twilio_ulaw(mp3_audio: bytes) -> bytes:
    """
    Convert MP3 audio into raw μ-law 8kHz mono audio
    required by Twilio Media Streams.
    """

    audio = AudioSegment.from_file(
        BytesIO(mp3_audio),
        format="mp3"
    )

    # Twilio requires:
    # 8 kHz
    # mono
    # 16-bit PCM before μ-law conversion

    audio = (
        audio
        .set_frame_rate(8000)
        .set_channels(1)
        .set_sample_width(2)
    )

    pcm_audio = audio.raw_data

    # PCM → μ-law
    ulaw_audio = audioop.lin2ulaw(
        pcm_audio,
        2
    )

    return ulaw_audio


def ulaw_to_base64(ulaw_audio: bytes) -> str:
    """
    Convert raw μ-law bytes to base64 string
    for Twilio Media Streams.
    """

    return base64.b64encode(
        ulaw_audio
    ).decode("ascii")