# Tamil Voice Assistant - Setup Verification Script
# Checks all dependencies and configurations before running

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Tamil Voice Assistant - Setup Verification Tool         ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# ============ 1. Python Check ============
Write-Host "🔍 Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "✗ Python not found. Install Python 3.9+ and add to PATH." -ForegroundColor Red
    $allGood = $false
}

# ============ 2. Ollama Check ============
Write-Host ""
Write-Host "🔍 Checking Ollama..." -ForegroundColor Yellow
try {
    $ollamaResponse = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($ollamaResponse.StatusCode -eq 200) {
        Write-Host "✓ Ollama is running at http://localhost:11434" -ForegroundColor Green
        
        # Check for model
        $json = $ollamaResponse.Content | ConvertFrom-Json
        $models = $json.models | ForEach-Object { $_.name -replace ":.*", "" }
        
        if ($models -contains "tamil-voice-qwen") {
            Write-Host "✓ Model 'tamil-voice-qwen' is available" -ForegroundColor Green
        } else {
            Write-Host "⚠ Model 'tamil-voice-qwen' not found" -ForegroundColor Yellow
            Write-Host "  Available models: $($models -join ', ')" -ForegroundColor Gray
            Write-Host "  Run: ollama pull tamil-voice-qwen" -ForegroundColor Cyan
        }
    }
} catch {
    Write-Host "✗ Ollama is not running" -ForegroundColor Red
    Write-Host "  Make sure Ollama is started: ollama serve" -ForegroundColor Cyan
    $allGood = $false
}

# ============ 3. Project Files Check ============
Write-Host ""
Write-Host "🔍 Checking Project Files..." -ForegroundColor Yellow

$files = @(
    "server.py",
    "templates/index.html",
    "requirements-web.txt",
    "QUICK_START.md",
    "WEB_INTERFACE_README.md"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "✓ $file" -ForegroundColor Green
    } else {
        Write-Host "✗ $file (missing)" -ForegroundColor Red
        $allGood = $false
    }
}

# ============ 4. Virtual Environment Check ============
Write-Host ""
Write-Host "🔍 Checking Virtual Environment..." -ForegroundColor Yellow

if (Test-Path "venv") {
    Write-Host "✓ Virtual environment exists (venv/)" -ForegroundColor Green
} else {
    Write-Host "⚠ Virtual environment not found" -ForegroundColor Yellow
    Write-Host "  It will be created when you run start-web.ps1" -ForegroundColor Cyan
}

# ============ 5. Dependencies Check ============
Write-Host ""
Write-Host "🔍 Checking Python Dependencies..." -ForegroundColor Yellow

$requiredPackages = @(
    "fastapi",
    "uvicorn",
    "python-multipart",
    "requests",
    "numpy",
    "faster-whisper"
)

$missingPackages = @()
foreach ($pkg in $requiredPackages) {
    pip show $pkg > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ $pkg" -ForegroundColor Green
    } else {
        Write-Host "⚠ $pkg (not installed)" -ForegroundColor Yellow
        $missingPackages += $pkg
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host ""
    Write-Host "  To install missing packages:" -ForegroundColor Cyan
    Write-Host "  pip install -r requirements-web.txt" -ForegroundColor Cyan
}

# ============ 6. Port Check ============
Write-Host ""
Write-Host "🔍 Checking Port 8000..." -ForegroundColor Yellow

try {
    $portCheck = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($portCheck) {
        Write-Host "⚠ Port 8000 is already in use" -ForegroundColor Yellow
        Write-Host "  Process: $($portCheck.OwningProcess)" -ForegroundColor Gray
        Write-Host "  Make sure to stop any existing servers first" -ForegroundColor Cyan
    } else {
        Write-Host "✓ Port 8000 is available" -ForegroundColor Green
    }
} catch {
    Write-Host "✓ Port 8000 is available" -ForegroundColor Green
}

# ============ 7. File Permissions Check ============
Write-Host ""
Write-Host "🔍 Checking File Permissions..." -ForegroundColor Yellow

try {
    $testFile = ".kiro-test-write"
    "test" | Out-File $testFile -Force
    Remove-Item $testFile -Force
    Write-Host "✓ Can write to project directory" -ForegroundColor Green
} catch {
    Write-Host "✗ Cannot write to project directory" -ForegroundColor Red
    $allGood = $false
}

# ============ SUMMARY ============
Write-Host ""
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan

if ($allGood) {
    Write-Host "✅ All checks passed! You're ready to go." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Run: .\start-web.ps1" -ForegroundColor White
    Write-Host "2. Open: http://localhost:8000" -ForegroundColor White
    Write-Host "3. Speak in Tamil!" -ForegroundColor White
} else {
    Write-Host "⚠️  Some issues detected. See above for details." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Common fixes:" -ForegroundColor Cyan
    Write-Host "• Start Ollama: ollama serve" -ForegroundColor White
    Write-Host "• Install dependencies: pip install -r requirements-web.txt" -ForegroundColor White
    Write-Host "• Pull model: ollama pull tamil-voice-qwen" -ForegroundColor White
    Write-Host "• Free port 8000: Close any running servers" -ForegroundColor White
}

Write-Host ""
Write-Host "📚 Documentation:" -ForegroundColor Cyan
Write-Host "• QUICK_START.md - 30-second setup guide" -ForegroundColor Gray
Write-Host "• WEB_INTERFACE_README.md - Full documentation" -ForegroundColor Gray
Write-Host "• config.example.py - Configuration options" -ForegroundColor Gray
Write-Host ""
