# Quick Rust agent test to verify it works
Write-Host "Testing Rust Agent..." -ForegroundColor Cyan
Write-Host ""

$testDir = "Demo_rust_agent_quick_test"
Remove-Item -Path $testDir -Recurse -Force -ErrorAction SilentlyContinue

cd Demo_rust_agent
.\target\release\demo_rust_agent.exe --model gemma3:latest --runs 1 --output-dir "../$testDir" --chimera-num-gpu 80 --chimera-num-ctx 1024 --chimera-temperature 0.8

cd ..

Write-Host ""
Write-Host "Test complete! Checking results..." -ForegroundColor Green
Write-Host ""

if (Test-Path "$testDir/reports/comparison_report.md") {
    Write-Host "✓ Reports generated successfully" -ForegroundColor Green
    Write-Host ""
    Get-Content "$testDir/reports/comparison_report.md" | Select-Object -First 30
} else {
    Write-Host "❌ Report generation failed" -ForegroundColor Red
}



