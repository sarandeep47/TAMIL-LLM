# Quick Start — Web Interface

Get the TAMIL-LLM web chat running in 5 minutes.

## Prerequisites

- Python 3.11+
- Node.js 16+ and npm
- Ollama running locally (`ollama serve`)

## Installation (One-time)

### 1. Backend

```powershell
cd backend
pip install -r requirements.txt
```

### 2. Frontend

```powershell
cd frontend
npm install
```

## Startup

### Option A: Three Terminal Windows (Recommended for debugging)

**Terminal 1 — Ollama:**
```powershell
ollama serve
```

**Terminal 2 — Backend:**
```powershell
cd backend
python main.py
```

**Terminal 3 — Frontend:**
```powershell
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

### Option B: Batch File (Windows Command Prompt)

```powershell
.\start_web.bat
```

This opens all 3 services in separate terminals.

### Option C: PowerShell Script

```powershell
.\start_web.ps1
```

This opens services in separate PowerShell windows and checks if they're already running.

## First Message

1. Type: `naa cse padichen college la` (I studied CSE at college)
2. Press Enter or click Send
3. Wait for the response (5-30 seconds)
4. The chatbot will acknowledge the fact in Tanglish

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Ollama unavailable" at bottom left | Run `ollama serve` in another terminal |
| Port 8000 already in use | Change `API_PORT` in `backend/.env` |
| Port 5173 already in use | Vite will auto-select a different port |
| Blank screen after clicking Send | Check browser console (F12) for errors |
| Backend crashes | Check `backend/.env` paths and permissions |

## Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend | 5173 | http://localhost:5173 |
| Backend | 8000 | http://localhost:8000 |
| API Docs | 8000 | http://localhost:8000/docs |
| Ollama | 11434 | http://localhost:11434 |

## Next Steps

- **Chat naturally** — the bot extracts facts from your messages
- **Check memories** — see what the bot learned via "Get memories" button (future feature)
- **Read API docs** — visit http://localhost:8000/docs for interactive API explorer
- **View code** — see `frontend/src/App.jsx` for main chat logic

## Terminal Commands

### Stop Backend
Press Ctrl+C in Terminal 1

### Stop Frontend
Press Ctrl+C in Terminal 2

### View API Documentation
http://localhost:8000/docs (interactive Swagger UI)

### Run Tests
```powershell
cd backend
python -m pytest tests/test_api.py -v
```

### Build Frontend for Production
```powershell
cd frontend
npm run build
# Output: frontend/dist/ (ready to deploy)
```

---

For full documentation, see:
- `README.md` — Project overview
- `API.md` — API reference
- `backend/main.py` — Backend code
- `frontend/src/App.jsx` — Frontend code
