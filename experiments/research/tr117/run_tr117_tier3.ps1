# TR117 Tier 3 Full Benchmark Runner
# This script is designed to run independently and survive terminal closure

$ErrorActionPreference = "Continue"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "TR117 TIER 3 FULL BENCHMARK - Starting..." -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to project root
Set-Location "C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts"
Write-Host "Working directory: $(Get-Location)" -ForegroundColor Green

# Create log directory
$logDir = "results/tr117_tier3/logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "$logDir/run_$timestamp.log"

Write-Host "Log file: $logFile" -ForegroundColor Green
Write-Host ""

# Save current power settings
Write-Host "Saving current power settings..." -ForegroundColor Yellow
$sleepAC = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Current AC Power Setting Index:").ToString().Split(":")[-1].Trim()
$monitorAC = (powercfg /query SCHEME_CURRENT SUB_VIDEO VIDEOIDLE | Select-String "Current AC Power Setting Index:").ToString().Split(":")[-1].Trim()

# Disable sleep during benchmark
Write-Host "Disabling system sleep for benchmark duration..." -ForegroundColor Yellow
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change monitor-timeout-ac 30 | Out-Null

# Set environment variables
$env:PYTHONPATH = "."
$env:BANTER_TRANSFORMER_MODEL = "models/tiny-gpt2"
$env:BANTER_OLLAMA_MODEL = "gemma3:latest"
$env:HF_HUB_OFFLINE = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Environment configured:" -ForegroundColor Green
Write-Host "  PYTHONPATH: $env:PYTHONPATH"
Write-Host "  BANTER_TRANSFORMER_MODEL: $env:BANTER_TRANSFORMER_MODEL"
Write-Host "  HF_HUB_OFFLINE: $env:HF_HUB_OFFLINE"
Write-Host ""

# Record start time
$startTime = Get-Date
Write-Host "Start time: $startTime" -ForegroundColor Cyan
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "BENCHMARK RUNNING - This will take 10-20 hours" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Progress monitoring:" -ForegroundColor Yellow
Write-Host "  - Log file: $logFile"
Write-Host "  - Run count: Get-ChildItem -Recurse results/tr117_tier3/runs -Filter 'run_*.json' | Measure-Object | Select-Object Count"
Write-Host ""
Write-Host "You can close this window - the process will continue." -ForegroundColor Green
Write-Host ""

# Run benchmark with logging
try {
    python scripts/tr117/run_matrix.py `
        --config scripts/tr117/configs/matrix_tier3_full.yaml `
        --output-root results/tr117_tier3/runs `
        2>&1 | Tee-Object -FilePath $logFile
    
    $exitCode = $LASTEXITCODE
    
    $endTime = Get-Date
    $duration = $endTime - $startTime
    
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Cyan
    if ($exitCode -eq 0) {
        Write-Host "BENCHMARK COMPLETED SUCCESSFULLY" -ForegroundColor Green
    } else {
        Write-Host "BENCHMARK COMPLETED WITH ERRORS (exit code: $exitCode)" -ForegroundColor Red
    }
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Start time: $startTime" -ForegroundColor White
    Write-Host "End time: $endTime" -ForegroundColor White
    Write-Host "Duration: $($duration.Hours)h $($duration.Minutes)m $($duration.Seconds)s" -ForegroundColor White
    Write-Host ""
    
    # Run analysis
    Write-Host "Running post-benchmark analysis..." -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "1. Aggregating metrics..." -ForegroundColor White
    python scripts/tr117/analyze_tr117.py `
        --runs-root results/tr117_tier3/runs `
        --output results/tr117_tier3/metrics.csv
    
    Write-Host "2. Statistical analysis..." -ForegroundColor White
    python scripts/tr117/statistical_analysis.py
    
    Write-Host "3. Cost analysis..." -ForegroundColor White
    python scripts/tr117/cost_analysis.py `
        --metrics results/tr117_tier3/metrics.csv `
        --output results/tr117_tier3/cost_analysis.json
    
    Write-Host "4. Capturing environment..." -ForegroundColor White
    python scripts/tr117/env_capture.py
    
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "ALL ANALYSIS COMPLETE" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Results location: results/tr117_tier3/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Key outputs:" -ForegroundColor White
    Write-Host "  - metrics.csv (aggregated data)"
    Write-Host "  - statistical_analysis.json (CIs, p-values, effect sizes)"
    Write-Host "  - cost_analysis.json ($/1M tokens, efficiency)"
    Write-Host "  - latency_by_backend.png (visualization)"
    Write-Host "  - env.json (reproducibility)"
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "ERROR: Benchmark failed" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
} finally {
    # Restore power settings
    Write-Host "Restoring power settings..." -ForegroundColor Yellow
    powercfg /change standby-timeout-ac $sleepAC | Out-Null
    powercfg /change monitor-timeout-ac $monitorAC | Out-Null
    
    Write-Host ""
    Write-Host "Log file saved: $logFile" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

