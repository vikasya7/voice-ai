
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from fastapi import UploadFile,File
from app.agent.graph import graph
from app.voice.stt import speech_to_text
from app.voice.tts import text_to_speech
from app.database.database import Base, engine
from app.database import models
from app.agent.tools import log_conversation
from fastapi.responses import Response

app = FastAPI(
    title="AI Voice Agent"
)

# Create database tables
Base.metadata.create_all(bind=engine)





class CallRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
def root():
    return {
        "message": "AI Voice Agent is running"
    }


@app.post("/call")
def handle_call(request: CallRequest):

    config = {
        "configurable": {
            "thread_id": request.session_id
        }
    }

    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content=request.message)
            ],
            "session_id": request.session_id,
        },
        config=config,
    )

    response_text = result["messages"][-1].content
    intent = result.get("intent")

    # Logging should never break the customer's request
    try:
        log_conversation.invoke({
            "session_id": request.session_id,
            "customer_message": request.message,
            "agent_response": response_text,
            "intent": intent,
        })
    except Exception as e:
        print(f"⚠️ Conversation logging failed: {e}")

    return {
        "intent": intent,
        "response": response_text,
    }

@app.post("/voice")
async def voice_call(
    session_id:str,
    audio:UploadFile=File(...)
):
    audio_bytes=await audio.read()

    #STT will go here
    transcript = speech_to_text(
        audio_bytes,
        filename=audio.filename or "audio.wav",
    )


    # Send transcript through existing receptionist
    config = {
        "configurable": {
            "thread_id": session_id
        }
    }


    result=graph.invoke(
        {
            "messages":[
                HumanMessage(content=transcript)
            ],
            "session_id":session_id
        },
        config=config
    )

    response_text=result["messages"][-1].content

    # log conversation
    try:
        log_conversation.invoke({
            "session_id": session_id,
            "customer_message": transcript,
            "agent_response": response_text,
            "intent": result.get("intent"),
        })
    except Exception as e:
        print(f" Conversation logging failed: {e}")

     # Text → speech
    audio_response = text_to_speech(response_text)

    return Response(
        content=audio_response,
        media_type="audio/mpeg",
        headers={
            "X-Transcript": transcript,
            "X-Intent": result.get("intent", ""),
        },
    )



from twilio.twiml.voice_response import VoiceResponse, Connect
from fastapi import WebSocket,WebSocketDisconnect


@app.post("/twilio/voice")
async def twilio_voice():

    print("🔥 TWILIO VOICE WEBHOOK HIT")

    response = VoiceResponse()

    connect = Connect()

    connect.stream(
        url="wss://plus-heat-ecosystem.ngrok-free.dev/media"
    )

    # IMPORTANT: add Connect to the response
    response.append(connect)

    print("📄 TwiML:")
    print(str(response))

    return Response(
        content=str(response),
        media_type="application/xml"
    )


import base64
import audioop
import wave
from io import BytesIO
from fastapi import WebSocket
from langchain_core.messages import HumanMessage

