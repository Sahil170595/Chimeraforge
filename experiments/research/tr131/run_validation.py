"""TR131 Phase 1: Validate that nsys captures CUDA traces from Ollama.

This is the critical gate — if nsys can't capture kernel data from
the Ollama process tree, we need a fallback strategy.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
import subprocess
from threading import Thread
import time

from research.tr131.shared.nsys_driver import NsysDriver
from research.tr131.shared.request_driver import wait_ollama_ready, warmup
from research.tr131.shared.trace_parser import parse_all_reports
from research.tr131.shared.utils import NSYS_PATH, generate_prompts

log = logging.getLogger("tr131.validation")


def _stop_ollama() -> None:
    """Stop any running Ollama process (including tray app)."""
    with contextlib.suppress(Exception):
        subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-Process | Where-Object { $_.ProcessName -like '*ollama*' } "
                "| Stop-Process -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            timeout=15,
        )
    time.sleep(3)


def _send_requests_after_ready(
    model_tag: str,
    n_requests: int,
    max_tokens: int,
    results_holder: list,
) -> None:
    """Wait for Ollama, warmup, then send requests. Runs in a thread."""
    from research.tr131.shared.request_driver import send_requests

    if not wait_ollama_ready(timeout_s=30):
        log.error("Ollama not ready within 30s")
        return

    log.info("Ollama ready, sending warmup...")
    warmup(model_tag, n=2, max_tokens=32)

    log.info("Sending %d validation requests...", n_requests)
    prompts = generate_prompts(n_requests)
    results = send_requests(
        n_agents=1,
        requests_per_agent=n_requests,
        model_tag=model_tag,
        prompts=prompts,
        max_tokens=max_tokens,
    )
    results_holder.extend(results)
    log.info("Validation requests complete: %d results", len(results))


def run_phase1(cfg: dict, run_dir: Path) -> dict:
    """Run Phase 1 validation.

    Returns validation report dict with feature availability.
    """
    traces_dir = run_dir / "traces"
    exports_dir = run_dir / "exports"
    traces_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    phase1_cfg = cfg.get("phase1", {})
    n_requests = phase1_cfg.get("requests", 3)
    duration_s = phase1_cfg.get("profile_duration_s", 30)
    max_tokens = cfg.get("max_new_tokens", 128)

    model = cfg["models"][0]  # Use first model for validation
    model_tag = model["ollama_tag"]

    validation = {
        "gate_passed": False,
        "nsys_captures_cuda": False,
        "nsys_captures_kernels": False,
        "gpuctxsw_works": False,
        "gpu_metrics_works": False,
        "ollama_requests_ok": False,
        "features": {},
        "errors": [],
    }

    # 1. Stop existing Ollama
    log.info("Stopping existing Ollama...")
    _stop_ollama()

    # 2. Initialize nsys driver
    nsys = NsysDriver(str(NSYS_PATH), cfg.get("nsys", {}))
    nsys_check = nsys.validate()
    if not nsys_check["nsys_ok"]:
        validation["errors"].append("nsys not reachable")
        return validation
    validation["nsys_version"] = nsys_check.get("version", "unknown")

    # 3. Profile Ollama with nsys
    trace_name = "validation_ollama"
    trace_path = traces_dir / trace_name

    # Start request sender in a background thread
    request_results: list = []
    sender = Thread(
        target=_send_requests_after_ready,
        args=(model_tag, n_requests, max_tokens, request_results),
        daemon=True,
    )

    log.info("Launching Ollama under nsys (duration=%ds)...", duration_s)
    try:
        sender.start()
        rep_path = nsys.profile(
            target_cmd=["ollama", "serve"],
            output_path=trace_path,
            duration_s=duration_s,
            extra_flags=["--kill", "true"],
        )
        sender.join(timeout=10)
        validation["trace_file"] = str(rep_path)
        validation["trace_size_mb"] = round(rep_path.stat().st_size / 1e6, 1)
    except Exception as e:
        validation["errors"].append(f"nsys profile failed: {e}")
        log.error("nsys profile failed: %s", e)
        _stop_ollama()
        return validation

    # 4. Check request results
    ok_count = sum(1 for r in request_results if r.status == "ok")
    validation["ollama_requests_ok"] = ok_count >= 1
    validation["requests_sent"] = len(request_results)
    validation["requests_ok"] = ok_count
    if request_results:
        tps_values = [r.effective_tps for r in request_results if r.status == "ok"]
        if tps_values:
            validation["mean_tps"] = round(sum(tps_values) / len(tps_values), 1)

    # 5. Extract stats
    log.info("Extracting nsys stats...")
    from research.tr131.shared.utils import NSYS_REPORTS

    try:
        csv_paths = nsys.stats_csv(rep_path, NSYS_REPORTS, exports_dir)
        validation["reports_extracted"] = list(csv_paths.keys())
    except Exception as e:
        validation["errors"].append(f"nsys stats failed: {e}")
        csv_paths = {}

    # 6. Parse and validate
    parsed = parse_all_reports(exports_dir, trace_name)

    # Check CUDA API
    api_data = parsed.get("cuda_api_sum", {})
    if api_data.get("total_calls", 0) > 0:
        validation["nsys_captures_cuda"] = True
        validation["cuda_api_calls"] = api_data["total_calls"]
        log.info("CUDA API calls captured: %d", api_data["total_calls"])
    else:
        validation["errors"].append("No CUDA API calls captured")
        log.warning("No CUDA API calls captured!")

    # Check kernels
    kern_data = parsed.get("cuda_gpu_kern_sum", {})
    if kern_data.get("total_instances", 0) > 0:
        validation["nsys_captures_kernels"] = True
        validation["kernel_count"] = kern_data["total_instances"]
        validation["gpu_time_ms"] = round(kern_data["total_gpu_time_ms"], 1)
        validation["top_3_kernels"] = [
            k["name"][:80] for k in kern_data.get("top_10", [])[:3]
        ]
        log.info(
            "GPU kernels captured: %d (%.1f ms GPU time)",
            kern_data["total_instances"],
            kern_data["total_gpu_time_ms"],
        )
    else:
        validation["errors"].append("No GPU kernels captured")
        log.warning("No GPU kernels captured!")

    # Check kernel exec trace (serialization data)
    exec_data = parsed.get("cuda_kern_exec_trace", {})
    if exec_data.get("n_launches", 0) > 0:
        validation["kernel_exec_trace_ok"] = True
        validation["gpu_utilization_pct"] = round(
            exec_data.get("gpu_utilization_pct", 0), 1
        )
        validation["max_concurrent_kernels"] = exec_data.get(
            "max_concurrent_kernels", 0
        )
        log.info(
            "Kernel exec trace: %d launches, %.1f%% GPU util, max %d concurrent",
            exec_data["n_launches"],
            exec_data.get("gpu_utilization_pct", 0),
            exec_data.get("max_concurrent_kernels", 0),
        )

    # Mark GPU features as working if we got kernel data
    validation["gpuctxsw_works"] = validation["nsys_captures_kernels"]
    validation["gpu_metrics_works"] = validation["nsys_captures_kernels"]

    # Store full parsed data
    validation["parsed_data"] = parsed

    # 7. Summary
    gate_passed = (
        validation["nsys_captures_cuda"]
        and validation["nsys_captures_kernels"]
        and validation["ollama_requests_ok"]
    )
    validation["gate_passed"] = gate_passed

    if gate_passed:
        log.info("Phase 1 PASSED: nsys captures CUDA kernels from Ollama")
    else:
        log.error("Phase 1 FAILED: %s", validation["errors"])

    # Cleanup
    _stop_ollama()

    return validation
