"""TR132 Phase 1: Validation Gate.

Validates that nsys can capture GPU kernels from a Docker-based serving backend.

Two modes controlled by ``profiling_mode`` in config:
  - ``"in_container"`` — mount Linux nsys into Docker, CUPTI traces from inside.
  - ``"system_wide"``  — host nsys captures system-wide (original approach).

Gate: must see >0 CUDA kernels from Docker before proceeding to Phase 2-3.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from research.tr130.shared.backends import create_backend
from research.tr130.shared.docker_utils import docker_available
from research.tr131.shared.trace_parser import parse_all_reports
from research.tr132.shared.nsys_system_driver import NsysSystemDriver
from research.tr132.shared.utils import NSYS_REPORTS, generate_prompts

log = logging.getLogger("tr132.validation")


def run_phase1(cfg: dict, run_dir: Path) -> dict:
    """Run Phase 1 validation gate — dispatches by profiling_mode."""
    mode = cfg.get("profiling_mode", "system_wide")
    log.info("Profiling mode: %s", mode)
    if mode == "in_container":
        return _run_phase1_in_container(cfg, run_dir)
    return _run_phase1_system_wide(cfg, run_dir)


# ── In-container mode ────────────────────────────────────────────────


def _run_phase1_in_container(cfg: dict, run_dir: Path) -> dict:
    """Validation gate using in-container nsys profiling.

    Steps:
    1. Validate Windows nsys reachable (for stats export)
    2. Validate Linux nsys directory exists
    3. Validate Docker available
    4. Start profiled vLLM container (nsys wraps server entrypoint)
    5. wait_ready → warmup → 3 test requests
    6. Stop container → find .nsys-rep
    7. nsys stats (Windows) → parse CSVs → check kernel_count > 0
    """
    from research.tr132.shared.nsys_container_driver import NsysContainerDriver

    result = {
        "phase": "validation",
        "profiling_mode": "in_container",
        "gate_passed": False,
        "checks": {},
        "errors": [],
    }

    nsys_path = cfg.get("nsys_path", "nsys")
    nsys_linux_dir = cfg.get("nsys_linux_dir", "")
    nsys_cfg = cfg.get("nsys", {})
    phase_cfg = cfg.get("phase1", {})
    n_requests = phase_cfg.get("requests", 3)
    backend_name = phase_cfg.get("backend", "vllm")
    backend_cfg = cfg["backends"][backend_name]

    model = cfg["models"][0]
    max_tokens = cfg.get("max_new_tokens", 128)

    # ── Check 1: Windows nsys reachable (for stats export) ──
    log.info("Check 1: Windows nsys reachable (for stats export)")
    nsys_driver = NsysContainerDriver(nsys_path, nsys_linux_dir, nsys_cfg)
    validation = nsys_driver.validate()
    result["checks"]["nsys_windows"] = validation
    if not validation.get("nsys_ok"):
        result["errors"].append(f"Windows nsys not reachable: {validation}")
        return result
    log.info("  Windows nsys OK: %s", validation.get("version", "unknown"))

    # ── Check 2: Linux nsys directory exists ──
    log.info("Check 2: Linux nsys directory exists")
    linux_dir = Path(nsys_linux_dir)
    linux_nsys_ok = linux_dir.is_dir()
    result["checks"]["nsys_linux_dir"] = {
        "path": str(linux_dir),
        "exists": linux_nsys_ok,
    }
    if not linux_nsys_ok:
        result["errors"].append(f"Linux nsys directory not found: {nsys_linux_dir}")
        return result
    log.info("  Linux nsys dir OK: %s", nsys_linux_dir)

    # ── Check 3: Docker available ──
    log.info("Check 3: Docker available")
    docker_ok = docker_available()
    result["checks"]["docker"] = docker_ok
    if not docker_ok:
        result["errors"].append("Docker not available")
        return result
    log.info("  Docker OK")

    # ── Check 4: Start profiled container ──
    log.info(
        "Check 4: Starting profiled %s container (model=%s)",
        backend_name,
        model["name"],
    )

    traces_dir = run_dir / "traces"
    exports_dir = run_dir / "exports"
    traces_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    trace_stem = "p1_validation"
    handle = None

    try:
        handle = nsys_driver.start_profiled_container(
            backend_name=backend_name,
            backend_cfg=backend_cfg,
            model_cfg=model,
            trace_name=trace_stem,
            traces_dir=traces_dir,
        )
    except Exception as e:
        result["errors"].append(f"Profiled container start failed: {e}")
        return result
    result["checks"]["container_started"] = True
    log.info("  Profiled container running: %s", handle.container_name)

    try:
        # ── Check 5: Wait for server ready, warmup, test requests ──
        log.info("Check 5: Waiting for server ready inside container")

        # Create backend as HTTP-only client (no start())
        backend = create_backend(backend_name, backend_cfg)
        backend._current_model = model["hf_id"]

        startup_timeout = backend_cfg.get("startup_timeout_s", 300)
        ready = backend.wait_ready(timeout_s=startup_timeout)
        if not ready:
            result["errors"].append(
                f"Server not ready after {startup_timeout}s inside container"
            )
            return result
        result["checks"]["server_ready"] = True
        log.info("  Server ready")

        # Warmup
        log.info("  Warmup requests")
        warmup_result = backend.warmup(
            n=cfg.get("warmup_requests", 3), max_tokens=max_tokens
        )
        result["checks"]["warmup"] = warmup_result
        log.info(
            "  Warmup: %d/%d ok",
            warmup_result["warmup_ok"],
            warmup_result["warmup_requests"],
        )

        # Test requests
        log.info("  Sending %d test requests", n_requests)
        prompts = generate_prompts(n_requests)
        request_results = []
        try:
            for i, prompt in enumerate(prompts):
                log.info("  Request %d/%d...", i + 1, n_requests)
                r = asyncio.run(backend.generate(prompt, max_tokens=max_tokens))
                request_results.append(
                    {
                        "seq": i,
                        "status": r.status,
                        "wall_ms": r.wall_ms,
                        "completion_tokens": r.completion_tokens,
                        "effective_tps": r.effective_tps,
                    }
                )
                log.info(
                    "    status=%s, wall=%.0fms, tokens=%d, tps=%.1f",
                    r.status,
                    r.wall_ms,
                    r.completion_tokens,
                    r.effective_tps,
                )
        except Exception as e:
            log.warning("Request sending error: %s", e)
            result["errors"].append(f"Request error: {e}")

        result["checks"]["requests"] = request_results

        # ── Check 6: Stop container → find trace ──
        log.info("Check 6: Stopping container and retrieving trace")
        try:
            rep_path = nsys_driver.stop_profiled_container(handle)
            handle = None  # consumed
        except Exception as e:
            result["errors"].append(f"Container stop / trace retrieval failed: {e}")
            return result

        result["checks"]["capture"] = {
            "rep_path": str(rep_path),
            "rep_size_mb": rep_path.stat().st_size / 1e6,
        }

        # ── Check 7: Parse trace and verify kernels ──
        log.info("Check 7: Parsing trace for CUDA kernels")
        try:
            stats = nsys_driver.stats_csv(rep_path, NSYS_REPORTS, exports_dir)
            result["checks"]["stats_reports"] = list(stats.keys())

            parsed = parse_all_reports(exports_dir, trace_stem)
            result["checks"]["parsed_reports"] = list(parsed.keys())

            kern_sum = parsed.get("cuda_gpu_kern_sum", {})
            kernel_count = kern_sum.get("total_instances", 0)
            gpu_time_ms = kern_sum.get("total_gpu_time_ms", 0)

            exec_trace = parsed.get("cuda_kern_exec_trace", {})
            n_launches = exec_trace.get("n_launches", 0)
            gpu_util = exec_trace.get("gpu_utilization_pct", 0)

            result["checks"]["kernels"] = {
                "kernel_count": kernel_count,
                "gpu_time_ms": gpu_time_ms,
                "n_launches": n_launches,
                "gpu_utilization_pct": gpu_util,
            }

            if kernel_count > 0:
                result["gate_passed"] = True
                log.info(
                    "  GATE PASSED: %d kernels, %.1f ms GPU time, "
                    "%.1f%% utilization",
                    kernel_count,
                    gpu_time_ms,
                    gpu_util,
                )

                top_kernels = kern_sum.get("top_10", [])[:5]
                for k in top_kernels:
                    log.info(
                        "    %s: %.2f ms (%d instances)",
                        k["name"][:60],
                        k["total_time_ms"],
                        k["instances"],
                    )
            else:
                result["errors"].append(
                    "No CUDA kernels captured — in-container nsys produced "
                    "empty trace (check CUPTI compatibility)"
                )
                log.error("  GATE FAILED: 0 kernels in trace")

            result["parsed_data"] = parsed

        except Exception as e:
            result["errors"].append(f"Trace parsing failed: {e}")
            log.error("Trace parsing error: %s", e)

    finally:
        if handle is not None:
            log.info("Cleaning up profiled container")
            try:
                nsys_driver.cancel_profiled_container(handle)
            except Exception as e:
                log.warning("Container cleanup error: %s", e)

    return result


# ── System-wide mode (original) ──────────────────────────────────────


def _run_phase1_system_wide(cfg: dict, run_dir: Path) -> dict:
    """Validation gate using system-wide nsys capture (original approach).

    Steps:
    1. Validate nsys reachable
    2. Validate Docker + GPU available
    3. Start vLLM container with llama3.2-1b
    4. Send warmup requests
    5. System-wide nsys capture: start -> 3 requests -> stop
    6. Parse trace -> check kernel_count > 0
    """
    result = {
        "phase": "validation",
        "profiling_mode": "system_wide",
        "gate_passed": False,
        "checks": {},
        "errors": [],
    }

    nsys_path = cfg.get("nsys_path", "nsys")
    nsys_cfg = cfg.get("nsys", {})
    phase_cfg = cfg.get("phase1", {})
    n_requests = phase_cfg.get("requests", 3)
    backend_name = phase_cfg.get("backend", "vllm")
    backend_cfg = cfg["backends"][backend_name]

    model = cfg["models"][0]
    max_tokens = cfg.get("max_new_tokens", 128)

    # ── Check 1: nsys reachable ──
    log.info("Check 1: nsys reachable")
    nsys = NsysSystemDriver(nsys_path, nsys_cfg)
    validation = nsys.validate()
    result["checks"]["nsys"] = validation
    if not validation.get("nsys_ok"):
        result["errors"].append(f"nsys not reachable: {validation}")
        return result
    log.info("  nsys OK: %s", validation.get("version", "unknown"))

    # ── Check 2: Docker available ──
    log.info("Check 2: Docker available")
    docker_ok = docker_available()
    result["checks"]["docker"] = docker_ok
    if not docker_ok:
        result["errors"].append("Docker not available")
        return result
    log.info("  Docker OK")

    # ── Check 3: Start backend container ──
    log.info("Check 3: Starting %s container (model=%s)", backend_name, model["name"])
    backend = create_backend(backend_name, backend_cfg)
    try:
        backend.start(
            model_hf_id=model["hf_id"], model_ollama_tag=model.get("ollama_tag")
        )
    except Exception as e:
        result["errors"].append(f"Backend start failed: {e}")
        return result
    result["checks"]["backend_started"] = True
    log.info("  %s container ready", backend_name)

    try:
        # ── Check 4: Warmup ──
        log.info("Check 4: Warmup requests")
        warmup_result = backend.warmup(
            n=cfg.get("warmup_requests", 3), max_tokens=max_tokens
        )
        result["checks"]["warmup"] = warmup_result
        log.info(
            "  Warmup: %d/%d ok",
            warmup_result["warmup_ok"],
            warmup_result["warmup_requests"],
        )

        # ── Check 5: System-wide nsys capture ──
        log.info("Check 5: System-wide nsys capture with %d requests", n_requests)

        traces_dir = run_dir / "traces"
        exports_dir = run_dir / "exports"
        traces_dir.mkdir(parents=True, exist_ok=True)
        exports_dir.mkdir(parents=True, exist_ok=True)

        trace_stem = "p1_validation"
        output_path = traces_dir / f"{trace_stem}.nsys-rep"
        session_name = "tr132_p1"

        prompts = generate_prompts(n_requests)

        handle = None
        try:
            handle = nsys.start_session(output_path, session_name=session_name)
        except Exception as e:
            result["errors"].append(f"nsys start_session failed: {e}")
            return result

        request_results = []
        try:
            for i, prompt in enumerate(prompts):
                log.info("  Request %d/%d...", i + 1, n_requests)
                r = asyncio.run(backend.generate(prompt, max_tokens=max_tokens))
                request_results.append(
                    {
                        "seq": i,
                        "status": r.status,
                        "wall_ms": r.wall_ms,
                        "completion_tokens": r.completion_tokens,
                        "effective_tps": r.effective_tps,
                    }
                )
                log.info(
                    "    status=%s, wall=%.0fms, tokens=%d, tps=%.1f",
                    r.status,
                    r.wall_ms,
                    r.completion_tokens,
                    r.effective_tps,
                )
        except Exception as e:
            log.warning("Request sending error: %s", e)
            result["errors"].append(f"Request error: {e}")

        try:
            rep_path = nsys.stop_session(handle)
        except Exception as e:
            result["errors"].append(f"nsys stop_session failed: {e}")
            if handle:
                nsys.cancel_session(handle)
            return result

        result["checks"]["capture"] = {
            "rep_path": str(rep_path),
            "rep_size_mb": rep_path.stat().st_size / 1e6,
            "requests": request_results,
        }

        # ── Check 6: Parse trace and verify kernels ──
        log.info("Check 6: Parsing trace for CUDA kernels")
        try:
            stats = nsys.stats_csv(rep_path, NSYS_REPORTS, exports_dir)
            result["checks"]["stats_reports"] = list(stats.keys())

            parsed = parse_all_reports(exports_dir, trace_stem)
            result["checks"]["parsed_reports"] = list(parsed.keys())

            kern_sum = parsed.get("cuda_gpu_kern_sum", {})
            kernel_count = kern_sum.get("total_instances", 0)
            gpu_time_ms = kern_sum.get("total_gpu_time_ms", 0)

            exec_trace = parsed.get("cuda_kern_exec_trace", {})
            n_launches = exec_trace.get("n_launches", 0)
            gpu_util = exec_trace.get("gpu_utilization_pct", 0)

            result["checks"]["kernels"] = {
                "kernel_count": kernel_count,
                "gpu_time_ms": gpu_time_ms,
                "n_launches": n_launches,
                "gpu_utilization_pct": gpu_util,
            }

            if kernel_count > 0:
                result["gate_passed"] = True
                log.info(
                    "  GATE PASSED: %d kernels, %.1f ms GPU time, "
                    "%.1f%% utilization",
                    kernel_count,
                    gpu_time_ms,
                    gpu_util,
                )

                top_kernels = kern_sum.get("top_10", [])[:5]
                for k in top_kernels:
                    log.info(
                        "    %s: %.2f ms (%d instances)",
                        k["name"][:60],
                        k["total_time_ms"],
                        k["instances"],
                    )
            else:
                result["errors"].append(
                    "No CUDA kernels captured — nsys system-wide cannot see "
                    "Docker GPU kernels (WDDM/WSL2 isolation)"
                )
                log.error("  GATE FAILED: 0 kernels in trace")

            result["parsed_data"] = parsed

        except Exception as e:
            result["errors"].append(f"Trace parsing failed: {e}")
            log.error("Trace parsing error: %s", e)

    finally:
        log.info("Stopping %s container", backend_name)
        try:
            backend.stop()
        except Exception as e:
            log.warning("Backend stop error: %s", e)

    return result
