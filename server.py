import io
import time
import os
import json
import requests
import numpy as np
import soundfile as sf
import threading
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool, iterate_in_threadpool
from faster_whisper import WhisperModel
from pydantic import BaseModel
import logging
from router import route_message
from step4.streaming_utils import strip_role_prefix, SentenceSplitter
from token_cleaner import TokenCleaner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
PERSONAI_MODEL = os.getenv("PERSONAI_MODEL", "gemma3:4b")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
NUM_CTX = int(os.getenv("NUM_CTX", "2048"))
NUM_PREDICT = int(os.getenv("NUM_PREDICT", "80"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
TOP_P = float(os.getenv("TOP_P", "0.8"))
PERSONAI_THREADS = int(os.getenv("PERSONAI_THREADS", "4"))
MAX_SENTENCES = int(os.getenv("MAX_SENTENCES", "2"))
PERSONAI_FAKE_STT_TEXT = os.getenv("PERSONAI_FAKE_STT_TEXT", None)  # Test-only override
NO_SPEECH_REPLY = "மன்னிக்கவும், பேச்சு கேட்கப்படவில்லை."

# Exact system prompt from Step 3
SYSTEM_PROMPT = """You are a friendly Tamil voice assistant that helps people book cabs. Reply in one short, natural, correct spoken-Tamil sentence. If the user writes Tamil in English letters (Tanglish), understand it and reply in Tamil script. If the user writes English, reply in English. Ask for the pickup location, drop location or time when needed. If you do not know something, say so briefly. Never repeat the user's words back. Examples:
User: Anna Nagar la iruken
A: சரி, எங்கே போகணும்?
User: unga peru enna
A: என் பெயர் PersonAI, உங்களுக்கு என்ன உதவி வேணும்?
User: Can you help me?
A: Of course! Where would you like to go?"""

# Legacy prompt (unused, kept for reference)
LEGACY_SYSTEM_PROMPT = """You are a helpful, spoken-Tamil voice assistant for cab booking and assistance.
Rules:
- Always respond in clear, spoken Tamil (பேச்சுத் தமிழ்).
- Reply in ONLY ONE short sentence.
- If the user's speech is unclear, corrupted, or gibberish, do NOT repeat their words. Instead reply: 'மன்னிக்கவும், நீங்கள் பேசியது புரியவில்லை. மீண்டும் சொல்லுங்கள்?'
- If the user asks for a cab or car, ask for the pickup location: 'கண்டிப்பா, உங்க பிக்கப் லொகேஷன் சொல்லுங்க?'"""

ROUTER_ENABLED = os.getenv("PERSONAI_ROUTER", "on").lower() != "off"
logger.info(f"Router enabled: {ROUTER_ENABLED}")
logger.info(f"Model: {PERSONAI_MODEL}")
logger.info(f"Config: NUM_CTX={NUM_CTX}, NUM_PREDICT={NUM_PREDICT}, TEMPERATURE={TEMPERATURE}, MAX_SENTENCES={MAX_SENTENCES}")

# ============ GLOBAL STATE ============
model_warm = False
model_warm_time = 0

# ============ REQUEST MODELS ============
class ChatRequest(BaseModel):
    text: str

# ============ WHISPER INITIALIZATION ============
logger.info("Initializing Faster-Whisper (optimized CPU settings)...")
whisper_model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8",
    cpu_threads=4,
    num_workers=1
)

# ============ FASTAPI APP ============
app = FastAPI(title="Tamil Voice Assistant - Step 4A Streaming")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ UTILITY FUNCTIONS ============

def load_wav_to_numpy(audio_bytes: bytes) -> np.ndarray:
    """Reads uncompressed 16kHz WAV bytes directly into a float32 NumPy array."""
    try:
        with io.BytesIO(audio_bytes) as audio_file:
            data, sample_rate = sf.read(audio_file, dtype="float32")

        logger.info(f"Loaded WAV: {sample_rate}Hz, {len(data)} samples, shape={data.shape}")

        # Convert stereo to mono if needed
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)

        return data
    except Exception as e:
        logger.error(f"WAV parsing error: {e}")
        logger.error(f"Audio bytes size: {len(audio_bytes)}")
        logger.error(f"First 44 bytes (hex): {audio_bytes[:44].hex()[:88] if len(audio_bytes) >= 44 else 'Too short'}")
        raise


