# TR117 Tier 3 Launcher - Runs in detached process
# Safe to close this terminal after launch

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "TR117 TIER 3 LAUNCHER" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$scriptPath = Join-Path $PSScriptRoot "run_tr117_tier3.ps1"

if (-not (Test-Path $scriptPath)) {
    Write-Host "ERROR: Script not found: $scriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "Launching TR117 Tier 3 benchmark in detached window..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Benchmark details:" -ForegroundColor White
Write-Host "  - Total runs: 12,348" -ForegroundColor White
Write-Host "  - Estimated time: 10-20 hours" -ForegroundColor White
Write-Host "  - Models: 6 (124M to 8B)" -ForegroundColor White
Write-Host "  - Backends: 7 (full sweep)" -ForegroundColor White
Write-Host "  - Statistical reps: 7" -ForegroundColor White
Write-Host ""
Write-Host "Monitor progress:" -ForegroundColor Yellow
Write-Host "  - Check log: Get-Content results/tr117_tier3/logs/run_*.log -Tail 20 -Wait" -ForegroundColor Gray
Write-Host "  - Count runs: (Get-ChildItem -Recurse results/tr117_tier3/runs -Filter 'run_*.json').Count" -ForegroundColor Gray
Write-Host ""

$confirm = Read-Host "Launch benchmark? (yes/no)"

if ($confirm -eq "yes") {
    Write-Host ""
    Write-Host "Starting benchmark in new window..." -ForegroundColor Green
    
    # Launch in minimized window that persists
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" -WindowStyle Normal
    
    Write-Host ""
    Write-Host "✓ Benchmark launched!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The benchmark is running in a separate window." -ForegroundColor Cyan
    Write-Host "You can safely close this terminal." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To monitor:" -ForegroundColor Yellow
    Write-Host "  1. Check the benchmark window for live updates"
    Write-Host "  2. Tail the log file (see command above)"
    Write-Host "  3. Count completed runs (see command above)"
    Write-Host ""
    Write-Host "Expected completion: $(((Get-Date).AddHours(17)).ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Benchmark launch cancelled." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

