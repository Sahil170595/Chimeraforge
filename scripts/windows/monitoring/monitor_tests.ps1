# Monitor comprehensive test execution
Write-Host "Monitoring Technical Report 110 Comprehensive Tests" -ForegroundColor Cyan
Write-Host "=" * 80

# Check job status
$job = Get-Job -Name "TR110_Comprehensive_Tests" -ErrorAction SilentlyContinue
if ($job) {
    Write-Host "`nJob Status: $($job.State)" -ForegroundColor Yellow
    Write-Host "Job ID: $($job.Id)"
    Write-Host "Started: $($job.PSBeginTime)"
    
    # Get recent output
    $output = Receive-Job -Id $job.Id -Keep
    if ($output) {
        Write-Host "`n--- Recent Output (last 50 lines) ---" -ForegroundColor Green
        $output | Select-Object -Last 50
    }
}

# Check progress file
$progressFile = "banterhearts/demo_multiagent/comprehensive_test_results/test_execution_log.json"
if (Test-Path $progressFile) {
    Write-Host "`n--- Test Progress ---" -ForegroundColor Cyan
    $progress = Get-Content $progressFile | ConvertFrom-Json
    Write-Host "Total Tests: $($progress.total_tests)"
    Write-Host "Successful: $($progress.successful_tests)"
    Write-Host "Failed: $($progress.failed_tests)"
    Write-Host "Current Time: $($progress.current_time)"
    
    if ($progress.test_results) {
        $latest = $progress.test_results | Select-Object -Last 1
        Write-Host "`nLatest Test:"
        Write-Host "  Phase: $($latest.phase)"
        Write-Host "  Test ID: $($latest.test_id)"
        Write-Host "  Scenario: $($latest.scenario)"
        Write-Host "  Success: $($latest.success)"
    }
}

Write-Host "`n" + "=" * 80
Write-Host "Run this script again to check progress" -ForegroundColor Yellow

