param(
    [string]$Model = "gemma3:latest",
    [string]$CollectorOllamaUrl = "http://localhost:11434",
    [string]$InsightOllamaUrl = "http://localhost:11435",
    [int]$DefaultRuns = 5,
    [string]$OutRoot = "runs/tr110_rust_full"
)

function Build-ChimeraArgs {
    param(
        [string]$Prefix,
        [hashtable]$Config
    )
    if (-not $Config) { return "" }
    $map = @{
        "num_gpu"        = "num-gpu"
        "num_ctx"        = "num-ctx"
        "temperature"    = "temperature"
        "top_p"          = "top-p"
        "top_k"          = "top-k"
        "repeat_penalty" = "repeat-penalty"
    }
    $args = @()
    foreach ($key in $map.Keys) {
        if ($Config.ContainsKey($key) -and $null -ne $Config[$key]) {
            $val = $Config[$key]
            $args += "--$Prefix-$($map[$key]) $val"
        }
    }
    return ($args -join " ")
}

$tests = @(
    # Phase 1 – baseline vs chimera (tests 001-006 + 202)
    @{ id = "test001"; scenario = "baseline-vs-chimera"; runs = 5; insight = @{ num_gpu = 60; num_ctx = 512; temperature = 0.8 } },
    @{ id = "test002"; scenario = "baseline-vs-chimera"; runs = 5; insight = @{ num_gpu = 60; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test003"; scenario = "baseline-vs-chimera"; runs = 5; insight = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 } },
    @{ id = "test004"; scenario = "baseline-vs-chimera"; runs = 5; insight = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test005"; scenario = "baseline-vs-chimera"; runs = 5; insight = @{ num_gpu = 120; num_ctx = 512; temperature = 0.8 } },
    @{ id = "test006"; scenario = "baseline-vs-chimera"; runs = 5; insight = @{ num_gpu = 120; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test202"; scenario = "baseline-vs-chimera"; runs = 5; insight = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 } },

    # Phase 1 – chimera hetero (tests 007-012 + 201)
    @{ id = "test007"; scenario = "chimera-hetero"; runs = 5; collector = @{ num_gpu = 60; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test008"; scenario = "chimera-hetero"; runs = 5; collector = @{ num_gpu = 60; num_ctx = 1024; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 2048; temperature = 0.8 } },
    @{ id = "test009"; scenario = "chimera-hetero"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 100; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test010"; scenario = "chimera-hetero"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.8 }; insight = @{ num_gpu = 100; num_ctx = 2048; temperature = 0.8 } },
    @{ id = "test011"; scenario = "chimera-hetero"; runs = 5; collector = @{ num_gpu = 120; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 140; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test012"; scenario = "chimera-hetero"; runs = 5; collector = @{ num_gpu = 120; num_ctx = 1024; temperature = 0.8 }; insight = @{ num_gpu = 140; num_ctx = 2048; temperature = 0.8 } },
    @{ id = "test201"; scenario = "chimera-hetero"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.8 } },

    # Phase 1 – chimera homo (tests 013-018)
    @{ id = "test013"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 60; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 60; num_ctx = 512; temperature = 0.8 } },
    @{ id = "test014"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 60; num_ctx = 1024; temperature = 0.8 }; insight = @{ num_gpu = 60; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test015"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 } },
    @{ id = "test016"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test017"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 120; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 120; num_ctx = 512; temperature = 0.8 } },
    @{ id = "test018"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 120; num_ctx = 1024; temperature = 0.8 }; insight = @{ num_gpu = 120; num_ctx = 1024; temperature = 0.8 } },

    # Phase 2 – temperature/context sweep (tests 100-108)
    @{ id = "test100"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 512; temperature = 0.6 }; insight = @{ num_gpu = 80; num_ctx = 512; temperature = 0.6 } },
    @{ id = "test101"; scenario = "chimera_homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 } },
    @{ id = "test102"; scenario = "chimera_homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 512; temperature = 1.0 }; insight = @{ num_gpu = 80; num_ctx = 512; temperature = 1.0 } },
    @{ id = "test103"; scenario = "chimera_homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.6 }; insight = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.6 } },
    @{ id = "test104"; scenario = "chimera_homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 1024; temperature = 0.8 } },
    @{ id = "test105"; scenario = "chimera_homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 1024; temperature = 1.0 }; insight = @{ num_gpu = 80; num_ctx = 1024; temperature = 1.0 } },
    @{ id = "test106"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 2048; temperature = 0.6 }; insight = @{ num_gpu = 80; num_ctx = 2048; temperature = 0.6 } },
    @{ id = "test107"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 2048; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 2048; temperature = 0.8 } },
    @{ id = "test108"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 2048; temperature = 1.0 }; insight = @{ num_gpu = 80; num_ctx = 2048; temperature = 1.0 } },

    # Phase 3 – validation set (tests 200-202 already included as needed)
    @{ id = "test200"; scenario = "chimera-homo"; runs = 5; collector = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 }; insight = @{ num_gpu = 80; num_ctx = 512; temperature = 0.8 } }
)

foreach ($test in $tests) {
    $runs = if ($test.ContainsKey("runs")) { $test.runs } else { $DefaultRuns }
    $scenarioName = $test.scenario -replace '_','-'
    $scenarioArg = "--scenario $scenarioName"
    $collectorArgs = ""
    $insightArgs = ""

    switch ($test.scenario) {
            "baseline-vs-chimera" {
            if ($test.insight) {
                $insightArgs = Build-ChimeraArgs -Prefix "chimera" -Config $test.insight
            }
        }
        default {
            if ($test.collector) {
                $collectorArgs = Build-ChimeraArgs -Prefix "chimera" -Config $test.collector
            }
            if ($test.insight) {
                $insightArgs = Build-ChimeraArgs -Prefix "chimera2" -Config $test.insight
            }
        }
    }

    $scenarioFolder = Join-Path $OutRoot $test.scenario
    $testFolder = Join-Path $scenarioFolder $test.id
    if (Test-Path $testFolder) {
        Write-Host "Skipping $($test.id) (already exists)" -ForegroundColor Yellow
        continue
    }
    New-Item -ItemType Directory -Force -Path $testFolder | Out-Null

    $cmd = @(
        "cargo run --release --",
        "--model $Model",
        "--runs $runs",
        "--collector-ollama-url $CollectorOllamaUrl",
        "--insight-ollama-url $InsightOllamaUrl",
        $scenarioArg,
        $collectorArgs,
        $insightArgs,
        "--output-dir `"$testFolder`""
    ) -join " "

    Write-Host "`n=== Running $($test.id) [$($test.scenario)] ===" -ForegroundColor Cyan
    Write-Host $cmd -ForegroundColor DarkGray
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) {
        throw "Sweep aborted on $($test.id)."
    }
}

Write-Host "`nAll TR110 sweep runs completed. Results stored under $OutRoot." -ForegroundColor Green
