# TR117 Tier 3 Launch Instructions

## IMPORTANT: Run in Standalone PowerShell

**DO NOT run in Cursor terminal** - 17 hour runtime will fail if Cursor closes.

## Quick Launch (Recommended)

1. Open **PowerShell** (not in Cursor)
2. Navigate to project:

   ```powershell
   cd C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts
   ```

3. Run launcher:

   ```powershell
   .\launch_tr117_tier3.ps1
   ```

4. Type `yes` when prompted
5. A new window opens with the benchmark - you can close the launcher window
6. Monitor progress in the benchmark window or via log file

## Alternative: Manual Launch

```powershell
# 1. Open PowerShell
cd C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts

# 2. Disable sleep (optional but recommended)
powercfg /change standby-timeout-ac 0

# 3. Set environment
$env:PYTHONPATH = "."
$env:BANTER_TRANSFORMER_MODEL = "models/tiny-gpt2"
$env:HF_HUB_OFFLINE = "1"

# 4. Run with logging
python scripts/tr117/run_matrix.py `
  --config scripts/tr117/configs/matrix_tier3_full.yaml `
  --output-root results/tr117_tier3/runs `
  2>&1 | Tee-Object -FilePath "tr117_tier3_run.log"

# 5. When done, restore sleep
powercfg /change standby-timeout-ac 15
```

## Monitoring Progress

### Check live log

```powershell
Get-Content tr117_tier3_run.log -Tail 20 -Wait
```

### Count completed runs

```powershell
(Get-ChildItem -Recurse results/tr117_tier3/runs -Filter "run_*.json").Count
```

Expected: **12,348 runs total**

### Check status breakdown

```powershell
python -c "import pandas as pd; df = pd.read_csv('results/tr117_tier3/metrics.csv'); print(df['status'].value_counts())"
```

## What to Expect

**Timeline:**

- Optimistic: 7 hours (if degraded runs dominate)
- Realistic: 17 hours
- Pessimistic: 34 hours (if all large models take time)

**Progress indicators:**

- First 1,000 runs: ~1-2 hours (fast CPU runs)
- Middle runs: Slower (Ollama large models)
- Last 1,000 runs: Mixed speed

**Checkpoints:**

- 25% (~3,000 runs): ~3-5 hours
- 50% (~6,000 runs): ~7-10 hours
- 75% (~9,000 runs): ~12-15 hours
- 100%: ~17 hours average

## After Completion

The script automatically runs analysis:

1. Aggregates to CSV
2. Computes statistical tests
3. Generates cost analysis
4. Creates plots
5. Captures environment

All results in: `results/tr117_tier3/`

## Troubleshooting

### If benchmark crashes

- Check log file: `tr117_tier3_run.log`
- Resume not supported - need to restart
- Results saved incrementally (won't lose completed runs)

### If system sleep/hibernate occurs

- Benchmark will be killed
- Restart from beginning
- Use `powercfg` commands to prevent this

### If running out of disk

- Benchmark will fail
- Need 10GB+ free space
- Check with: `(Get-PSDrive C).Free / 1GB`

## Success Criteria

When complete, you should have:

- ✓ 12,348 run JSONs in `results/tr117_tier3/runs/`
- ✓ `metrics.csv` with all aggregated data
- ✓ `statistical_analysis.json` with CIs and p-values
- ✓ `cost_analysis.json` with efficiency metrics
- ✓ `latency_by_backend.png` visualization
- ✓ `env.json` for reproducibility

## Next Steps After Completion

```powershell
# Verify data quality
python scripts/tr117/smoke_test.py

# View statistical results
Get-Content results/tr117_tier3/statistical_analysis.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# View cost analysis
Get-Content results/tr117_tier3/cost_analysis.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Now you can write the technical report!
```

## Notes

- The benchmark runs in its own window - safe to close launcher
- All output is logged to file
- Power settings are restored automatically
- Results are saved incrementally (crash-safe)
- Can monitor progress without interrupting the run

