# Quick Start - Tamil Voice Assistant Web Interface

## ⚡ Start Here

### 1. Prerequisites
- **Ollama Running**: `ollama serve` in a terminal
- **Model Available**: `ollama pull tamil-voice-qwen`
- **Python Dependencies**: Already installed via `pip install -r requirements-web.txt`

### 2. Start the Web Server

```powershell
cd "c:\ROBO WEB TECHNOLOGIES\tamil-llama"
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

**Expected Output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:server:Initializing Faster-Whisper (optimized CPU settings)...
INFO:     Application startup complete.
```

### 3. Open Browser

Navigate to: **`http://127.0.0.1:8000`**

### 4. Test the Interface

1. **Check Status**: Look at the top - should show green dots for ✓ Ollama and ✓ Whisper
2. **Click Microphone**: Large blue circle in the middle
3. **Speak Tamil**: Say something like "வணக்கம்" (Hello) or "நன்றி" (Thank you)
4. **Speak for 3+ seconds**: Wait until you release
5. **Release**: Stop pressing/speaking
6. **See Results**:
   - Your question appears (blue bubble, right side)
   - Bot reply appears (gray bubble, left side)
   - Latencies shown: `[STT: XXXms]` and `[LLM: XXXms]`
   - Bot speaks the reply automatically

### 5. Export Conversation

- **📋 View Output**: Opens a modal with formatted transcript
- **📋 Copy Output**: Copies to clipboard (paste anywhere with Ctrl+V)
- **⬇️ Download TXT**: Downloads as `.txt` file to your computer
- **🗑️ Clear History**: Resets the conversation

### 6. Troubleshoot

#### Red Status Pills (Not Connected)
- **Ollama**: Run `ollama serve` in another terminal
- **Whisper**: Wait a few seconds (loading), then refresh page

#### Microphone Says "Denied"
- Click **🔧 Test Microphone** button
- Allow microphone permission when browser asks
- Refresh page (Ctrl+R) and try again

#### No Audio Captured (Empty Response)
- Speak louder and longer (3+ seconds)
- Make sure your microphone is plugged in and working
- Try the test microphone tool

#### Bot Doesn't Reply (LLM: 0ms)
- Check Ollama is running: `ollama list` should show `tamil-voice-qwen`
- If model not listed: `ollama pull tamil-voice-qwen`

---

## 📊 What You Should See

```
┌─────────────────────────────────────┐
│  Tamil Voice Assistant              │
│  🟢 Ollama  🟢 Whisper              │
├─────────────────────────────────────┤
│                                     │
│         YOU: வணக்கம்                 │
│         [STT: 2450ms]              │
│                                     │
│         BOT: வணக்கம்! உன்னிடம் என்ன வ│
│         [LLM: 3210ms]              │
│                                     │
├─────────────────────────────────────┤
│        🎤  (Tap to Speak)           │
│   🔧 Test Microphone                │
│                                     │
│  📋 View  📋 Copy  ⬇️ Download  🗑️ │
└─────────────────────────────────────┘
```

---

## 🔬 Technical Details

### Audio Flow
```
Browser Microphone → 16kHz PCM → WAV Encoding → Server
                                                     ↓
                                    soundfile.read() ↓
                                                 Faster-Whisper (STT) ↓
                                           Ollama LLM Query ↓
                                                              Response
                                                                  ↓
                                                    Display + TTS Playback
```

### Key Technologies
- **Browser**: Web Audio API (ScriptProcessorNode at 16kHz)
- **Format**: Standard 16-bit PCM WAV (no codecs)
- **STT**: Faster-Whisper (CPU-optimized, Tamil language)
- **LLM**: Ollama + tamil-voice-qwen model
- **TTS**: Web Speech API (browser native, Tamil voice)
- **Server**: FastAPI with soundfile (no FFmpeg needed)

---

## 📝 Notes

- **Recording**: Hold mic button or press Space to start; release to stop
- **Latencies**: 
  - STT (Whisper): 1-5 seconds depending on audio length
  - LLM (Qwen): 2-10 seconds depending on reply length
- **Local-Only**: No internet needed; everything runs on your machine
- **Dependencies**: soundfile (WAV parsing), faster-whisper, ollama (external service)

---

## 🚀 Performance Tips

1. **First Load**: Faster-Whisper model downloads on startup (~500MB), then cached
2. **CPU Usage**: Expect 80-100% CPU during STT/LLM processing (normal)
3. **RAM**: ~4GB free recommended (Whisper + Ollama)
4. **Multiple Turns**: Conversation persists in browser; use "Clear History" to reset

---

## ✅ You're All Set!

- ✓ Server running at http://127.0.0.1:8000
- ✓ Audio format is native WAV (no codec issues)
- ✓ Ollama integration working
- ✓ Export features ready
- ✓ Diagnostics tool available

**Next**: Open your browser and start speaking Tamil! 🎤
