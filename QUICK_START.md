# Quick Start Guide - Tamil Voice Assistant Web Interface

## 🎯 TL;DR - Get Running in 30 Seconds

### Step 1: Ensure Ollama is Running
```powershell
ollama serve
# Keep this terminal open
```

### Step 2: Start the Web Interface
```powershell
# In a new PowerShell terminal, navigate to the project folder:
cd C:\ROBO WEB TECHNOLOGIES\tamil-llama

# Run the quick start script (handles venv + dependencies):
.\start-web.ps1

# Or manually:
python -m pip install -r requirements-web.txt
python server.py
```

### Step 3: Open in Browser
```
http://localhost:8000
```

### Step 4: Use the Interface
1. Click the blue microphone button
2. Speak in Tamil or Tanglish
3. Release to send
4. Wait for bot response (will be spoken aloud)

---

## 📋 System Requirements

- **Python** 3.9+
- **Ollama** running with `tamil-voice-qwen` model
- **Microphone** for recording
- **Modern Browser** (Chrome, Firefox, Edge, Safari)

---

## 🔧 Installation (First Time Only)

```powershell
# Option A: Use the quick start script (recommended)
.\start-web.ps1

# Option B: Manual setup
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-web.txt
python server.py
```

---

## 🚀 Running the Server

### Method 1: PowerShell Script (Easiest)
```powershell
.\start-web.ps1
```
This will:
- Create venv if needed
- Install dependencies
- Check Ollama connection
- Start the server

### Method 2: Manual Command
```powershell
python server.py
```

### Method 3: With Uvicorn Options
```powershell
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 Access the Interface

**Local Browser:**
```
http://localhost:8000
```

**From Another Device (same network):**
```
http://<your-pc-ip>:8000
```

**API Documentation:**
```
http://localhost:8000/docs
```

---

## 🎤 Usage Tips

### Recording Audio
- **Click & Hold** the microphone button to record
- **Release** to submit
- Or use **Space Bar** to hold/release

### What Happens
1. Audio is recorded in your browser
2. Sent to Faster-Whisper for transcription
3. Tamil text sent to Ollama (Qwen model)
4. Response is spoken back via browser TTS

### Latencies Shown
- **STT**: Speech-to-Text (Faster-Whisper)
- **LLM**: Language Model response (Qwen)

---

## ⚡ Performance

| Task | Typical Time | Hardware |
|------|-------------|----------|
| STT (Transcription) | 1-2 seconds | CPU (base model, int8) |
| LLM (Response) | 2-5 seconds | CPU (Qwen) |
| TTS (Playback) | Real-time | Browser |

---

## 🐛 Troubleshooting

### "Connection Refused" to Ollama
**Problem:** Server can't connect to Ollama  
**Solution:** 
```powershell
ollama serve
# In another terminal, check:
curl http://localhost:11434/api/tags
```

### Microphone Not Working
**Problem:** Browser says "Microphone access denied"  
**Solution:**
1. Check browser permissions (address bar → lock icon)
2. Allow microphone for localhost
3. Reload page (Ctrl+F5)

### Empty Transcription
**Problem:** Audio recorded but no text  
**Solution:**
- Speak louder and clearer
- Check microphone input levels
- Try recording longer (2-3 seconds minimum)

### Ollama Model Not Found
**Problem:** "tamil-voice-qwen not found"  
**Solution:**
```powershell
ollama pull tamil-voice-qwen
```

### Server Won't Start
**Problem:** "Port 8000 already in use"  
**Solution:**
```powershell
# Find what's using port 8000
Get-NetTCPConnection -LocalPort 8000

# Kill the process or use different port:
python server.py --port 8001
```

---

## 📁 Project Structure

```
tamil-llama/
├── server.py                    # FastAPI backend
├── templates/
│   └── index.html              # Web UI (no build needed)
├── requirements-web.txt        # Python dependencies
├── start-web.ps1              # Quick start script
├── call_agent.py              # Original CLI version
├── WEB_INTERFACE_README.md    # Full documentation
└── QUICK_START.md             # This file
```

---

## 🔌 API Reference

### Health Check
```bash
curl http://localhost:8000/api/health
# Response: {"ollama": true, "whisper": true}
```

### Voice Turn (Main Endpoint)
```bash
curl -X POST http://localhost:8000/api/voice-turn \
  -F "file=@audio.webm"
# Response: {
#   "user_text": "...",
#   "bot_text": "...",
#   "stt_latency_ms": 1250,
#   "llm_latency_ms": 3450
# }
```

---

## 💡 Pro Tips

### Keyboard Shortcuts
- **Space Bar**: Hold to record, release to send
- **Ctrl+C**: Stop server (in terminal)

### Development
- Edit `templates/index.html` for UI changes (no build step)
- Edit `server.py` for backend logic
- Changes take effect after page reload (Ctrl+F5)

### Performance
- Use `--reload` with uvicorn during development
- Monitor CPU usage when running STT and LLM
- Consider GPU acceleration for faster transcription

---

## 📞 Support

1. **Check server logs** (terminal where server is running)
2. **Check browser console** (F12 → Console tab)
3. **Verify Ollama** is running and model exists
4. **Review** WEB_INTERFACE_README.md for detailed docs

---

## Next Steps

- [ ] Customize the Tamil prompt in `server.py` (line ~52)
- [ ] Adjust microphone sensitivity/recording duration
- [ ] Add session history/logging
- [ ] Deploy to a server (change CORS settings)
- [ ] Experiment with different Ollama models

---

**Enjoy your Tamil Voice Assistant! 🎙️**
