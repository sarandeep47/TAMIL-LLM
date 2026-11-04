# Tamil Voice Assistant Web Interface

A lightweight, modern web test interface for the Tamil Voice Assistant pipeline. Features a Google Assistant-style UI with real-time audio recording, Tamil transcription via Faster-Whisper, and LLM responses from Ollama.

## Features

- 🎤 **Real-time Audio Recording** - MediaRecorder API for browser-based recording
- 🧠 **Local Speech-to-Text** - Faster-Whisper with Tamil optimization (base model, int8 quantization)
- 🗣️ **Tamil Text-to-Speech** - Browser's Web Speech API with Tamil voice support
- ⚡ **Performance Metrics** - Real-time latency tracking for STT and LLM
- 🌙 **Dark Mode UI** - Google Assistant / Gemini-inspired design
- 📱 **Responsive Design** - Works on desktop and mobile devices
- 🔄 **Health Monitoring** - Real-time status checks for Ollama and Whisper

## Architecture

```
browser (index.html)
    ↓ Audio Blob (WebM)
[FastAPI Server: server.py]
    ├─→ Faster-Whisper (STT)
    │   └─→ Tamil text
    ├─→ Ollama API (LLM)
    │   └─→ tamil-voice-qwen model
    └─→ JSON Response (latencies)
    ↓
browser (TTS playback)
```

## Prerequisites

1. **Ollama**: Running locally on `http://localhost:11434`
   - Model: `tamil-voice-qwen` installed and available
   - Verify: `ollama pull tamil-voice-qwen`

2. **Python 3.9+** with venv or conda

3. **Microphone**: Browser microphone access required

## Installation

### 1. Create Virtual Environment (Optional but Recommended)

```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# Or macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```powershell
pip install -r requirements-web.txt
```

### 3. Verify Ollama is Running

```powershell
# Check Ollama health
curl http://localhost:11434/api/tags

# Or manually start Ollama (ensure model is available)
ollama serve
# In another terminal:
ollama pull tamil-voice-qwen
```

## Running the Web Interface

### Start the FastAPI Server

```powershell
python server.py
```

You should see:
```
Starting Tamil Voice Assistant Web Interface...
Access at http://localhost:8000
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Access the Interface

Open your browser and navigate to:
```
http://localhost:8000
```

## Usage

### Basic Workflow

1. **Allow Microphone**: Browser will prompt for microphone access (allow it)
2. **Tap the Microphone Button**: Blue circular button in the center
3. **Speak in Tamil or Tanglish**: Speak your query naturally
4. **Release to Submit**: The audio is transcribed and sent to Qwen
5. **Hear the Response**: The bot's Tamil response is automatically spoken back

### Keyboard Shortcuts

- **Space Bar**: Hold to record, release to submit
- **Ctrl+C**: Stop the server

### UI Status Indicators

- **Status Pills** (top):
  - Green dot = Service active
  - Red dot = Service down
- **Mic Button**:
  - Blue (idle) = Ready to record
  - Pulsing ring (listening) = Recording audio
  - Purple (thinking) = Processing STT/LLM
- **Transcripts**:
  - Right-aligned purple bubble = Your speech
  - Left-aligned gray bubble = Bot response
  - Small latency badges show STT and LLM processing times

## API Endpoints

### `GET /`
Serves the web interface (index.html)

### `GET /api/health`
Returns service status:
```json
{
  "ollama": true,
  "whisper": true
}
```

### `POST /api/voice-turn`
Main endpoint for processing voice input.

**Request:**
```
Content-Type: multipart/form-data
Body: file (audio blob, WebM or WAV)
```

**Response:**
```json
{
  "user_text": "நீ எப்படி இருக்கையா?",
  "bot_text": "வணக்கம்! நான் நன்றாக இருக்கிறேன்...",
  "stt_latency_ms": 1250,
  "llm_latency_ms": 3450
}
```

**Error Response:**
```json
{
  "detail": "Ollama service is unavailable. Ensure it's running at http://localhost:11434"
}
```

## Configuration

Edit these constants in `server.py` if needed:

```python
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "tamil-voice-qwen"
SAMPLE_RATE = 16000
```

Edit these in Whisper initialization for STT tuning:

```python
whisper_model = WhisperModel(
    "base",              # Model size: tiny, small, base, small, medium, large
    device="cpu",        # or "cuda" if GPU available
    compute_type="int8", # "int8", "int16", or "float32"
    cpu_threads=4,       # Adjust based on CPU cores
)
```

## Troubleshooting

### "Ollama service is unavailable"
- Ensure Ollama is running: `ollama serve` in a separate terminal
- Check Ollama has the model: `ollama list | grep tamil-voice-qwen`
- Verify it's accessible: `curl http://localhost:11434/api/tags`

### "Microphone access denied"
- Check browser permissions for microphone
- Restart the browser or clear cache
- Ensure HTTPS is not required (localhost works with HTTP)

### Audio not playing in browser
- Check browser volume and mute status
- Verify Web Speech API is supported (most modern browsers)
- Check browser console for errors (F12 → Console tab)

### Transcription is empty or inaccurate
- Ensure you're speaking clearly in Tamil or Tanglish
- Check microphone input levels
- The VAD filter might be too aggressive; try speaking louder or longer

### Slow response times
- Check CPU usage (Whisper and Ollama are CPU-intensive)
- Consider using a smaller model or GPU acceleration
- Reduce `cpu_threads` in Whisper to free resources for Ollama

## Performance Tuning

### Faster Inference
1. Use CUDA (if GPU available): Change `device="cuda"` and `compute_type="float16"`
2. Use smaller models: `tiny`, `small` instead of `base`
3. Increase thread count if CPU has spare capacity

### Memory Optimization
1. Lower `cpu_threads` in Whisper config
2. Use `compute_type="int8"` for quantization
3. Ensure no other heavy processes are running

## Browser Compatibility

- **Chrome/Chromium** ✅ (recommended)
- **Firefox** ✅
- **Safari** ✅ (Web Speech API support varies by region)
- **Edge** ✅

## Files Overview

- `server.py` - FastAPI backend with STT/LLM integration
- `templates/index.html` - React-free web UI with vanilla JS
- `requirements-web.txt` - Python dependencies
- `call_agent.py` - Original CLI version (reference)

## Development Notes

### Adding Features
The code is modular and easy to extend:
- Add new routes in `server.py`
- Update UI in `index.html` without build step
- No npm/webpack required

### Debugging
Enable debug logging in `server.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check browser console (F12) for client-side errors.

## License

Part of the Tamil Voice Assistant project.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review server logs for errors
3. Check browser console (F12 → Console)
4. Verify Ollama and audio inputs are working