def transcribe_audio_array(audio_array: np.ndarray):
    """Transcribe float32 NumPy audio array using Faster-Whisper with minimal prompt."""
    try:
        start_time = time.time()
        
        # Minimal prompt to avoid hallucination
        # Just basic Tamil words, no full sentences
        tamil_prompt = "வணக்கம், நன்றி, கேப், கார், இருக்கேன்"

        segments, _ = whisper_model.transcribe(
            audio_array,
            language="ta",
            initial_prompt=tamil_prompt,
            beam_size=2,
            best_of=2,
            temperature=0.0,
            condition_on_previous_text=False,
            repetition_penalty=1.2,  # Increased to prevent repetition
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500, threshold=0.42)
        )

        text = "".join([segment.text for segment in segments]).strip()
        
        # Additional hallucination filter
        # If result is too repetitive or too long for the audio, flag it
        if text.count(text.split()[0] if text.split() else '') > len(text.split()) * 0.5:
            logger.warning(f"Possible hallucination detected: {text}")
        
        latency = round((time.time() - start_time) * 1000)
        logger.info(f"[STT Latency: {latency}ms] Transcribed: '{text}'")
        return text, latency
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise


def respond(user_text):
    """Route message through router if enabled."""
    if not ROUTER_ENABLED:
        return None, 0, "llm"
    
    result = route_message(user_text)
    if result is None:
        return None, 0, "llm"
    
    intent = result.get("intent")
    reply = result.get("reply", "")
    return reply, 0, f"rule:{intent}"


def ask_ollama(prompt_text):
    """Send prompt to Ollama /api/chat endpoint and get response."""
    start_time = time.time()
    
    payload = {
        "model": PERSONAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text}
        ],
        "stream": False,
        "options": {
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "num_thread": PERSONAI_THREADS
        },
        "keep_alive": OLLAMA_KEEP_ALIVE
    }
    
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        result = response.json().get("message", {}).get("content", "").strip()
        
        # Strip role prefix
        result = strip_role_prefix(result)
        
        latency = round((time.time() - start_time) * 1000)
        logger.info(f"[LLM Latency: {latency}ms] Response: {result}")
        return result, latency
    
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama at http://127.0.0.1:11434")
        raise HTTPException(status_code=503, detail="Ollama service unavailable")
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


def warm_model():
    """Warm up the model in background thread."""
    global model_warm, model_warm_time
    try:
        start = time.time()
        payload = {
            "model": PERSONAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Hi"}
            ],
            "stream": False,
            "options": {
                "num_predict": 1,
                "num_ctx": NUM_CTX,
                "num_thread": PERSONAI_THREADS
            },
            "keep_alive": OLLAMA_KEEP_ALIVE
        }
        response = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=60)
        model_warm_time = int((time.time() - start) * 1000)
        model_warm = True
        logger.info(f"Model warm in {model_warm_time} ms")
    except Exception as e:
        logger.error(f"Model warm-up failed: {e}")
        model_warm = False


class StreamingResponse_:
    """Wrapper that yields chunks and carries metrics."""
    def __init__(self, prompt_text):
        self.prompt_text = prompt_text
        self.metrics = {}
        self._generator = None
    
    def __iter__(self):
        """Create generator for this request."""
        payload = {
            "model": PERSONAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self.prompt_text}
            ],
            "stream": True,
            "options": {
                "num_ctx": NUM_CTX,
                "num_predict": NUM_PREDICT,
                "temperature": TEMPERATURE,
                "top_p": TOP_P,
                "num_thread": PERSONAI_THREADS
            },
            "keep_alive": OLLAMA_KEEP_ALIVE
        }
        
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json=payload,
            timeout=120,
            stream=True
        )
        response.raise_for_status()
        
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    
                    # Capture final metrics from the last chunk (when done=True)
                    if data.get("done", False):
                        self.metrics = {
                            "load_ms": data.get("load_duration", 0) // 1_000_000,
                            "prefill_ms": data.get("prompt_eval_duration", 0) // 1_000_000,
                            "eval_count": data.get("eval_count", 0)
                        }
                except json.JSONDecodeError:
                    continue
        finally:
            response.close()
            logger.info(f"stream closed: ollama response for '{self.prompt_text[:50]}...'")
    
    def close(self):
        """Explicit close (no-op since response closed in __iter__ finally)."""
        logger.info(f"stream close() called on: '{self.prompt_text[:50]}...'")




def ask_ollama_stream(prompt_text):
    """Stream response from Ollama /api/chat endpoint. Returns StreamingResponse_ object with metrics."""
    return StreamingResponse_(prompt_text)

# ============ STARTUP ============

