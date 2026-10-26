# Start the TAMIL-LLM web interface (backend + frontend)
#
# Usage: .\start_web.ps1
#
# Prerequisites:
# - Python 3.11+ installed
# - Node.js 16+ installed
# - cd backend; pip install -r requirements.txt (from TAMIL-LLM root)
# - cd frontend; npm install (from TAMIL-LLM root)
# - Ollama running (ollama serve in another terminal)

Write-Host ""
Write-Host "======================================================"
Write-Host "  TAMIL-LLM Web Interface Startup"
Write-Host "======================================================"
Write-Host ""

# Check if backends are already running
$ollama_running = $null -ne (Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue)
$backend_running = $null -ne (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue)
$frontend_running = $null -ne (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue)

if ($ollama_running) {
    Write-Host "✓ Ollama already running on port 11434"
} else {
    Write-Host "ℹ Ollama not detected. Start it with: ollama serve"
}

if ($backend_running) {
    Write-Host "✓ Backend already running on port 8000"
} else {
    Write-Host "Starting backend..."
    Start-Process PowerShell -ArgumentList "cd backend; python main.py"
    Write-Host "  → Backend starting on http://localhost:8000"
}

if ($frontend_running) {
    Write-Host "✓ Frontend already running on port 5173"
} else {
    Write-Host "Starting frontend..."
    Start-Process PowerShell -ArgumentList "cd frontend; npm run dev"
    Write-Host "  → Frontend starting on http://localhost:5173"
}

Write-Host ""
Write-Host "======================================================"
Write-Host "  Ready to go!"
Write-Host ""
Write-Host "  Frontend:  http://localhost:5173"
Write-Host "  Backend:   http://localhost:8000"
Write-Host "  API Docs:  http://localhost:8000/docs"
Write-Host "  Ollama:    http://localhost:11434"
Write-Host ""
Write-Host "  To stop a service, press Ctrl+C in its terminal."
Write-Host "  First message may take 5-30 seconds (Ollama startup)."
Write-Host "======================================================"
Write-Host ""
