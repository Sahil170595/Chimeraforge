# Setup Dual Ollama Instances for True Concurrent Multi-Agent Benchmarking
# Based on TR110 methodology (Python multi-agent)

Write-Host "=== Setting Up Dual Ollama Instances ===" -ForegroundColor Cyan

# Check if Ollama is installed
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "ERROR: Ollama not found in PATH" -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/5] Checking existing Ollama processes..." -ForegroundColor Yellow
$existingProcesses = Get-Process ollama -ErrorAction SilentlyContinue
if ($existingProcesses) {
    Write-Host "Found running Ollama processes. Stopping them..." -ForegroundColor Yellow
    Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Write-Host "`n[2/5] Creating Ollama instance directories..." -ForegroundColor Yellow
$instance1Dir = "$env:USERPROFILE\.ollama_instance1"
$instance2Dir = "$env:USERPROFILE\.ollama_instance2"

New-Item -ItemType Directory -Force -Path $instance1Dir | Out-Null
New-Item -ItemType Directory -Force -Path $instance2Dir | Out-Null

Write-Host "  Instance 1: $instance1Dir"
Write-Host "  Instance 2: $instance2Dir"

Write-Host "`n[3/5] Starting Ollama Instance 1 (port 11434)..." -ForegroundColor Yellow
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_MODELS = $instance1Dir
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -PassThru | Out-Null
Start-Sleep -Seconds 3

Write-Host "`n[4/5] Starting Ollama Instance 2 (port 11435)..." -ForegroundColor Yellow
# Start second instance in a new PowerShell window with environment variables
$startScript2 = @"
`$env:OLLAMA_HOST = '127.0.0.1:11435'
`$env:OLLAMA_MODELS = '$instance2Dir'
cd '$PWD'
ollama serve
"@
$startScript2 | Out-File -FilePath "$env:TEMP\start_ollama2.ps1" -Encoding UTF8

# Start in a new window so environment variables are properly set
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "`$env:OLLAMA_HOST='127.0.0.1:11435'; `$env:OLLAMA_MODELS='$instance2Dir'; ollama serve" -WindowStyle Minimized
Start-Sleep -Seconds 5

Write-Host "`n[5/5] Verifying instances..." -ForegroundColor Yellow
try {
    $test1 = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "   Instance 1 (port 11434): RUNNING" -ForegroundColor Green
} catch {
    Write-Host "   Instance 1 (port 11434): FAILED" -ForegroundColor Red
}

try {
    $test2 = Invoke-WebRequest -Uri "http://localhost:11435/api/tags" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "   Instance 2 (port 11435): RUNNING" -ForegroundColor Green
} catch {
    Write-Host "   Instance 2 (port 11435): FAILED" -ForegroundColor Red
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "`nTo use dual instances with Rust multi-agent:" -ForegroundColor White
Write-Host "  .\Demo_rust_multiagent\target\release\Demo_rust_multiagent.exe \" -ForegroundColor Gray
Write-Host "    --model gemma3:latest \" -ForegroundColor Gray
Write-Host "    --scenario chimera_homo \" -ForegroundColor Gray
Write-Host "    --collector-ollama-url http://localhost:11434 \" -ForegroundColor Gray
Write-Host "    --insight-ollama-url http://localhost:11435 \" -ForegroundColor Gray
Write-Host "    --chimera-num-gpu 80 \" -ForegroundColor Gray
Write-Host "    --chimera-num-ctx 1024 \" -ForegroundColor Gray
Write-Host "    --chimera-temperature 0.6" -ForegroundColor Gray

Write-Host "`nTo stop both instances:" -ForegroundColor White
Write-Host "  Stop-Process -Name ollama -Force" -ForegroundColor Gray

Write-Host "`nNote: Model will need to be loaded on BOTH instances." -ForegroundColor Yellow
Write-Host "First run will download/load the model on each instance." -ForegroundColor Yellow

