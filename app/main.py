
import logging

from fastapi import FastAPI, Request
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

class _AccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn logs the request target, including any query parameters.
        args = record.args
        if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str):
            client, method, target, version, status = args
            record.args = (client, method, target.partition("?")[0], version, status)
        return True


logging.getLogger("uvicorn.access").addFilter(_AccessLogFilter())

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






import re

def split_response_and_sources(response_text: str):
    # Extract URLs before cleaning the response.
    urls = re.findall(r"https?://[^\s<>\])\",]+", response_text)
    sources = list(dict.fromkeys(urls))

    spoken_response = response_text

    # Remove URLs from the spoken text.
    spoken_response = re.sub(
        r"https?://[^\s<>\])\",]+",
        "",
        spoken_response,
    )

    # Remove empty citation placeholders: (), ( and ), etc.
    spoken_response = re.sub(
        r"\(\s*(?:and\s*)*\)",
        "",
        spoken_response,
        flags=re.IGNORECASE,
    )

    # Remove Markdown heading and bullet formatting.
    spoken_response = re.sub(r"(?m)^\s*#{1,6}\s*", "", spoken_response)
    spoken_response = re.sub(r"(?m)^\s*[-*]\s+", "", spoken_response)

    # Remove repeated whitespace and excess blank lines.
    spoken_response = re.sub(r"[ \t]+", " ", spoken_response)
    spoken_response = re.sub(r"\n{2,}", "\n", spoken_response)
    spoken_response = spoken_response.strip()

    return spoken_response, sources




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

    response_text = result.get(
    "assistant_response",
    result["messages"][-1].content,
)
    spoken_response = result.get(
    "spoken_response",
    response_text,
    )
    sources = result.get("sources", [])
    intent = result.get("intent")

    # Logging should never break the customer's request.
    try:
        log_conversation.invoke({
            "session_id": request.session_id,
            "customer_message": request.message,
            "agent_response": response_text,
            "intent": intent,
        })
    except Exception as e:
        print(f"⚠️ Conversation logging failed: {type(e).__name__}")

    return {
        "intent": intent,
        "response": spoken_response,
        "spoken_response": spoken_response,
        "sources": sources,
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
        print(f" Conversation logging failed: {type(e).__name__}")

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



from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse, Connect
from fastapi import WebSocket,WebSocketDisconnect

import re
@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    if not TWILIO_AUTH_TOKEN or not NGROK_DOMAIN:
        raise HTTPException(status_code=503, detail="Twilio webhook is not configured.")

    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")

    # Twilio signs the public HTTPS URL, which may differ from the proxy's URL.
    raw_path = request.scope.get("raw_path") or request.url.path.encode("ascii")
    public_url = f"https://{NGROK_DOMAIN}{raw_path.decode('ascii')}"
    query = request.scope["query_string"]
    if query:
        public_url += "?" + query.decode("ascii")

    async with request.form() as form:
        if not RequestValidator(TWILIO_AUTH_TOKEN).validate(public_url, form, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature.")

    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{NGROK_DOMAIN}/media")
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")



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




async def send_agent_audio(websocket, stream_sid, ulaw_audio):
    chunk_size = 160

    try:
        print("📤 Sending agent audio...")

        for i in range(0, len(ulaw_audio), chunk_size):
            chunk = ulaw_audio[i:i + chunk_size]
            payload = ulaw_to_base64(chunk)

            await websocket.send_json({
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": payload
                }
            })

            await asyncio.sleep(0.02)

        await websocket.send_json({
            "event": "mark",
            "streamSid": stream_sid,
            "mark": {
                "name": "agent_response"
            }
        })

        print("✅ Agent audio sent; waiting for playback mark")

    except Exception as e:
        print(f"❌ Audio sending failed: {type(e).__name__}")


# for reference
#Event	Meaning
#connected	Twilio's WebSocket connection is established
#start	The audio stream has started
#media	A chunk of audio has arrived
#mark	A previously marked audio playback point has been reached
#stop	The audio stream has stopped



import asyncio
@app.websocket("/media")
async def media_stream(websocket: WebSocket):
    signature = websocket.headers.get("X-Twilio-Signature")
    if not TWILIO_AUTH_TOKEN or not NGROK_DOMAIN or not signature or websocket.url.query:
        await websocket.close(code=1008)
        return

    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    # The upgrade may be signed as an HTTPS or WSS URL. Twilio also
    # documents a trailing-slash variant for voice stream handshakes.
    public_urls = (f"https://{NGROK_DOMAIN}/media", f"wss://{NGROK_DOMAIN}/media")
    if not any(
        validator.validate(url + suffix, {}, signature)
        for url in public_urls
        for suffix in ("", "/")
    ):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    print("📞 Twilio Media Stream connected")

    audio_buffer = bytearray()
    silence_chunks = 0
    speech_detected = False

    SILENCE_THRESHOLD = 1000
    SILENCE_CHUNKS_REQUIRED = 40
    MIN_AUDIO_BYTES = 4000

    stream_sid = None
    session_id = None
    agent_speaking = False
    initial_greeting_sent = False
    awaiting_outbound_confirmation = False

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
                    f"{type(e).__name__}"
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


                # call type
                custom_parameters=(
                    message["start"]
                    .get("customParameters",{})
                )
                call_type=custom_parameters.get(
                    "call_type",
                    "inbound"
                )
                print("📞 Call type:", "outbound" if call_type == "outbound" else "inbound")


                if not initial_greeting_sent:
                    initial_greeting_sent = True
                    if call_type == "outbound":
                        awaiting_outbound_confirmation = True
                        greeting = (
                            "Hi, this is the VIKAS AI assistant. "
                            "I'm calling to speak with you. "
                            "Is this a good time to talk?"
                        )
                    else:
                        greeting = "Hi, this is the VIKAS AI assistant. How can I help you today?"

                    print("📞 Sending initial greeting")
                    agent_speaking = True
                    mp3_audio = text_to_speech(greeting)
                    ulaw_audio = mp3_to_twilio_ulaw(mp3_audio)
                    audio_task = asyncio.create_task(
                        send_agent_audio(websocket, stream_sid, ulaw_audio)
                    )

            # -----------------------------------
            # INCOMING AUDIO
            # -----------------------------------
            elif event == "media":

                payload = message["media"]["payload"]
                pcm_audio = twilio_ulaw_to_pcm(payload)


                speaking = is_speech(
                  pcm_audio,
                  SILENCE_THRESHOLD
                )

                # Handle caller speech
                if speaking:
                     # Interrupt agent audio only when a new utterance starts
                    if agent_speaking and not speech_detected:
                        print("🛑 Caller interrupted agent")

                        if audio_task and not audio_task.done():

                            audio_task.cancel()

                            try:
                                  await audio_task
                            except asyncio.CancelledError:
                                 pass

                        await websocket.send_json({
                                "event": "clear",
                                "streamSid": stream_sid
                        })

                        agent_speaking = False
                        audio_buffer = bytearray()
                        silence_chunks = 0

                    if not speech_detected:
                        print("🎤 Caller started speaking")
                    speech_detected=True
                    audio_buffer.extend(pcm_audio)
                    silence_chunks=0

                    # Caller is silent
                else:
                       
                    if not speech_detected:
                        continue

                    silence_chunks += 1
                    audio_buffer.extend(pcm_audio)

                if (
                        speech_detected
                         and silence_chunks >= SILENCE_CHUNKS_REQUIRED
                         and len(audio_buffer) >= MIN_AUDIO_BYTES
                ):
                        
                    print("🤫 Caller stopped speaking")
                    print(f"🎵 Audio size: {len(audio_buffer)} bytes")

                    current_audio = bytes(audio_buffer)
                    audio_buffer = bytearray()
                    silence_chunks = 0
                    speech_detected = False


                    # -----------------------------------
                    # PCM → WAV
                    # -----------------------------------

                    wav_audio = pcm_to_wav(current_audio)
                    print("🎵 PCM audio bytes:", len(current_audio))
                    print("🎵 WAV audio bytes:", len(wav_audio))

                    # -----------------------------------
                    # SPEECH TO TEXT
                    # -----------------------------------

                    try:

                        transcript = speech_to_text(
                            wav_audio,
                            filename="twilio_turn.wav"
                        )


                    except Exception as e:

                        print(
                            f"❌ STT error: "
                            f"{type(e).__name__}"
                        )

                        continue

                    if not transcript.strip():
                        print("⚠️ Empty transcript")
                        continue

                    # -----------------------------------
                    # LANGGRAPH
                    # -----------------------------------

                    # -----------------------------------
                    # OUTBOUND CONFIRMATION / LANGGRAPH
                    # -----------------------------------
                    spoken_text = None
                    if awaiting_outbound_confirmation:

                        normalized = re.sub(
                             r"[^\w\s]",
                              "",
                              transcript.lower()
                        ).strip()


                         # -------------------------------
                       # YES
                         # -------------------------------

                        if normalized in {
                            "yes",
                            "yeah",
                            "yep",
                            "sure",
                             "okay",
                            "ok",
                            "of course",
                             "yes please",
                        }:

                            awaiting_outbound_confirmation = False

                            response_text = (
            "Great, thank you. "
            "How can I help you today?"
                            )
                            spoken_text=response_text

                         # -------------------------------
                        # NO
                         # -------------------------------

                        elif normalized in {
                            "no",
        "nope",
        "not now",
        "busy",
        "not a good time",
                        }:

                            awaiting_outbound_confirmation = False

                            response_text = (
            "No problem. I'll let you go. "
            "Have a great day."
                            )
                            spoken_text=response_text

    # -------------------------------
    # UNCLEAR
    # -------------------------------

                        else:

                            response_text = (
            "Sorry, I just wanted to check "
            "whether this is a good time to talk. "
            "Is now okay?"
                        )
                            spoken_text=response_text

                    else:

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

                                "assistant_response": None,
                                "spoken_response": None,
                                "sources": [],
                                },

                                config=config,
                            )
                            #actual assistant response exists inside messages, but the separate assistant_response field is still None. so we used or as it picks first truthy value
                            response_text = result.get("assistant_response") or result["messages"][-1].content
                            spoken_text=result.get("spoken_response") or response_text
                        except Exception as e:
                            print(f"❌ Agent error: {type(e).__name__}")
                            continue

                    # -----------------------------------
                    # TTS
                    # -----------------------------------

                    try:

                        print("🔊 Generating TTS...")

                        agent_speaking = True

                        mp3_audio = text_to_speech(
                            spoken_text or response_text
                        )

                        print(
                            f"🔊 TTS size: "
                            f"{len(mp3_audio)} bytes"
                        )

                    except Exception as e:

                        agent_speaking = False

                        print(
                            f"❌ TTS error: "
                            f"{type(e).__name__}"
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
                            f"{type(e).__name__}"
                        )

                        continue

                    # -----------------------------------
                    # SEND AUDIO TO TWILIO
                    # -----------------------------------

                    
                    agent_speaking = True

                    audio_task = asyncio.create_task(
                        send_agent_audio(
                            websocket,
                            stream_sid,
                            ulaw_audio
                        )
                    )
                    # -----------------------------------
                    # MARK
                    # -----------------------------------

                    

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
                    "✅ Twilio playback mark received"
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

                print("Ignoring unsupported Twilio event")

    except WebSocketDisconnect as e:

        print(
            f"📞 Twilio WebSocket disconnected: "
            f"code={e.code}"
        )

    except Exception as e:

        print(
            f"❌ Media stream error: "
            f"{type(e).__name__}"
        )

    finally:

        agent_speaking = False

        print(
            "📞 Twilio Media Stream disconnected"
        )

import os
import secrets
from twilio.rest import Client
from fastapi import Header, HTTPException
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN")

twilio_client = Client(
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN
)



@app.post("/outbound-call")
def outbound_call(
    phone_number: str,
    api_key: str | None = Header(default=None, alias="X-Outbound-Call-Key"),
):
    expected_key = os.getenv("OUTBOUND_CALL_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=503, detail="Outbound calling is disabled.")
    if not api_key or not secrets.compare_digest(api_key.encode(), expected_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid outbound call API key.")

    try:
        twiml = f"""
<Response>
    <Connect>
        <Stream url="wss://{NGROK_DOMAIN}/media">
            <Parameter name="call_type" value="outbound" />
        </Stream>
    </Connect>
</Response>
"""
        call=twilio_client.calls.create(
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            twiml=twiml
        )
        print("Outbound call started")


        return {
            "success":True,
            "call_sid":call.sid,
            "to":phone_number
        }
    except Exception as exc:
        print("Outbound call failed:", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Could not start the outbound call.",
        ) from exc
