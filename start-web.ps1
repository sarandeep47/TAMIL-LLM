# Tamil Voice Assistant Web Interface - Quick Start Script
# Windows PowerShell

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Tamil Voice Assistant - Web Interface Launcher          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python not found. Please install Python 3.9+ and try again." -ForegroundColor Red
    exit 1
}

Write-Host "✓ Python found: $(python --version)" -ForegroundColor Green

# Check if venv exists
if (!(Test-Path "venv")) {
    Write-Host "⚠ Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate venv
Write-Host "⚙ Activating virtual environment..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Check if dependencies are installed
Write-Host "⚙ Checking dependencies..." -ForegroundColor Cyan
pip show fastapi > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚙ Installing dependencies from requirements-web.txt..." -ForegroundColor Cyan
    pip install -r requirements-web.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install dependencies." -ForegroundColor Red
        exit 1
    }
}

Write-Host "✓ Dependencies ready" -ForegroundColor Green
Write-Host ""

# Check Ollama health
Write-Host "🔍 Checking Ollama connection..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ Ollama is running at http://localhost:11434" -ForegroundColor Green
        
        # Check for tamil-voice-qwen model
        $json = $response.Content | ConvertFrom-Json
        $hasModel = $json.models | Where-Object { $_.name -like "*tamil-voice-qwen*" }
        if ($hasModel) {
            Write-Host "✓ Model 'tamil-voice-qwen' is available" -ForegroundColor Green
        } else {
            Write-Host "⚠ Model 'tamil-voice-qwen' not found. Ollama will try to pull it on first use." -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "⚠ Ollama not running. Make sure Ollama is started with: ollama serve" -ForegroundColor Yellow
    Write-Host "  Then run this script again." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  🚀 Starting FastAPI Server...                            ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Web Interface: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📚 Documentation: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server
python server.py
