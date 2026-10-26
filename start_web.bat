@echo off
REM Start the TAMIL-LLM web interface (backend + frontend)
REM
REM Prerequisites:
REM - Python 3.11+ installed
REM - Node.js 16+ installed  
REM - pip install -r backend/requirements.txt (from TAMIL-LLM root)
REM - cd frontend && npm install (from TAMIL-LLM root)
REM - Ollama running (ollama serve in another terminal)
REM
REM Note: This script opens 3 new terminal windows.
REM To stop a service, press Ctrl+C in its terminal.

echo.
echo ======================================================
echo  TAMIL-LLM Web Interface Startup
echo ======================================================
echo.
echo Starting Ollama in Terminal 1...
echo (Make sure Ollama is installed: https://ollama.com)
start cmd /k "ollama serve"

echo.
echo Starting backend (FastAPI) in Terminal 2...
echo (on port 8000)
start cmd /k "cd backend && python main.py"

echo.
echo Starting frontend (Vite React) in Terminal 3...
echo (on port 5173)
start cmd /k "cd frontend && npm run dev"

echo.
echo ======================================================
echo  Startup initiated!
echo  
echo  Frontend:  http://localhost:5173
echo  Backend:   http://localhost:8000
echo  API Docs:  http://localhost:8000/docs
echo  Ollama:    http://localhost:11434
echo.
echo  Each service opens in a new terminal window.
echo  To stop a service, press Ctrl+C in its terminal.
echo.
echo  First message may take 5-30 seconds (Ollama startup).
echo ======================================================
echo.
pause
