# Run TR116 end-to-end (Windows, sequential, dual Ollama assumed running on 11434/11435)
# Usage: pwsh experiments/TR116/scripts/run_tr116_all.ps1
# Notes:
# - Expects models already pulled: qwen2.5:7b, gemma3:latest, llama3.1:8b-instruct-q4_0
# - Expects dual Ollama servers running on ports 11434 and 11435
# - Python multi-agent not included (module currently empty); Rust multi-agent covers chimera-homo and baseline-vs-chimera

param(
    [int]$RunsSingle = 5,
    [int]$RunsMulti = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot/../../.."
Set-Location $repoRoot

$pythonExe = "python"
$pythonPath = "$($repoRoot)\src\python"

$models = @(
    @{ name = "qwen2.5:7b"; slug = "qwen2p5_7b" },
    @{ name = "gemma3:latest"; slug = "gemma3_latest" },
    @{ name = "llama3.1:8b-instruct-q4_0"; slug = "llama3p1_8b_q4_0" }
)

$singleGpu = @(60, 80)
$singleCtx = @(512, 1024)

function Run-PythonSingle {
    param($modelName, $slug)
    foreach ($g in $singleGpu) {
        foreach ($c in $singleCtx) {
            $outDir = "experiments/TR116/results/single/python/$slug/gpu${g}_ctx${c}_temp08"
            Write-Host "Python single-agent: $modelName g=$g c=$c -> $outDir" -ForegroundColor Cyan
            $env:PYTHONPATH = $pythonPath
            & $pythonExe src/python/banterhearts/demo_agent/run_demo.py `
                --model $modelName `
                --runs $RunsSingle `
                --chimera-num-gpu $g `
                --chimera-num-ctx $c `
                --chimera-temperature 0.8 `
                --output-dir $outDir
        }
    }
}

function Run-RustSingle {
    param($modelName, $slug)
    Push-Location src/rust/demo_agent
    foreach ($g in $singleGpu) {
        foreach ($c in $singleCtx) {
            $outDir = "../../experiments/TR116/results/single/rust/$slug/gpu${g}_ctx${c}_temp08"
            Write-Host "Rust single-agent: $modelName g=$g c=$c -> $outDir" -ForegroundColor Yellow
            ./target/release/demo_rust_agent.exe `
                --model $modelName `
                --runs $RunsSingle `
                --chimera-num-gpu $g `
                --chimera-num-ctx $c `
                --chimera-temperature 0.8 `
                --output-dir $outDir
        }
    }
    Pop-Location
}

function Run-RustMulti {
    param($modelName, $slug)
    Push-Location src/rust/demo_multiagent
    $scenarios = @("chimera-homo", "baseline-vs-chimera")
    foreach ($scenario in $scenarios) {
        $outDir = "../../experiments/TR116/results/multi/rust/$slug/${scenario}_gpu80_ctx512_temp10"
        Write-Host "Rust multi-agent: $modelName scenario=$scenario -> $outDir" -ForegroundColor Green
        ./target/release/Demo_rust_multiagent.exe `
            --model $modelName `
            --runs $RunsMulti `
            --scenario $scenario `
            --collector-ollama-url http://localhost:11434 `
            --insight-ollama-url http://localhost:11435 `
            --chimera-num-gpu 80 `
            --chimera-num-ctx 512 `
            --chimera-temperature 1.0 `
            --output-dir $outDir
    }
    Pop-Location
}

# Build rust binaries (idempotent)
Write-Host "Building Rust binaries..." -ForegroundColor Magenta
Push-Location src/rust/demo_agent; cargo build --release | Out-Null; Pop-Location
Push-Location src/rust/demo_multiagent; cargo build --release --features runtime-tokio-default | Out-Null; Pop-Location

# Run suites
foreach ($m in $models) {
    Run-PythonSingle -modelName $m.name -slug $m.slug
    Run-RustSingle -modelName $m.name -slug $m.slug
    Run-RustMulti  -modelName $m.name -slug $m.slug
}

Write-Host "TR116 batch complete." -ForegroundColor Green
