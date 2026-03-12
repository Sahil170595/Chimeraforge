param(
    [string]$Model = "gemma3:latest",
    [string]$BaseUrl = "http://localhost:11434",
    [int]$Runs = 3,
    [string]$OutRoot = "runs/tr109_rust"
)

$common = "--model $Model --base-url $BaseUrl --runs $Runs"

$configs = @(
    @{ name = "baseline_default"; args = "" },
    @{ name = "gpu60_ctx512_temp0p8"; args = "--chimera-num-gpu 60 --chimera-num-ctx 512 --chimera-temperature 0.8" },
    @{ name = "gpu120_ctx512_temp0p8"; args = "--chimera-num-gpu 120 --chimera-num-ctx 512 --chimera-temperature 0.8" },
    @{ name = "gpu80_ctx512_temp0p6"; args = "--chimera-num-gpu 80 --chimera-num-ctx 512 --chimera-temperature 0.6" },
    @{ name = "gpu80_ctx1024_temp0p8"; args = "--chimera-num-gpu 80 --chimera-num-ctx 1024 --chimera-temperature 0.8" },
    @{ name = "gpu60_ctx256_temp0p8"; args = "--chimera-num-gpu 60 --chimera-num-ctx 256 --chimera-temperature 0.8" },
    @{ name = "gpu60_ctx1024_temp0p6"; args = "--chimera-num-gpu 60 --chimera-num-ctx 1024 --chimera-temperature 0.6" },
    @{ name = "gpu80_ctx256_temp0p8"; args = "--chimera-num-gpu 80 --chimera-num-ctx 256 --chimera-temperature 0.8" },
    @{ name = "gpu120_ctx1024_temp0p8"; args = "--chimera-num-gpu 120 --chimera-num-ctx 1024 --chimera-temperature 0.8" },
    @{ name = "gpu80_ctx1024_temp0p6_v2"; args = "--chimera-num-gpu 80 --chimera-num-ctx 1024 --chimera-temperature 0.6" },
    @{ name = "gpu60_ctx1024_temp0p8"; args = "--chimera-num-gpu 60 --chimera-num-ctx 1024 --chimera-temperature 0.8" },
    @{ name = "gpu120_ctx256_temp0p8"; args = "--chimera-num-gpu 120 --chimera-num-ctx 256 --chimera-temperature 0.8" },
    @{ name = "gpu80_ctx256_temp0p6"; args = "--chimera-num-gpu 80 --chimera-num-ctx 256 --chimera-temperature 0.6" },
    @{ name = "gpu120_ctx1024_temp0p6"; args = "--chimera-num-gpu 120 --chimera-num-ctx 1024 --chimera-temperature 0.6" },
    @{ name = "gpu60_ctx256_temp0p6"; args = "--chimera-num-gpu 60 --chimera-num-ctx 256 --chimera-temperature 0.6" },
    @{ name = "gpu80_ctx512_temp0p8_v2"; args = "--chimera-num-gpu 80 --chimera-num-ctx 512 --chimera-temperature 0.8" },
    @{ name = "gpu120_ctx512_temp0p6"; args = "--chimera-num-gpu 120 --chimera-num-ctx 512 --chimera-temperature 0.6" },
    @{ name = "gpu60_ctx512_temp0p6"; args = "--chimera-num-gpu 60 --chimera-num-ctx 512 --chimera-temperature 0.6" },
    @{ name = "gpu120_ctx256_temp0p6"; args = "--chimera-num-gpu 120 --chimera-num-ctx 256 --chimera-temperature 0.6" }
)

foreach ($config in $configs) {
    $outDir = Join-Path $OutRoot $config.name
    Write-Host "`n=== Running $($config.name) ===" -ForegroundColor Cyan
    $cmd = "cargo run --release -- $common $($config.args) --output-dir $outDir"
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) {
        throw "Run failed: $($config.name)"
    }
}
