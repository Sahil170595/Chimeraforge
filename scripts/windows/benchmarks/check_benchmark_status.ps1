# Check benchmark status
Write-Host "Checking Rust benchmark status..." -ForegroundColor Cyan
Write-Host ""

if (Test-Path rust_benchmark_results) {
    Write-Host "[OK] Results directory exists" -ForegroundColor Green
    
    # Count completed configs
    $configs = Get-ChildItem rust_benchmark_results -Directory
    Write-Host "  Configs started: $($configs.Count)" -ForegroundColor Gray
    
    # Check for metrics files (indicates completion)
    $completed = 0
    foreach ($config in $configs) {
        if (Test-Path "$($config.FullName)\data\metrics.json") {
            $completed++
        }
    }
    Write-Host "  Configs completed: $completed" -ForegroundColor Gray
    
    # Show latest results if available
    if ($completed -gt 0) {
        Write-Host ""
        Write-Host "Latest completed configs:" -ForegroundColor Yellow
        foreach ($config in $configs) {
            $metricsFile = "$($config.FullName)\data\metrics.json"
            if (Test-Path $metricsFile) {
                $metrics = Get-Content $metricsFile | ConvertFrom-Json
                $throughput = $metrics.chimera.aggregate_metrics.average_tokens_per_second
                $ttft = $metrics.chimera.aggregate_metrics.average_ttft_ms
                Write-Host "  $($config.Name): $([math]::Round($throughput, 2)) tok/s, TTFT $([math]::Round($ttft, 0))ms" -ForegroundColor White
            }
        }
    }
    
    # Check if summary exists (all done)
    if (Test-Path rust_benchmark_results\benchmark_results.json) {
        Write-Host ""
        Write-Host "[DONE] Benchmark complete! Run: python analyze_rust_results.py" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "[..] Benchmark still running..." -ForegroundColor Yellow
    }
} else {
    Write-Host "[WAIT] Benchmark not started or no results yet..." -ForegroundColor Yellow
}

Write-Host ""



