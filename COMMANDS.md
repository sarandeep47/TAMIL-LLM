# Quick Command Reference

## Installation

```powershell
# Backend dependencies
cd backend
pip install -r requirements.txt
cd ..

# Frontend dependencies
cd frontend
npm install
cd ..
```

## Starting Services

### Terminal 1: Ollama
```powershell
ollama serve
```

### Terminal 2: Backend
```powershell
cd backend
python main.py
```

### Terminal 3: Frontend
```powershell
cd frontend
npm run dev
```

## Quick Checks

```powershell
# Check Python version
python --version

# Check Node.js version
node --version

# Check npm version
npm --version

# Check Ollama is running
curl http://localhost:11434/api/tags

# Check Backend is running
curl http://localhost:8000/health

# Open Frontend in browser
start http://localhost:5173

# View API Documentation
start http://localhost:8000/docs
```

## Testing

```powershell
# Run backend tests
cd backend
python -m pytest tests/test_api.py -v

# Run existing chatbot tests (verify no regression)
cd ..
python -m pytest tests/test_chatbot.py -q

# Run all tests
python -m pytest tests/ -q
```

## Stopping Services

In each terminal, press **Ctrl+C** to stop the service.

## Automated Startup

```powershell
# PowerShell script (recommended)
.\start_web.ps1

# Batch file
.\start_web.bat
```

## File Locations

| What | Location |
|------|----------|
| Backend code | `backend/main.py` |
| Frontend code | `frontend/src/App.jsx` |
| Backend config | `backend/.env` |
| Frontend config | `frontend/.env.local` (optional) |
| Database (memory) | `data/processed/memory.db` |
| Database (chat) | `data/processed/chatbot.db` |

## Ports

| Service | Port | URL |
|---------|------|-----|
| Ollama | 11434 | http://localhost:11434 |
| Backend | 8000 | http://localhost:8000 |
| Frontend | 5173 | http://localhost:5173 |
| API Docs | 8000 | http://localhost:8000/docs |

## API Endpoints

```bash
# Health check
GET http://localhost:8000/health

# Send message
POST http://localhost:8000/api/chat
Body: { "message": "Your message here" }

# Get memories
GET http://localhost:8000/api/memories
```

## Documentation

| File | Purpose |
|------|---------|
| QUICKSTART.md | 5-minute setup |
| SETUP_POWERSHELL.md | PowerShell guide (you are here) |
| README.md | Full documentation |
| API.md | API reference |
| VERIFICATION_CHECKLIST.md | Testing guide |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Shift+Enter | New line in message |
| Ctrl+C (in terminal) | Stop service |
| F12 (in browser) | Open developer console |

## Useful PowerShell Tips

```powershell
# Open new PowerShell window in current directory
start powershell

# Clear screen
clear

# List files
ls

# Go to parent directory
cd ..

# Go to home directory
cd ~

# Search for running process using port
Get-NetTCPConnection -LocalPort 8000

# Stop a process by name
Stop-Process -Name python -Force
```

## Common Issues & Quick Fixes

| Issue | Fix |
|-------|-----|
| `pip not recognized` | Use `python -m pip install` instead |
| `npm not recognized` | Install Node.js from nodejs.org |
| `Port 8000 in use` | Change `API_PORT` in `backend/.env` |
| `Ollama unavailable` | Run `ollama serve` in another terminal |
| `Module not found` | Run `pip install -r requirements.txt` or `npm install` |
| `Can't connect to backend` | Check backend is running in Terminal 2 |

## Versions Required

- Python 3.11 or higher
- Node.js 16 or higher  
- npm (comes with Node.js)
- Ollama (latest)

Check versions with:
```powershell
python --version
node --version
npm --version
ollama --version
```

---

**Ready? Start with SETUP_POWERSHELL.md or run: `.\start_web.ps1`**
