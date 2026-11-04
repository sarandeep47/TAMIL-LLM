# Tamil Voice Assistant - Local LLM Pipeline

A complete, end-to-end **Tamil speech-to-text → LLM → text-to-speech** pipeline running entirely on local hardware. No cloud dependencies.

## 🎯 Features

✅ **Native Audio Processing**
- Browser captures audio directly as 16kHz PCM WAV (no codec dependencies)
- Zero FFmpeg/PyAV overhead

✅ **Accurate Tamil STT**
- Faster-Whisper base model (Tamil-optimized)
- Balanced prompt engineering to prevent phonetic hallucination
- VAD (Voice Activity Detection) with configurable sensitivity

✅ **Contextual Tamil LLM**
- Ollama + Qwen2.5 3B model (quantized for CPU)
- Intent-aware responses (greetings, bookings, FAQs)
- No truncation: 80-token budget for complete sentences

✅ **Conversational TTS**
- Web Speech API (browser-native Tamil voice)
- Adjustable playback speed (0.7 rate for clarity)
- Natural Tamil phrasing

✅ **Clean Web Interface**
- Dark mode design with real-time status indicators
- Transcript history with latency metrics
- Export: View/Copy/Download conversation as text

---

## 🏗️ Architecture

```
Browser (Web Audio API)
    ↓
[WAV Encoding: 16-bit PCM @ 16kHz]
    ↓
FastAPI Server (Python)
    ├─ soundfile.read() → Parse WAV
    ├─ Faster-Whisper → STT (Tamil transcription)
    ├─ Ollama LLM → Intent-aware response
    └─ JSON response (user_text, bot_text, latencies)
    ↓
Browser (Web Speech API)
    ├─ Display transcript
    └─ Play TTS audio (Tamil voice, 0.7x speed)
```

---

## 📦 Requirements

### System
- **OS**: Windows/Mac/Linux
- **RAM**: 4GB+ (Faster-Whisper + Ollama model)
- **CPU**: Multi-core recommended

