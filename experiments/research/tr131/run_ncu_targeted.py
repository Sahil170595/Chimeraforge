"""TR131 Phase 6: Nsight Compute targeted profiling of top GPU kernels.

Runs ncu on a small PyTorch script to capture detailed per-kernel metrics:
SM occupancy, memory bandwidth utilization, compute throughput.
"""

from __future__ import annotations

import contextlib
import json
import logging
from pathlib import Path
import subprocess
import time

from research.tr131.shared.utils import NCU_PATH

log = logging.getLogger("tr131.ncu_targeted")

_PYTHON = subprocess.check_output(
    ["python", "-c", "import sys; print(sys.executable)"],
    text=True,
).strip()


def _ncu_worker_script(
    hf_id: str,
    max_new_tokens: int,
    n_requests: int,
) -> str:
    """Generate a minimal inference script for ncu to profile."""
    return f"""
import sys
sys.path.insert(0, r"{Path(__file__).resolve().parents[2]}")

from research.tr131.shared.pytorch_inference import PyTorchInferenceEngine
from research.tr131.shared.utils import generate_prompts

engine = PyTorchInferenceEngine("{hf_id}", max_new_tokens={max_new_tokens})
engine.load()

# Warmup (not profiled — ncu uses --launch-skip)
prompts = generate_prompts(2, low=50, high=80)
for p in prompts:
    engine.generate_one(p)

# Profiled inference
prompts = generate_prompts({n_requests}, low=100, high=150)
for p in prompts:
    engine.generate_one(p)

engine.unload()
print("ncu worker done")
"""


def _parse_ncu_csv(csv_path: Path) -> dict:
    """Parse ncu CSV output into structured data."""
    import csv

    if not csv_path.exists():
        return {"error": "CSV not found"}

    with open(csv_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Skip header comments
    header_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith('"==')
            and not stripped.startswith("==")
        ):
            header_idx = i
            break

    data_lines = lines[header_idx:]
    if not data_lines:
        return {"kernels": [], "n_kernels": 0}

    reader = csv.DictReader(data_lines)
    kernels = []
    for row in reader:
        kernel = {
            "name": row.get("Kernel Name", row.get("Name", "unknown")),
        }
        # Extract key metrics (ncu CSV column names vary by version)
        for key in row:
            if "Occupancy" in key and "Achieved" in key:
                with contextlib.suppress(ValueError, TypeError):
                    kernel["sm_occupancy_pct"] = float(row[key])
            if "DRAM" in key and "Throughput" in key:
                with contextlib.suppress(ValueError, TypeError):
                    kernel["dram_throughput_pct"] = float(row[key])
            if "Compute" in key and "Throughput" in key:
                with contextlib.suppress(ValueError, TypeError):
                    kernel["compute_throughput_pct"] = float(row[key])
            if "Duration" in key:
                with contextlib.suppress(ValueError, TypeError):
                    kernel["duration_ns"] = float(row[key])
            if "Registers" in key:
                with contextlib.suppress(ValueError, TypeError):
                    kernel["registers_per_thread"] = int(float(row[key]))
            if "Block Size" in key or "Threads" in key:
                with contextlib.suppress(ValueError, TypeError):
                    kernel["block_size"] = int(float(row[key]))

        kernels.append(kernel)

    # Summarize
    occ_values = [k["sm_occupancy_pct"] for k in kernels if "sm_occupancy_pct" in k]
    bw_values = [
        k["dram_throughput_pct"] for k in kernels if "dram_throughput_pct" in k
    ]
    compute_values = [
        k["compute_throughput_pct"] for k in kernels if "compute_throughput_pct" in k
    ]

    return {
        "n_kernels": len(kernels),
        "kernels": kernels[:20],  # Top 20 detailed
        "summary": {
            "mean_sm_occupancy_pct": (
                round(sum(occ_values) / len(occ_values), 1) if occ_values else None
            ),
            "mean_dram_throughput_pct": (
                round(sum(bw_values) / len(bw_values), 1) if bw_values else None
            ),
            "mean_compute_throughput_pct": (
                round(sum(compute_values) / len(compute_values), 1)
                if compute_values
                else None
            ),
        },
    }


