# Run TR116 Python multi-agent benchmarks (dual Ollama required on 11434/11435)
# Usage: powershell -ExecutionPolicy Bypass -File experiments/TR116/scripts/run_tr116_python_multi.ps1
# Optional: -Runs 5 (default)

param(
    [int]$Runs = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot/../../.."
Set-Location $repoRoot

$env:PYTHONPATH = "$($repoRoot)\src\python"

$models = @(
    @{ name = "qwen2.5:7b"; slug = "qwen2p5_7b" },
    @{ name = "gemma3:latest"; slug = "gemma3_latest" },
    @{ name = "llama3.1:8b-instruct-q4_0"; slug = "llama3p1_8b_q4_0" }
)

$scenarios = @(
    "baseline_vs_chimera",
    "chimera_homo"
)

foreach ($m in $models) {
    foreach ($scenario in $scenarios) {
        $outRoot = "experiments/TR116/results/multi/python/$($m.slug)"
        Write-Host "Python multi-agent: $($m.name) scenario=$scenario -> $outRoot" -ForegroundColor Cyan
        python -m banterhearts.demo_multiagent.run_multiagent_demo `
            --model $m.name `
            --runs $Runs `
            --scenario $scenario `
            --collector-ollama-url http://localhost:11434 `
            --insight-ollama-url http://localhost:11435 `
            --chimera-num-gpu 80 `
            --chimera-num-ctx 2048 `
            --chimera-temperature 1.0 `
            --output-dir $outRoot
    }
}

Write-Host "Python multi-agent batch complete." -ForegroundColor Green
