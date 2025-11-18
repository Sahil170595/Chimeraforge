# Minimal Rust benchmark runner - just execute the Python script
# Use this if you want PowerShell wrapper

Write-Host "Starting Rust Agent Benchmark Sweep..." -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is running
$ollamaRunning = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaRunning) {
    Write-Host "[WARN] Ollama doesn't appear to be running" -ForegroundColor Yellow
    Write-Host "Start Ollama before continuing"
    Write-Host ""
}

# Check if model is available
Write-Host "Checking if gemma3:latest is available..." -ForegroundColor Gray
ollama list | Select-String "gemma3"

Write-Host ""
Write-Host "Starting benchmark..." -ForegroundColor Green
Write-Host ""

python run_rust_benchmark_sweep.py

Write-Host ""
Write-Host "[DONE] Benchmark complete!" -ForegroundColor Green
Write-Host "Results in: rust_benchmark_results/" -ForegroundColor Cyan



