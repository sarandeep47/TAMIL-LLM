# Configuration Template for Tamil Voice Assistant Web Interface
# Copy this file to config.py and customize as needed

# ============ OLLAMA CONFIGURATION ============
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "tamil-voice-qwen"
OLLAMA_TIMEOUT_SEC = 30

# ============ WHISPER CONFIGURATION ============
WHISPER_MODEL_SIZE = "base"  # Options: tiny, small, base, medium, large
WHISPER_DEVICE = "cpu"        # Options: cpu, cuda
WHISPER_COMPUTE_TYPE = "int8" # Options: int8, int16, float32
WHISPER_CPU_THREADS = 4       # Adjust based on available CPU cores
WHISPER_NUM_WORKERS = 1       # Number of parallel workers

# ============ AUDIO CONFIGURATION ============
SAMPLE_RATE = 16000           # Hz (recommended for Whisper)
RECORD_DURATION = 4           # Seconds max recording time
SILENCE_THRESHOLD = 0.015     # RMS energy threshold (0.0-1.0)
MIN_SILENCE_DURATION_MS = 500 # Minimum silence for VAD

# ============ WHISPER PROMPT (Tamil Vocabulary Priming) ============
TAMIL_PROMPT = """வணக்கம், எனக்கு ஒரு கேப் புக் பண்ணனும், ஒரு டவுட் இருக்கு, கார் வேணும், பிக்கப் லொகேஷன்."""

# ============ WEB SERVER CONFIGURATION ============
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000
CORS_ORIGINS = ["*"]  # For production, restrict to specific domains
RELOAD = False         # Set True for development with auto-reload

# ============ LOGGING ============
LOG_LEVEL = "INFO"     # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

# ============ UI CUSTOMIZATION ============
UI_TITLE = "Tamil Voice Assistant"
UI_THEME = "dark"      # Options: dark, light (currently only dark is implemented)

# ============ FEATURE FLAGS ============
ENABLE_HEALTH_CHECK = True
ENABLE_LATENCY_BADGES = True
ENABLE_AUTO_TTS = True
ENABLE_VITE_FILTER = True

# ============ PERFORMANCE TUNING ============
# Adjust these based on your hardware
MAX_CONCURRENT_REQUESTS = 1   # Process one voice turn at a time
STT_TIMEOUT_SEC = 30
LLM_TIMEOUT_SEC = 30

# ============ ADVANCED - WHISPER PARAMETERS ============
WHISPER_BEAM_SIZE = 1
WHISPER_BEST_OF = 1
WHISPER_TEMPERATURE = 0.0
WHISPER_REPETITION_PENALTY = 1.2
WHISPER_CONDITION_ON_PREVIOUS_TEXT = False
WHISPER_VAD_FILTER = True

# ============ ADVANCED - OLLAMA PARAMETERS ============
OLLAMA_NUM_THREADS = 4
OLLAMA_TEMPERATURE = 0.7      # Creativity level (0.0-1.0)
OLLAMA_TOP_P = 0.9            # Diversity sampling
OLLAMA_TOP_K = 40             # Top-K filtering