@app.on_event("startup")
def startup_event():
    """Start model warm-up in background thread."""
    thread = threading.Thread(target=warm_model, daemon=True)
    thread.start()
    logger.info("Starting Tamil Voice Assistant Web Interface...")
    logger.info("Access at http://127.0.0.1:8000")


# ============ HEALTH CHECK ============

@app.get("/api/health")
async def health():
    """Health check endpoint with model warm status."""
    return {
        "status": "ok",
        "model": PERSONAI_MODEL,
        "warm": model_warm,
        "warm_time_ms": model_warm_time if model_warm else None,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============ EXISTING ENDPOINTS (unchanged) ============

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the web interface."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tamil Voice Assistant</title>
        <style>
            body { font-family: Arial; margin: 20px; }
            textarea { width: 100%; height: 100px; }
            button { padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>Tamil Voice Assistant - Step 4A</h1>
        <p>Model: {model}</p>
        <input type="file" id="audio_file" accept="audio/wav">
        <button onclick="sendAudio()">Send Audio</button>
        <hr>
        <textarea id="text_input" placeholder="Enter text..."></textarea>
        <button onclick="sendText()">Send Text</button>
        <hr>
        <div id="output"></div>
        <script>
            async function sendAudio() {{
                const file = document.getElementById('audio_file').files[0];
                if (!file) return;
                const formData = new FormData();
                formData.append('file', file);
                const response = await fetch('/api/voice-turn', {{ method: 'POST', body: formData }});
                document.getElementById('output').textContent = await response.text();
            }}
            async function sendText() {{
                const text = document.getElementById('text_input').value;
                if (!text) return;
                const response = await fetch('/api/chat', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ text }})
                }});
                const data = await response.json();
                document.getElementById('output').textContent = data.reply;
            }}
        </script>
    </body>
    </html>
    """.format(model=PERSONAI_MODEL)
    return html_content


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Text chat endpoint (non-streaming)."""
    user_text = request.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Empty text")
    
    start_time = time.time()
    
    # Try router first
    rule_reply, rule_latency, route = await run_in_threadpool(respond, user_text)
    
    if rule_reply is None:
        # Use LLM
        bot_text, llm_latency = await run_in_threadpool(ask_ollama, user_text)
    else:
        bot_text = rule_reply
        llm_latency = rule_latency
    
    total_ms = int((time.time() - start_time) * 1000)
    
    return {
        "user_text": user_text,
        "bot_text": bot_text,
        "llm_latency_ms": llm_latency,
        "stt_latency_ms": 0,
        "route": route
    }


@app.post("/api/voice-turn")
async def voice_turn(file: UploadFile = File(...)):
    """Audio input endpoint (non-streaming)."""
    start_time = time.time()
    
    audio_bytes = await file.read()
    logger.info(f"Received audio file: {len(audio_bytes)} bytes, format: {file.content_type}")
    
    # Check file size first
    if len(audio_bytes) < 1000:
        logger.warning("Audio file too small: < 1000 bytes")
        return {
            "user_text": "",
            "bot_text": NO_SPEECH_REPLY,
            "stt_latency_ms": 0,
            "llm_latency_ms": 0,
            "route": "silence"
        }
    
    # STT (with test override)
    if PERSONAI_FAKE_STT_TEXT:
        user_text = PERSONAI_FAKE_STT_TEXT
        stt_latency = 0
        logger.info(f"[TEST OVERRIDE] Using PERSONAI_FAKE_STT_TEXT: {user_text}")
    else:
        audio_array = await run_in_threadpool(load_wav_to_numpy, audio_bytes)
        if audio_array.size == 0:
            return {
                "user_text": "",
                "bot_text": NO_SPEECH_REPLY,
                "stt_latency_ms": 0,
                "llm_latency_ms": 0,
                "route": "silence"
            }
        user_text, stt_latency = await run_in_threadpool(transcribe_audio_array, audio_array)
    
    if not user_text or len(user_text.strip()) < 2:
        total_ms = int((time.time() - start_time) * 1000)
        return {
            "user_text": user_text,
            "bot_text": NO_SPEECH_REPLY,
            "stt_latency_ms": stt_latency,
            "llm_latency_ms": 0,
            "route": "silence"
        }
    
    # Try router first
    rule_reply, rule_latency, route = await run_in_threadpool(respond, user_text)
    
    if rule_reply is not None:
        bot_text = rule_reply
        llm_latency = rule_latency
    else:
        bot_text, llm_latency = await run_in_threadpool(ask_ollama, user_text)
    
    total_ms = int((time.time() - start_time) * 1000)
    
    return {
        "user_text": user_text,
        "bot_text": bot_text,
        "stt_latency_ms": stt_latency,
        "llm_latency_ms": llm_latency,
        "route": route
    }