### Software
- Python 3.10+
- Ollama ([download here](https://ollama.ai))

### Python Dependencies
```
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
requests==2.31.0
numpy>=1.26.0
faster-whisper>=1.0.0
soundfile==0.12.1
```

---

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/sarandeep47/TAMIL-LLM.git
cd TAMIL-LLM
```

### 2. Install Dependencies
```bash
pip install -r requirements-web.txt
```

### 3. Start Ollama
In one terminal:
```bash
ollama serve
```

### 4. Rebuild Tamil Model
In another terminal:
```bash
cd TAMIL-LLM
ollama create tamil-voice-qwen -f .\Modelfile.qwen_tamil
```

### 5. Start FastAPI Server
```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

### 6. Open Browser
```
http://127.0.0.1:8000
```

### 7. Test
1. **Wear headphones** (acoustic isolation)
2. Click microphone
3. Speak Tamil: "வணக்கம், எப்படி இருக்கீங்க?"
4. See transcription and bot response

---

## ⚙️ Configuration

### Whisper STT Tuning (`server.py`)
```python
tamil_prompt = "வணக்கம், எப்படி இருக்கீங்க? நல்லா இருக்கேன்..."
vad_parameters=dict(min_silence_duration_ms=600, threshold=0.4)
beam_size=2  # Balance accuracy vs latency
```

### Ollama LLM Parameters (`Modelfile.qwen_tamil`)
```
PARAMETER num_predict 80      # Token budget (complete sentences)
PARAMETER temperature 0.2     # Low randomness (consistent output)
PARAMETER top_p 0.8          # Nucleus sampling
```

### TTS Speed (`templates/index.html`)
```javascript
utterance.rate = 0.7;  // 70% of normal speed (for clarity)
```

---

## 📊 Pipeline Specifications

| Component | Details |
|-----------|---------|
| **Audio Format** | 16-bit PCM, 16kHz, Mono (WAV) |
| **STT Model** | Faster-Whisper base (Tamil) |
| **STT Latency** | 1-3s (CPU-dependent) |
| **LLM Model** | Qwen2.5 3B (int8 quantized) |
| **LLM Latency** | 5-15s (CPU-dependent) |
| **Token Budget** | 80 tokens per response |
| **Context Window** | 1024 tokens |
| **TTS** | Web Speech API (browser-native) |

---

## 🔧 Troubleshooting

### Issue: "Format not recognised" (STT error)
**Solution**: Ensure WAV encoding is correct. Check browser console for blob size > 1000 bytes.

### Issue: Truncated responses ("சொல்லுங்...")
**Solution**: Rebuild model with `PARAMETER num_predict 80` (was 35).

### Issue: Microphone not working
**Solution**: Click 🔧 Test Microphone button. Allow permissions when prompted. Wear headphones.

### Issue: LLM response doesn't match intent
**Solution**: Check Modelfile system prompt is loaded. Rebuild with `ollama create tamil-voice-qwen -f .\Modelfile.qwen_tamil`.

### Issue: "Cannot connect to Ollama"
**Solution**: Ensure `ollama serve` is running in another terminal on port 11434.

---

## 📝 Project Files

| File | Purpose |
|------|---------|
| `server.py` | FastAPI backend (STT, LLM orchestration) |
| `templates/index.html` | Web UI (recording, transcript, export) |
| `Modelfile.qwen_tamil` | Ollama model configuration (system prompt, parameters) |
| `requirements-web.txt` | Python dependencies |
| `.gitignore` | Git ignore patterns |

---

## 🎓 Key Improvements

### VAD (Voice Activity Detection)
- **min_silence_duration_ms**: 600ms (captures tail-end of speech)
- **threshold**: 0.4 (25% more sensitive for softer Tamil endings)

### Prompt Engineering
- **Balanced vocabulary**: Greetings + well-being + booking terms
- **Intent separation**: Explicit rules for different user queries
- **No truncation**: System prompt mandates "complete sentences"

### Token Budget
- **Before**: 35 tokens (~11 words) → **After**: 80 tokens (~32 words)
- **Impact**: Complete sentences instead of mid-word cuts

### Acoustic Feedback Prevention
- TTS cancellation before recording starts
- Prevents bot voice from being recorded as user input

---

## 🌍 Language Support

- **Primary**: Tamil (தமிழ்) - Spoken Tamil (பேச்சுத் தமிழ்)
- **Model**: Qwen2.5 3B (multilingual, fine-tuned for Tamil)
- **Whisper**: Base model (trained on multilingual data)

---

## 📊 Performance Benchmarks

On CPU (Intel i5 / Ryzen 5):
- **STT latency**: 1.5-3.5s (16-40 word sentence)
- **LLM latency**: 7-15s (response generation)
- **TTS latency**: <0.5s (playback start)
- **Total E2E latency**: ~10-20s per turn

---

## 🔐 Privacy & Security

✅ **No cloud calls** - Everything runs locally
✅ **No data transmission** - Conversation stays on your machine
✅ **No API keys** - No external dependencies
✅ **Open source** - Full code visibility

---

## 📄 License

This project is open source. Use and modify freely.

---

## 🤝 Contributing

Found a bug or have a feature request?
1. Test with clear Tamil utterances
2. Check logs: `server.log`
3. Document the issue with:
   - Input (Tamil text)
   - Expected output
   - Actual output
   - Error traceback (if any)

---

## 📚 References

- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) - Fast STT
- [Ollama](https://ollama.ai) - Local LLM runtime
- [Qwen2.5](https://huggingface.co/Qwen) - LLM model
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API) - Browser audio
- [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API) - Browser TTS

---

## 👤 Author

**ROBO WEB TECHNOLOGIES**

Built with ❤️ for the Tamil-speaking community.

---

**Version**: 1.0.0 (Production Ready)
**Last Updated**: November 2026