def run_ncu_targeted(cfg: dict, run_dir: Path) -> list[dict]:
    """Run Nsight Compute on top kernels for detailed metrics.

    Args:
        cfg: Full config dict
        run_dir: Run directory

    Returns:
        List of per-model ncu result dicts.
    """
    ncu_dir = run_dir / "ncu"
    scripts_dir = run_dir / "scripts"
    ncu_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    phase6_cfg = cfg.get("phase6", {})
    kernel_launch_count = phase6_cfg.get("kernel_launch_count", 5)
    max_tokens = cfg.get("max_new_tokens", 128)

    ncu_path = str(NCU_PATH)
    all_results = []

    for model in cfg["models"]:
        model_name = model["name"]
        hf_id = model["hf_id"]
        run_label = f"p6_ncu_{model_name}"

        log.info("--- %s ---", run_label)

        # Generate worker script
        script_content = _ncu_worker_script(
            hf_id=hf_id,
            max_new_tokens=max_tokens,
            n_requests=2,  # Small — ncu is very slow per kernel
        )
        script_path = scripts_dir / f"{run_label}.py"
        script_path.write_text(script_content, encoding="utf-8")

        # Output paths
        ncu_report = ncu_dir / f"{run_label}.ncu-rep"
        ncu_csv = ncu_dir / f"{run_label}.csv"

        # Run ncu
        cmd = [
            ncu_path,
            "--target-processes",
            "all",
            "--launch-skip",
            "50",  # Skip warmup kernels
            "--launch-count",
            str(kernel_launch_count),
            "--set",
            "full",
            "--csv",
            "--log-file",
            str(ncu_csv),
            "-o",
            str(ncu_report).replace(".ncu-rep", ""),
            "-f",
            _PYTHON,
            str(script_path),
        ]

        log.info("Running ncu (this is slow — ~2-5 min per kernel)...")
        log.debug("Command: %s", " ".join(cmd[:8]))

        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 min timeout
            )
            wall_s = time.perf_counter() - t0

            if result.returncode != 0:
                log.warning(
                    "ncu returned exit %d: %s", result.returncode, result.stderr[:500]
                )
        except subprocess.TimeoutExpired:
            log.warning("ncu timed out for %s", model_name)
            continue
        except Exception as e:
            log.error("ncu failed for %s: %s", model_name, e)
            continue

        # Parse results
        parsed = {}
        if ncu_csv.exists():
            parsed = _parse_ncu_csv(ncu_csv)
        elif ncu_report.exists():
            log.info("ncu-rep saved but CSV parsing not available")

        ncu_result = {
            "run_label": run_label,
            "model": model_name,
            "hf_id": hf_id,
            "wall_s": round(wall_s, 1),
            "kernel_launch_count": kernel_launch_count,
            "parsed": parsed,
        }

        if ncu_report.exists():
            ncu_result["report_file"] = str(ncu_report)
            ncu_result["report_size_mb"] = round(ncu_report.stat().st_size / 1e6, 1)

        log.info(
            "  ncu done in %.1fs — %d kernels profiled",
            wall_s,
            parsed.get("n_kernels", 0),
        )
        if parsed.get("summary"):
            s = parsed["summary"]
            log.info(
                "  SM occupancy=%.1f%%  DRAM throughput=%.1f%%  Compute=%.1f%%",
                s.get("mean_sm_occupancy_pct", 0) or 0,
                s.get("mean_dram_throughput_pct", 0) or 0,
                s.get("mean_compute_throughput_pct", 0) or 0,
            )

        all_results.append(ncu_result)

    # Save
    with open(run_dir / "p6_ncu_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)

    return all_results