from app.voice.tts import text_to_speech
from app.voice.audio import (
    twilio_ulaw_to_pcm,
    pcm_to_wav,
    is_speech,
    mp3_to_twilio_ulaw,
    ulaw_to_base64,
)
import asyncio
@app.websocket("/media")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print("📞 Twilio Media Stream connected")

    audio_buffer = bytearray()
    silence_chunks = 0
    speech_detected = False

    SILENCE_THRESHOLD = 1000
    SILENCE_CHUNKS_REQUIRED = 40
    MIN_AUDIO_BYTES = 40000

    stream_sid = None
    session_id = None
    agent_speaking = False

    try:
        while True:

            # -----------------------------------
            # RECEIVE MESSAGE FROM TWILIO
            # -----------------------------------
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect as e:
                print(f"📞 Twilio WebSocket disconnected: code={e.code}")
                break
            except Exception as e:
                print(
                    f"⚠️ WebSocket receive error: "
                    f"{type(e).__name__}: {e}"
                )
                break

            event = message.get("event")

            # -----------------------------------
            # CONNECTED
            # -----------------------------------
            if event == "connected":

                print("🔗 Twilio connected")

            # -----------------------------------
            # START
            # -----------------------------------
            elif event == "start":

                print("▶️ Stream started")

                stream_sid = message["start"]["streamSid"]
                session_id = stream_sid

                print(f"🆔 Session ID: {session_id}")

            # -----------------------------------
            # INCOMING AUDIO
            # -----------------------------------
            elif event == "media":

                # Don't process caller audio while
                # agent audio is playing.
                if agent_speaking:
                    continue

                payload = message["media"]["payload"]

                # Twilio μ-law → PCM
                pcm_audio = twilio_ulaw_to_pcm(payload)

                speaking = is_speech(
                    pcm_audio,
                    SILENCE_THRESHOLD
                )

                # -----------------------------------
                # CALLER IS SPEAKING
                # -----------------------------------
                if speaking:

                    if not speech_detected:
                        print("🎤 Caller started speaking")

                    speech_detected = True

                    audio_buffer.extend(pcm_audio)

                    silence_chunks = 0

                # -----------------------------------
                # SILENCE
                # -----------------------------------
                else:

                    if not speech_detected:
                        continue

                    silence_chunks += 1

                    # Keep the silence at the end of
                    # the caller's sentence.
                    audio_buffer.extend(pcm_audio)

                # -----------------------------------
                # CALLER FINISHED SPEAKING
                # -----------------------------------
                if (
                    speech_detected
                    and silence_chunks >= SILENCE_CHUNKS_REQUIRED
                    and len(audio_buffer) >= MIN_AUDIO_BYTES
                ):

                    print("🤫 Caller stopped speaking")

                    print(
                        f"🎵 Audio size: "
                        f"{len(audio_buffer)} bytes"
                    )

                    # -----------------------------------
                    # COPY AUDIO AND RESET BUFFER
                    # -----------------------------------

                    current_audio = bytes(audio_buffer)

                    audio_buffer = bytearray()
                    silence_chunks = 0
                    speech_detected = False

                    # -----------------------------------
                    # PCM → WAV
                    # -----------------------------------

                    wav_audio = pcm_to_wav(current_audio)

                    # -----------------------------------
                    # SPEECH TO TEXT
                    # -----------------------------------

                    try:

                        transcript = speech_to_text(
                            wav_audio,
                            filename="twilio_turn.wav"
                        )

                        print(
                            f"📝 Transcript: {transcript}"
                        )

                    except Exception as e:

                        print(
                            f"❌ STT error: "
                            f"{type(e).__name__}: {e}"
                        )

                        continue

                    if not transcript.strip():
                        print("⚠️ Empty transcript")
                        continue

                    # -----------------------------------
                    # LANGGRAPH
                    # -----------------------------------

                    try:

                        print(
                            "🧠 Sending transcript to agent..."
                        )

                        config = {
                            "configurable": {
                                "thread_id": session_id
                            }
                        }

                        result = graph.invoke(
                            {
                                "messages": [
                                    HumanMessage(
                                        content=transcript
                                    )
                                ],
                                "session_id": session_id,
                            },
                            config=config,
                        )

                        response_text = (
                            result["messages"][-1].content
                        )

                        print(
                            f"🤖 Agent: {response_text}"
                        )

                    except Exception as e:

                        print(
                            f"❌ Agent error: "
                            f"{type(e).__name__}: {e}"
                        )

                        continue

                    # -----------------------------------
                    # TTS
                    # -----------------------------------

                    try:

                        print("🔊 Generating TTS...")

                        agent_speaking = True

                        mp3_audio = text_to_speech(
                            response_text
                        )

                        print(
                            f"🔊 TTS size: "
                            f"{len(mp3_audio)} bytes"
                        )

                    except Exception as e:

                        agent_speaking = False

                        print(
                            f"❌ TTS error: "
                            f"{type(e).__name__}: {e}"
                        )

                        continue

                    # -----------------------------------
                    # MP3 → μ-LAW
                    # -----------------------------------

                    try:

                        ulaw_audio = mp3_to_twilio_ulaw(
                            mp3_audio
                        )

                        print(
                            f"🎵 μ-law size: "
                            f"{len(ulaw_audio)} bytes"
                        )

                    except Exception as e:

                        agent_speaking = False

                        print(
                            f"❌ Audio conversion error: "
                            f"{type(e).__name__}: {e}"
                        )

                        continue

                    # -----------------------------------
                    # SEND AUDIO TO TWILIO
                    # -----------------------------------

                    try:

                        CHUNK_SIZE = 160

                        print(
                            "📤 Sending agent audio..."
                        )

                        for i in range(
                            0,
                            len(ulaw_audio),
                            CHUNK_SIZE
                        ):

                            chunk = ulaw_audio[
                                i:i + CHUNK_SIZE
                            ]

                            payload = ulaw_to_base64(
                                chunk
                            )

                            await websocket.send_json(
                                {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": payload
                                    },
                                }
                            )

                            # 160 bytes of 8kHz μ-law
                            # = 20 milliseconds.
                            await asyncio.sleep(0.02)

                        print(
                            "📞 Agent audio sent to Twilio"
                        )

                    except WebSocketDisconnect as e:

                        print(
                            f"❌ WebSocket disconnected "
                            f"while sending audio: "
                            f"code={e.code}"
                        )

                        break

                    except Exception as e:

                        print(
                            f"❌ Audio send error: "
                            f"{type(e).__name__}: {e}"
                        )

                        break

                    # -----------------------------------
                    # MARK
                    # -----------------------------------

                    try:

                        print(
                            "📍 Sending playback mark..."
                        )

                        await websocket.send_json(
                            {
                                "event": "mark",
                                "streamSid": stream_sid,
                                "mark": {
                                    "name": "agent_response"
                                },
                            }
                        )

                        print(
                            "⏳ Waiting for Twilio "
                            "playback to finish..."
                        )

                    except Exception as e:

                        print(
                            f"❌ Mark send error: "
                            f"{type(e).__name__}: {e}"
                        )

                        break

            # -----------------------------------
            # TWILIO MARK
            # -----------------------------------
            elif event == "mark":

                mark_name = (
                    message
                    .get("mark", {})
                    .get("name")
                )

                print(
                    f"✅ Twilio finished playing: "
                    f"{mark_name}"
                )

                if mark_name == "agent_response":

                    agent_speaking = False

                    print(
                        "🎤 Listening for caller..."
                    )

            # -----------------------------------
            # TWILIO STOP
            # -----------------------------------
            elif event == "stop":

                print("🛑 Stream stopped")

                break

            # -----------------------------------
            # OTHER EVENTS
            # -----------------------------------
            else:

                print(
                    f"ℹ️ Twilio event: {event}"
                )

    except WebSocketDisconnect as e:

        print(
            f"📞 Twilio WebSocket disconnected: "
            f"code={e.code}"
        )

    except Exception as e:

        print(
            f"❌ Media stream error: "
            f"{type(e).__name__}: {e}"
        )

    finally:

        agent_speaking = False

        print(
            "📞 Twilio Media Stream disconnected"
        )