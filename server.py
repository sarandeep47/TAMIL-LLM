import io
import time
import requests
import numpy as np
import soundfile as sf
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "tamil-voice-qwen"

logger.info("Initializing Faster-Whisper (optimized CPU settings)...")
whisper_model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8",
    cpu_threads=4,
    num_workers=1
)

# ============ FASTAPI APP ============
app = FastAPI(title="Tamil Voice Assistant Web Test")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    """Transcribe float32 NumPy audio array using Faster-Whisper with balanced prompt."""
    try:
        start_time = time.time()
        
        # Priming Whisper with full reciprocal colloquial Tamil vocabulary
        tamil_prompt = (
            "வணக்கம், எப்படி இருக்கீங்க? நான் நல்லா இருக்கேன், ரொம்ப நன்றி. "
            "எனக்கு ஒரு கேப் புக் பண்ணனும், கார் வேணும், பிக்கப் லொகேஷன் சொல்லுங்க."
        )

        segments, _ = whisper_model.transcribe(
            audio_array,
            language="ta",
            initial_prompt=tamil_prompt,
            beam_size=2,
            best_of=2,
            temperature=0.0,
            condition_on_previous_text=False,
            repetition_penalty=1.1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500, threshold=0.42)  # Optimal sweet spot
        )

        text = "".join([segment.text for segment in segments]).strip()
        latency = round((time.time() - start_time) * 1000)
        logger.info(f"[STT Latency: {latency}ms] Transcribed: '{text}'")
        return text, latency
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise


def ask_ollama(prompt_text):
    """Send prompt to Ollama and get Tamil response."""
    start_time = time.time()
    
    # System prompt to prevent gibberish echo
    system_prompt = """You are a helpful, spoken-Tamil voice assistant for cab booking and assistance.
Rules:
- Always respond in clear, spoken Tamil (பேச்சுத் தமிழ்).
- Reply in ONLY ONE short sentence.
- If the user's speech is unclear, corrupted, or gibberish, do NOT repeat their words. Instead reply: 'மன்னிக்கவும், நீங்கள் பேசியது புரியவில்லை. மீண்டும் சொல்லுங்கள்?'
- If the user asks for a cab or car, ask for the pickup location: 'கண்டிப்பா, உங்க பிக்கப் லொகேஷன் சொல்லுங்க?'

Examples:
User: வணக்கம்
Assistant: வணக்கம், நான் உங்களுக்கு எப்படி உதவ வேண்டும்?

User: எனக்கு ஒரு கேப் புக் பண்ணனும்
Assistant: கண்டிப்பா, உங்க பிக்கப் லொகேஷன் சொல்லுங்க?"""
    
    # Build full prompt with system context and user input
    full_prompt = f"{system_prompt}\n\nUser: {prompt_text}\nAssistant:"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "num_thread": 4,
            "temperature": 0.2,     # Low temperature for consistency
            "top_k": 40,            # Conservative token selection
            "top_p": 0.8            # Nucleus sampling
        }
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        result = response.json().get("response", "").strip()
        latency = round((time.time() - start_time) * 1000)
        logger.info(f"[LLM Latency: {latency}ms] Response: {result}")
        return result, latency
    
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama. Ensure Ollama is running at http://localhost:11434")
        raise HTTPException(
            status_code=503,
            detail="Ollama service is unavailable. Ensure it's running at http://localhost:11434"
        )
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


def check_ollama_health():
    """Check if Ollama is running and has the model."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        models = response.json().get("models", [])
        model_names = [m.get("name", "").split(":")[0] for m in models]
        is_available = any(MODEL_NAME in name for name in model_names)
        return is_available
    except:
        return False


def check_whisper_health():
    """Whisper is initialized at startup, so just confirm."""
    return True


# ============ ROUTES ============

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the web interface."""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/health")
async def health_check():
    """Check backend service health."""
    return {
        "ollama": check_ollama_health(),
        "whisper": check_whisper_health()
    }


@app.post("/api/voice-turn")
async def voice_turn(file: UploadFile = File(...)):
    """
    Process a single voice turn:
    1. Parse WAV file with soundfile
    2. Transcribe audio (STT)
    3. Send to Ollama (LLM)
    4. Return both with latencies
    """
    try:
        # Read audio file (should be uncompressed 16kHz WAV from browser)
        audio_bytes = await file.read()
        
        logger.info(f"Received audio file: {len(audio_bytes)} bytes, format: {file.content_type}")
        
        # Debug: Log first 44 bytes (WAV header)
        if len(audio_bytes) >= 44:
            header = audio_bytes[:44]
            logger.debug(f"WAV Header (hex): {header.hex()[:88]}")
            logger.debug(f"WAV Header (ascii): {repr(header)}")
        
        if len(audio_bytes) < 1000:
            logger.warning("Audio file too small: < 1000 bytes")
            return {
                "user_text": "",
                "bot_text": "மன்னிக்கவும், பேச்சு கேட்கப்படவில்லை.",
                "stt_latency_ms": 0,
                "llm_latency_ms": 0
            }
        
        # 1. Parse WAV directly via soundfile (no FFmpeg needed)
        audio_array = load_wav_to_numpy(audio_bytes)
        
        # Check if array is empty
        if audio_array.size == 0:
            return {
                "user_text": "",
                "bot_text": "மன்னிக்கவும், பேச்சு கேட்கப்படவில்லை.",
                "stt_latency_ms": 0,
                "llm_latency_ms": 0
            }
        
        # 2. Transcribe with Whisper (pure float32 array)
        user_text, stt_latency = transcribe_audio_array(audio_array)
        
        if not user_text:
            logger.warning("Transcription returned empty text")
            return {
                "user_text": "",
                "bot_text": "மன்னிக்கவும், பேச்சு கேட்கப்படவில்லை.",
                "stt_latency_ms": stt_latency,
                "llm_latency_ms": 0
            }
        
        # 3. Query Qwen on Ollama
        bot_text, llm_latency = ask_ollama(user_text)
        
        return {
            "user_text": user_text,
            "bot_text": bot_text,
            "stt_latency_ms": stt_latency,
            "llm_latency_ms": llm_latency
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice turn error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Tamil Voice Assistant Web Interface...")
    logger.info("Access at http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
