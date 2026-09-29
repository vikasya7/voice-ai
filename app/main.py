
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
    connection_alive = True

    try:

        while connection_alive:

            # --------------------------------------------------
            # RECEIVE MESSAGE FROM TWILIO
            # --------------------------------------------------

            try:
                message = await websocket.receive_json()

            except Exception as e:
                print(f"⚠️ WebSocket receive error: {e}")
                connection_alive = False
                break

            event = message.get("event")

            # ==================================================
            # CONNECTED
            # ==================================================

            if event == "connected":

                print("🔗 Twilio connected")

            # ==================================================
            # START
            # ==================================================

            elif event == "start":

                print("▶️ Stream started")

                stream_sid = message["start"]["streamSid"]

                session_id = stream_sid

                print(f"🆔 Session ID: {session_id}")

            # ==================================================
            # MEDIA
            # ==================================================

            elif event == "media":

                # --------------------------------------------------
                # Ignore caller audio while agent is speaking
                # --------------------------------------------------

                if agent_speaking:
                    continue

                payload = message["media"]["payload"]

                # --------------------------------------------------
                # Convert Twilio μ-law → PCM
                # --------------------------------------------------

                pcm_audio = twilio_ulaw_to_pcm(payload)

                # --------------------------------------------------
                # Voice activity detection
                # --------------------------------------------------

                speaking = is_speech(
                    pcm_audio,
                    SILENCE_THRESHOLD
                )

                # ==================================================
                # CALLER SPEAKING
                # ==================================================

                if speaking:

                    if not speech_detected:

                        print("🎤 Caller started speaking")

                    speech_detected = True

                    audio_buffer.extend(pcm_audio)

                    silence_chunks = 0

                # ==================================================
                # CALLER SILENT
                # ==================================================

                else:

                    if not speech_detected:
                        continue

                    silence_chunks += 1

                    audio_buffer.extend(pcm_audio)

                # ==================================================
                # DETECT END OF SPEECH
                # ==================================================

                if (
                    speech_detected
                    and silence_chunks >= SILENCE_CHUNKS_REQUIRED
                    and len(audio_buffer) >= MIN_AUDIO_BYTES
                ):

                    print("🤫 Caller stopped speaking")

                    print(
                        f"🎵 Audio size: {len(audio_buffer)} bytes"
                    )

                    # --------------------------------------------------
                    # Reset speech state immediately
                    # --------------------------------------------------

                    speech_detected = False
                    silence_chunks = 0

                    # --------------------------------------------------
                    # Copy audio and clear buffer
                    # --------------------------------------------------

                    audio_data = bytes(audio_buffer)

                    audio_buffer = bytearray()

                    # ==================================================
                    # CONVERT PCM → WAV
                    # ==================================================

                    try:

                        wav_audio = pcm_to_wav(audio_data)

                    except Exception as e:

                        print(
                            f"❌ PCM → WAV conversion failed: {e}"
                        )

                        continue

                    # ==================================================
                    # SPEECH TO TEXT
                    # ==================================================

                    try:

                        transcript = speech_to_text(
                            wav_audio,
                            filename="twilio_turn.wav"
                        )

                    except Exception as e:

                        print(
                            f"❌ Speech-to-text failed: {e}"
                        )

                        continue

                    print(f"📝 Transcript: {transcript}")

                    # --------------------------------------------------
                    # Ignore empty transcript
                    # --------------------------------------------------

                    if not transcript.strip():

                        print(
                            "⚠️ Empty transcript. Ignoring."
                        )

                        continue

                    # ==================================================
                    # CHECK CONNECTION BEFORE AGENT
                    # ==================================================

                    if not connection_alive:

                        print(
                            "⚠️ Call ended before agent processing."
                        )

                        break

                    # ==================================================
                    # SEND TO LANGGRAPH
                    # ==================================================

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

                    except Exception as e:

                        print(
                            f"❌ Agent processing failed: {e}"
                        )

                        continue

                    # ==================================================
                    # GET AGENT RESPONSE
                    # ==================================================

                    try:

                        response_text = (
                            result["messages"][-1].content
                        )

                    except Exception as e:

                        print(
                            f"❌ Could not get agent response: {e}"
                        )

                        continue

                    print(
                        f"🤖 Agent: {response_text}"
                    )

                    # ==================================================
                    # CHECK CONNECTION BEFORE TTS
                    # ==================================================

                    if not connection_alive:

                        print(
                            "⚠️ Call ended before TTS."
                        )

                        break

                    if not stream_sid:

                        print(
                            "⚠️ No stream SID. Skipping TTS."
                        )

                        continue

                    # ==================================================
                    # TEXT TO SPEECH
                    # ==================================================

                    try:

                        print(
                            "🔊 Generating TTS..."
                        )

                        agent_speaking = True

                        mp3_audio = text_to_speech(
                            response_text
                        )

                        print(
                            f"🔊 TTS size: "
                            f"{len(mp3_audio)} bytes"
                        )

                    except Exception as e:

                        print(
                            f"❌ TTS generation failed: {e}"
                        )

                        agent_speaking = False

                        continue

                    # ==================================================
                    # MP3 → μ-LAW
                    # ==================================================

                    try:

                        ulaw_audio = mp3_to_twilio_ulaw(
                            mp3_audio
                        )

                        print(
                            f"🎵 μ-law size: "
                            f"{len(ulaw_audio)} bytes"
                        )

                    except Exception as e:

                        print(
                            f"❌ Audio conversion failed: {e}"
                        )

                        agent_speaking = False

                        continue

                    # ==================================================
                    # SEND AUDIO TO TWILIO
                    # ==================================================

                    CHUNK_SIZE = 160

                    try:

                        for i in range(
                            0,
                            len(ulaw_audio),
                            CHUNK_SIZE
                        ):

                            # ------------------------------------------
                            # Check connection before every chunk
                            # ------------------------------------------

                            if not connection_alive:

                                print(
                                    "⚠️ Call ended "
                                    "while sending audio."
                                )

                                break

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

                        # ------------------------------------------
                        # Send mark only if connection is alive
                        # ------------------------------------------

                        if connection_alive:

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
                                "📞 Agent audio sent to Twilio"
                            )

                            print(
                                "⏳ Waiting for Twilio "
                                "playback to finish..."
                            )

                        else:

                            print(
                                "⚠️ Skipping mark "
                                "because call ended."
                            )

                            agent_speaking = False

                    except Exception as e:

                        print(
                            f"⚠️ Failed to send audio "
                            f"to Twilio: {e}"
                        )

                        connection_alive = False

                        agent_speaking = False

            # ==================================================
            # MARK
            # ==================================================

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

            # ==================================================
            # STOP
            # ==================================================

            elif event == "stop":

                print("🛑 Stream stopped")

                connection_alive = False

                agent_speaking = False

                break

    # ==========================================================
    # WEBSOCKET DISCONNECT
    # ==========================================================

    except WebSocketDisconnect:

        print(
            "📞 Caller disconnected "
            "(WebSocketDisconnect)"
        )

        connection_alive = False

    # ==========================================================
    # OTHER ERRORS
    # ==========================================================

    except Exception as e:

        print(
            f"❌ Media stream error: {e}"
        )

        connection_alive = False

    # ==========================================================
    # CLEANUP
    # ==========================================================

    finally:

        connection_alive = False

        agent_speaking = False

        audio_buffer.clear()

        print(
            "📞 Twilio Media Stream disconnected"
        )