# ============ NEW STREAMING ENDPOINTS ============

@app.post("/api/chat-stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint with Server-Sent Events."""
    user_text = request.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Empty text")
    
    def event_generator():
        try:
            request_start_time = time.time()
            first_token_time = None
            first_sentence_time = None
            
            # Try router first
            reply, route_latency, route = respond(user_text)
            
            if reply is not None:
                # Router handled it
                yield f'data: {json.dumps({"event": "meta", "route": route, "model": PERSONAI_MODEL})}\n\n'
                yield f'data: {json.dumps({"event": "sentence", "index": 0, "text": reply})}\n\n'
                yield f'data: {json.dumps({"event": "done", "reply": reply, "ttft_ms": 0, "first_sentence_ms": 0, "total_ms": int((time.time() - request_start_time) * 1000), "route": route})}\n\n'
            else:
                # Use LLM
                yield f'data: {json.dumps({"event": "meta", "route": "llm", "model": PERSONAI_MODEL})}\n\n'
                
                splitter = SentenceSplitter()
                cleaner = TokenCleaner()
                sentence_count = 0
                full_reply = ""
                
                stream_obj = ask_ollama_stream(user_text)
                try:
                    for chunk in stream_obj:
                        if first_token_time is None:
                            first_token_time = time.time()
                        
                        full_reply += chunk
                        
                        # Emit cleaned token event
                        cleaned = cleaner.feed(chunk)
                        if cleaned:
                            yield f'data: {json.dumps({"event": "token", "text": cleaned})}\n\n'
                        
                        # Check for sentences
                        sentences = splitter.feed(chunk)
                        for sentence in sentences:
                            if first_sentence_time is None:
                                first_sentence_time = time.time()
                            if sentence_count < MAX_SENTENCES:
                                yield f'data: {json.dumps({"event": "sentence", "index": sentence_count, "text": sentence})}\n\n'
                                sentence_count += 1
                            else:
                                break
                        
                        if sentence_count >= MAX_SENTENCES:
                            break
                finally:
                    stream_obj.close()
                    logger.info(f"stream closed: chat_stream loop stopped (sentences={sentence_count})")
                
                # Flush remaining
                tail = cleaner.flush()
                if tail:
                    yield f'data: {json.dumps({"event": "token", "text": tail})}\n\n'
                
                remaining = splitter.flush()
                if remaining and sentence_count < MAX_SENTENCES:
                    if first_sentence_time is None:
                        first_sentence_time = time.time()
                    yield f'data: {json.dumps({"event": "sentence", "index": sentence_count, "text": remaining})}\n\n'
                
                ttft_ms = int((first_token_time - request_start_time) * 1000) if first_token_time else 0
                first_sentence_ms = int((first_sentence_time - request_start_time) * 1000) if first_sentence_time else 0
                total_ms = int((time.time() - request_start_time) * 1000)
                
                # Clean the full reply
                full_reply = strip_role_prefix(full_reply)
                
                # Get Ollama metrics from stream object (per-request, not shared)
                metrics = stream_obj.metrics
                
                done_event = {
                    "event": "done",
                    "reply": full_reply,
                    "ttft_ms": ttft_ms,
                    "first_sentence_ms": first_sentence_ms,
                    "total_ms": total_ms,
                    "route": "llm"
                }
                # Add metrics if available
                if metrics.get("load_ms"):
                    done_event["load_ms"] = metrics.get("load_ms", 0)
                if metrics.get("prefill_ms"):
                    done_event["prefill_ms"] = metrics.get("prefill_ms", 0)
                if metrics.get("eval_count"):
                    done_event["eval_count"] = metrics.get("eval_count", 0)
                
                yield f'data: {json.dumps(done_event)}\n\n'
        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f'data: {json.dumps({"event": "error", "message": str(e)})}\n\n'
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/voice-turn-stream")
async def voice_turn_stream(file: UploadFile = File(...)):
    """Streaming voice input endpoint with Server-Sent Events."""
    
    async def event_generator():
        try:
            request_start_time = time.time()
            first_token_time = None
            first_sentence_time = None
            
            # Read audio file
            audio_bytes = await file.read()
            logger.info(f"Received audio file: {len(audio_bytes)} bytes")
            
            # STT (blocking, run in threadpool) - with test override
            if PERSONAI_FAKE_STT_TEXT:
                user_text = PERSONAI_FAKE_STT_TEXT
                stt_latency = 0
                logger.info(f"[TEST OVERRIDE] Using PERSONAI_FAKE_STT_TEXT: {user_text}")
            else:
                audio_array = await run_in_threadpool(load_wav_to_numpy, audio_bytes)
                user_text, stt_latency = await run_in_threadpool(transcribe_audio_array, audio_array)
            
            logger.info(f"STT result: '{user_text}' ({stt_latency}ms)")
            
            # Emit STT event
            yield f'data: {json.dumps({"event": "stt", "user_text": user_text, "stt_latency_ms": stt_latency})}\n\n'
            
            if not user_text or len(user_text.strip()) < 2:
                # No speech
                reply = NO_SPEECH_REPLY
                yield f'data: {json.dumps({"event": "done", "reply": reply, "ttft_ms": 0, "first_sentence_ms": 0, "total_ms": int((time.time() - request_start_time) * 1000), "route": "silence"})}\n\n'
                return
            
            # Try router
            reply, route_latency, route = await run_in_threadpool(respond, user_text)
            
            if reply is not None:
                # Router handled it
                yield f'data: {json.dumps({"event": "meta", "route": route, "model": PERSONAI_MODEL})}\n\n'
                yield f'data: {json.dumps({"event": "sentence", "index": 0, "text": reply})}\n\n'
                yield f'data: {json.dumps({"event": "done", "reply": reply, "ttft_ms": 0, "first_sentence_ms": 0, "total_ms": int((time.time() - request_start_time) * 1000), "route": route})}\n\n'
            else:
                # Use LLM
                yield f'data: {json.dumps({"event": "meta", "route": "llm", "model": PERSONAI_MODEL})}\n\n'
                
                splitter = SentenceSplitter()
                cleaner = TokenCleaner()
                sentence_count = 0
                full_reply = ""
                
                # Stream response without blocking event loop
                stream_obj = ask_ollama_stream(user_text)
                try:
                    async for chunk in iterate_in_threadpool(stream_obj):
                        if first_token_time is None:
                            first_token_time = time.time()
                        
                        full_reply += chunk
                        
                        # Emit cleaned token event
                        cleaned = cleaner.feed(chunk)
                        if cleaned:
                            yield f'data: {json.dumps({"event": "token", "text": cleaned})}\n\n'
                        
                        # Check for sentences
                        sentences = splitter.feed(chunk)
                        for sentence in sentences:
                            if first_sentence_time is None:
                                first_sentence_time = time.time()
                            if sentence_count < MAX_SENTENCES:
                                yield f'data: {json.dumps({"event": "sentence", "index": sentence_count, "text": sentence})}\n\n'
                                sentence_count += 1
                            else:
                                break
                        
                        if sentence_count >= MAX_SENTENCES:
                            break
                finally:
                    stream_obj.close()
                    logger.info(f"stream closed: voice_turn_stream loop stopped (sentences={sentence_count})")
                
                # Flush remaining
                tail = cleaner.flush()
                if tail:
                    yield f'data: {json.dumps({"event": "token", "text": tail})}\n\n'
                
                remaining = splitter.flush()
                if remaining and sentence_count < MAX_SENTENCES:
                    if first_sentence_time is None:
                        first_sentence_time = time.time()
                    yield f'data: {json.dumps({"event": "sentence", "index": sentence_count, "text": remaining})}\n\n'
                
                ttft_ms = int((first_token_time - request_start_time) * 1000) if first_token_time else 0
                first_sentence_ms = int((first_sentence_time - request_start_time) * 1000) if first_sentence_time else 0
                total_ms = int((time.time() - request_start_time) * 1000)
                
                # Clean the full reply
                full_reply = strip_role_prefix(full_reply)
                
                # Get Ollama metrics from stream object (per-request, not shared)
                metrics = stream_obj.metrics
                
                done_event = {
                    "event": "done",
                    "reply": full_reply,
                    "ttft_ms": ttft_ms,
                    "first_sentence_ms": first_sentence_ms,
                    "total_ms": total_ms,
                    "route": "llm"
                }
                # Add metrics if available
                if metrics.get("load_ms"):
                    done_event["load_ms"] = metrics.get("load_ms", 0)
                if metrics.get("prefill_ms"):
                    done_event["prefill_ms"] = metrics.get("prefill_ms", 0)
                if metrics.get("eval_count"):
                    done_event["eval_count"] = metrics.get("eval_count", 0)
                
                yield f'data: {json.dumps(done_event)}\n\n'
        
        except Exception as e:
            logger.error(f"Voice streaming error: {e}")
            yield f'data: {json.dumps({"event": "error", "message": str(e)})}\n\n'
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
