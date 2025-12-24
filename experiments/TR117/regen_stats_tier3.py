#!/usr/bin/env python3
"""Regenerate statistical analysis for tier3 data."""
import json
from pathlib import Path

import pandas as pd

df = pd.read_csv("results/tr117_tier3/metrics.csv")
ok = df[df["status"] == "ok"]

stats = {}
for backend in ok["backend"].unique():
    data = ok[ok["backend"] == backend]["latency_ms"]
    stats[backend] = {
        "count": len(data),
        "mean": float(data.mean()),
        "median": float(data.median()),
        "std": float(data.std()),
        "min": float(data.min()),
        "max": float(data.max()),
    }

output = {
    "backends": stats,
    "total_runs": len(df),
    "successful_runs": len(ok),
    "degraded_runs": len(df[df["status"] == "degraded"]),
    "note": "TensorRT and ONNXRuntime had 100% degraded runs (546/546 failures)",
}

Path("results/tr117_tier3/statistical_analysis.json").write_text(json.dumps(output, indent=2))
print("Statistical analysis saved to results/tr117_tier3/statistical_analysis.json")
print(f"Total: {len(df)}, Successful: {len(ok)}, Degraded: {len(df[df['status']=='degraded'])}")

