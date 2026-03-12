"""TR132 Phase 2-3: Profiled N-agent serving tests.

Generic profiling loop parameterized by backend name ("vllm" or "tgi").
Both implement ServingBackend ABC, so the code is identical.

Two modes controlled by ``profiling_mode`` in config:
  - ``"in_container"`` — container-per-rep with nsys wrapping the server.
  - ``"system_wide"``  — single container + system-wide nsys captures.

For each model x N-level (N=1, N=8):
  - 3 reps x (profiled capture -> N agents x K requests -> stop capture)
  - Parse traces, verify batching at N=8

Persists per-request data to CSV (TR130 pattern) so --analyze-only works.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
from pathlib import Path
import time

from research.tr130.shared.agent_executor import run_n_agent_test
from research.tr130.shared.backends import create_backend
from research.tr130.shared.docker_utils import docker_logs
from research.tr131.shared.trace_parser import parse_all_reports
from research.tr132.shared.nsys_system_driver import NsysSystemDriver
from research.tr132.shared.utils import NSYS_REPORTS, generate_prompts

log = logging.getLogger("tr132.serving_profiled")

# ── CSV schema for per-request persistence ────────────────────────────
CSV_FIELDS = [
    "phase",
    "backend",
    "model",
    "n_agents",
    "rep",
    "agent_id",
    "request_sequence",
    "in_flight_at_submit",
    "wall_ms",
    "prompt_tokens",
    "completion_tokens",
    "effective_tps",
    "submit_time_s",
    "complete_time_s",
    "status",
]


def _check_batching(
    n_agents: int,
    max_concurrent_kernels: int,
    backend_name: str,
    model_name: str,
) -> dict:
    """Verify that the backend is actually batching requests at N>1."""
    result = {
        "n_agents": n_agents,
        "max_concurrent_kernels": max_concurrent_kernels,
    }

    if n_agents == 1:
        result["expected"] = "no batching (N=1 baseline)"
        result["batching_confirmed"] = True
        return result

    if max_concurrent_kernels > 1:
        result["batching_confirmed"] = True
        result["evidence"] = (
            f"max_concurrent_kernels={max_concurrent_kernels} > 1 — "
            f"GPU executing overlapping kernels (batching active)"
        )
    else:
        result["batching_confirmed"] = False
        result["evidence"] = (
            f"max_concurrent_kernels={max_concurrent_kernels} — "
            f"kernels may be serialized (batching possibly inactive). "
            f"Check {backend_name} container logs for batch size metrics."
        )
        log.warning(
            "  BATCHING CHECK: %s %s N=%d — max_concurrent=%d "
            "(expected >1 for active batching)",
            backend_name,
            model_name,
            n_agents,
            max_concurrent_kernels,
        )

    return result


def _check_container_batch_size(backend_name: str, docker_name: str) -> dict:
    """Parse container logs for batch size information."""
    result = {"source": "container_logs"}
    try:
        logs = docker_logs(docker_name, tail=200)
        batch_lines = []
        for line in logs.split("\n"):
            lower = line.lower()
            if any(kw in lower for kw in ["batch", "running", "num_seqs", "scheduled"]):
                batch_lines.append(line.strip())
        if batch_lines:
            result["batch_log_lines"] = batch_lines[-10:]
            result["found_batch_info"] = True
        else:
            result["found_batch_info"] = False
    except Exception as e:
        result["error"] = str(e)
        result["found_batch_info"] = False
    return result


def _extract_rep_metrics(
    agent_results: list,
    parsed: dict,
    elapsed_s: float,
    n_agents: int,
    rep_path: Path,
) -> dict:
    """Extract per-rep metrics from agent results and parsed trace.

    Shared by both system-wide and in-container modes.
    """
    ok_results = [r for r in agent_results if r.status == "ok"]
    tps_values = [r.effective_tps for r in ok_results if r.effective_tps > 0]
    total_tokens = sum(r.completion_tokens for r in ok_results)

    kern_sum = parsed.get("cuda_gpu_kern_sum", {})
    exec_trace = parsed.get("cuda_kern_exec_trace", {})
    mem_sum = parsed.get("cuda_gpu_mem_time_sum", {})
    max_concurrent = exec_trace.get("max_concurrent_kernels", 0)

    return {
        "elapsed_s": round(elapsed_s, 2),
        "rep_path": str(rep_path),
        "rep_size_mb": round(rep_path.stat().st_size / 1e6, 2),
        # Agent-level metrics
        "n_ok": len(ok_results),
        "n_total": len(agent_results),
        "total_tokens": total_tokens,
        "mean_tps": (sum(tps_values) / len(tps_values) if tps_values else 0),
        "per_agent_tps": (total_tokens / elapsed_s / n_agents if elapsed_s > 0 else 0),
        # Kernel metrics
        "kernel_count": kern_sum.get("total_instances", 0),
        "gpu_time_ms": kern_sum.get("total_gpu_time_ms", 0),
        "kernel_classification": kern_sum.get("kernel_classification", {}),
        # Exec trace metrics
        "n_launches": exec_trace.get("n_launches", 0),
        "gpu_active_ms": exec_trace.get("gpu_active_ms", 0),
        "gpu_utilization_pct": exec_trace.get("gpu_utilization_pct", 0),
        "max_concurrent_kernels": max_concurrent,
        # Memory metrics
        "mem_time_ms": mem_sum.get("total_time_ms", 0),
        "mem_ops": mem_sum.get("total_ops", 0),
        # Top kernels
        "top_kernels": [
            {
                "name": k["name"][:80],
                "time_ms": k["total_time_ms"],
                "instances": k["instances"],
            }
            for k in kern_sum.get("top_10", [])[:5]
        ],
    }


def _write_agent_results_to_csv(
    csv_writer,
    agent_results: list,
    phase_label: str,
    backend_name: str,
    model_name: str,
    n_agents: int,
    rep_idx: int,
) -> None:
    """Write per-request data from agent results to CSV."""
    for ar in agent_results:
        csv_writer.writerow(
            {
                "phase": phase_label,
                "backend": backend_name,
                "model": model_name,
                "n_agents": n_agents,
                "rep": rep_idx,
                "agent_id": ar.agent_id,
                "request_sequence": ar.request_sequence,
                "in_flight_at_submit": ar.in_flight_at_submit,
                "wall_ms": round(ar.wall_ms, 2),
                "prompt_tokens": ar.prompt_tokens,
                "completion_tokens": ar.completion_tokens,
                "effective_tps": round(ar.effective_tps, 2),
                "submit_time_s": ar.submit_time_s,
                "complete_time_s": ar.complete_time_s,
                "status": ar.status,
            }
        )


# ── Public entry point ───────────────────────────────────────────────


def run_serving_profiled(
    cfg: dict,
    run_dir: Path,
    backend_name: str,
    phase_label: str,
) -> dict:
    """Run profiled N-agent tests for one backend (vLLM or TGI).

    Dispatches to in-container or system-wide mode based on config.
    """
    mode = cfg.get("profiling_mode", "system_wide")
    log.info("Profiling mode for %s: %s", phase_label, mode)
    if mode == "in_container":
        return _run_in_container_mode(cfg, run_dir, backend_name, phase_label)
    return _run_system_wide_mode(cfg, run_dir, backend_name, phase_label)


# ── In-container mode ────────────────────────────────────────────────


def _run_in_container_mode(
    cfg: dict,
    run_dir: Path,
    backend_name: str,
    phase_label: str,
) -> dict:
    """Profiled N-agent tests using in-container nsys (container-per-rep).

    For each model x N-level x rep:
      1. start_profiled_container() — nsys wraps server
      2. create_backend() as HTTP-only client
      3. wait_ready(), warmup(), run_n_agent_test()
      4. fetch container logs (for N>1)
      5. stop_profiled_container() -> .nsys-rep
      6. stats_csv() + parse_all_reports()
      7. extract metrics
    """
    from research.tr132.shared.nsys_container_driver import NsysContainerDriver

    nsys_path = cfg.get("nsys_path", "nsys")
    nsys_linux_dir = cfg.get("nsys_linux_dir", "")
    nsys_cfg = cfg.get("nsys", {})
    backend_cfg = cfg["backends"][backend_name]
    max_tokens = cfg.get("max_new_tokens", 128)
    cooldown_s = cfg.get("cooldown_between_captures_s", 3)

    phase_key = "phase2" if backend_name == "vllm" else "phase3"
    phase_cfg = cfg[phase_key]

    n_levels = {
        "n1": phase_cfg["n1"],
        "n8": phase_cfg["n8"],
    }

    nsys_driver = NsysContainerDriver(nsys_path, nsys_linux_dir, nsys_cfg)
    traces_dir = run_dir / "traces"
    exports_dir = run_dir / "exports"
    traces_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    csv_path = run_dir / f"{phase_label}_requests.csv"
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    csv_writer.writeheader()

    results = {
        "phase": phase_label,
        "backend": backend_name,
        "profiling_mode": "in_container",
        "models": {},
    }

    try:
        for model in cfg["models"]:
            model_name = model["name"]
            log.info("=" * 50)
            log.info("%s: model=%s (in-container mode)", phase_label, model_name)
            log.info("=" * 50)

            model_results = {"n_levels": {}}

            for level_name, level_cfg in n_levels.items():
                n_agents = level_cfg["n_agents"]
                req_per_agent = level_cfg["requests_per_agent"]
                reps = level_cfg["repetitions"]

                log.info("-" * 40)
                log.info(
                    "%s %s N=%d: %d reps x %d agents x %d req",
                    phase_label,
                    model_name,
                    n_agents,
                    reps,
                    n_agents,
                    req_per_agent,
                )

                level_results = {
                    "n_agents": n_agents,
                    "requests_per_agent": req_per_agent,
                    "repetitions": reps,
                    "reps": [],
                }

                total_prompts = n_agents * req_per_agent
                prompts = generate_prompts(
                    max(total_prompts, 20),
                    low=cfg.get("prompt_tokens_low", 100),
                    high=cfg.get("prompt_tokens_high", 200),
                )

                for rep_idx in range(reps):
                    rep_label = (
                        f"{phase_label}_{model_name}_" f"{level_name}_rep{rep_idx}"
                    )
                    trace_name = rep_label

                    log.info("  Rep %d/%d: %s", rep_idx + 1, reps, rep_label)

                    rep_result = {
                        "rep": rep_idx,
                        "label": rep_label,
                        "status": "pending",
                    }

                    handle = None
                    try:
                        # Start profiled container for this rep
                        handle = nsys_driver.start_profiled_container(
                            backend_name=backend_name,
                            backend_cfg=backend_cfg,
                            model_cfg=model,
                            trace_name=trace_name,
                            traces_dir=traces_dir,
                        )

                        # HTTP-only client (no start())
                        backend = create_backend(backend_name, backend_cfg)
                        backend._current_model = model["hf_id"]

                        # Wait for server ready
                        startup_timeout = backend_cfg.get("startup_timeout_s", 300)
                        ready = backend.wait_ready(timeout_s=startup_timeout)
                        if not ready:
                            raise RuntimeError(
                                f"Server not ready after {startup_timeout}s"
                            )

                        # Warmup
                        backend.warmup(
                            n=cfg.get("warmup_requests", 3),
                            max_tokens=max_tokens,
                        )

                        # Run N-agent test
                        t0 = time.perf_counter()
                        agent_results = asyncio.run(
                            run_n_agent_test(
                                backend=backend,
                                n_agents=n_agents,
                                requests_per_agent=req_per_agent,
                                prompts=prompts,
                                max_tokens=max_tokens,
                            )
                        )
                        elapsed_s = time.perf_counter() - t0

                        # Write per-request CSV data
                        _write_agent_results_to_csv(
                            csv_writer,
                            agent_results,
                            phase_label,
                            backend_name,
                            model_name,
                            n_agents,
                            rep_idx,
                        )
                        csv_file.flush()

                        # Check container batch logs before stopping (N>1)
                        container_batch_check = None
                        if n_agents > 1:
                            container_batch_check = _check_container_batch_size(
                                backend_name, handle.container_name
                            )

                        # Stop container and get trace
                        rep_path = nsys_driver.stop_profiled_container(handle)
                        handle = None  # consumed

                        # Parse trace
                        nsys_driver.stats_csv(rep_path, NSYS_REPORTS, exports_dir)
                        parsed = parse_all_reports(exports_dir, rep_label)

                        # Extract metrics
                        metrics = _extract_rep_metrics(
                            agent_results, parsed, elapsed_s, n_agents, rep_path
                        )
                        rep_result.update(metrics)
                        rep_result["status"] = "ok"

                        max_concurrent = metrics["max_concurrent_kernels"]

                        # Batching verification
                        batching = _check_batching(
                            n_agents, max_concurrent, backend_name, model_name
                        )
                        rep_result["batching_check"] = batching

                        if container_batch_check is not None:
                            rep_result["container_batch_check"] = container_batch_check

                        log.info(
                            "    OK: %d/%d req, %.1f TPS/agent, "
                            "%d kernels, %.1f%% GPU, "
                            "concurrent=%d, batching=%s",
                            metrics["n_ok"],
                            metrics["n_total"],
                            metrics["per_agent_tps"],
                            metrics["kernel_count"],
                            metrics["gpu_utilization_pct"],
                            max_concurrent,
                            batching.get("batching_confirmed", "?"),
                        )

                    except Exception as e:
                        log.error("    Rep %d FAILED: %s", rep_idx, e)
                        rep_result["status"] = f"error: {e}"
                        if handle is not None:
                            nsys_driver.cancel_profiled_container(handle)
                            handle = None

                    level_results["reps"].append(rep_result)

                    # Cooldown between reps
                    if rep_idx < reps - 1:
                        time.sleep(cooldown_s)

                # After all reps for this level, store batch check summary
                if n_agents > 1:
                    batch_checks = [
                        r.get("container_batch_check", {})
                        for r in level_results["reps"]
                        if r.get("container_batch_check")
                    ]
                    if batch_checks:
                        level_results["container_batch_check"] = batch_checks[-1]
                        if batch_checks[-1].get("found_batch_info"):
                            log.info(
                                "  Container batch info: %s",
                                batch_checks[-1].get("batch_log_lines", [])[:3],
                            )

                model_results["n_levels"][level_name] = level_results

            results["models"][model_name] = model_results

    finally:
        csv_file.close()
        log.info("Per-request CSV saved: %s", csv_path)

    # Save phase results JSON
    results_path = run_dir / f"{phase_label}_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    log.info("Phase results saved: %s", results_path)

    return results


# ── System-wide mode (original) ──────────────────────────────────────


def _run_system_wide_mode(
    cfg: dict,
    run_dir: Path,
    backend_name: str,
    phase_label: str,
) -> dict:
    """Profiled N-agent tests using system-wide nsys capture (original).

    Single container per model; nsys system-wide captures per rep.
    """
    nsys_path = cfg.get("nsys_path", "nsys")
    nsys_cfg = cfg.get("nsys", {})
    backend_cfg = cfg["backends"][backend_name]
    max_tokens = cfg.get("max_new_tokens", 128)
    cooldown_s = cfg.get("cooldown_between_captures_s", 3)

    phase_key = "phase2" if backend_name == "vllm" else "phase3"
    phase_cfg = cfg[phase_key]

    n_levels = {
        "n1": phase_cfg["n1"],
        "n8": phase_cfg["n8"],
    }

    nsys = NsysSystemDriver(nsys_path, nsys_cfg)
    traces_dir = run_dir / "traces"
    exports_dir = run_dir / "exports"
    traces_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    csv_path = run_dir / f"{phase_label}_requests.csv"
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    csv_writer.writeheader()

    results = {
        "phase": phase_label,
        "backend": backend_name,
        "profiling_mode": "system_wide",
        "models": {},
    }

    try:
        for model in cfg["models"]:
            model_name = model["name"]
            log.info("=" * 50)
            log.info("%s: model=%s", phase_label, model_name)
            log.info("=" * 50)

            model_results = {"n_levels": {}}

            backend = create_backend(backend_name, backend_cfg)
            try:
                log.info("Starting %s for %s...", backend_name, model_name)
                backend.start(
                    model_hf_id=model["hf_id"],
                    model_ollama_tag=model.get("ollama_tag"),
                )

                warmup_result = backend.warmup(
                    n=cfg.get("warmup_requests", 3),
                    max_tokens=max_tokens,
                )
                model_results["warmup"] = warmup_result
                log.info(
                    "Warmup: %d/%d ok",
                    warmup_result["warmup_ok"],
                    warmup_result["warmup_requests"],
                )

                for level_name, level_cfg in n_levels.items():
                    n_agents = level_cfg["n_agents"]
                    req_per_agent = level_cfg["requests_per_agent"]
                    reps = level_cfg["repetitions"]

                    log.info("-" * 40)
                    log.info(
                        "%s %s N=%d: %d reps x %d agents x %d req",
                        phase_label,
                        model_name,
                        n_agents,
                        reps,
                        n_agents,
                        req_per_agent,
                    )

                    level_results = {
                        "n_agents": n_agents,
                        "requests_per_agent": req_per_agent,
                        "repetitions": reps,
                        "reps": [],
                    }

                    total_prompts = n_agents * req_per_agent
                    prompts = generate_prompts(
                        max(total_prompts, 20),
                        low=cfg.get("prompt_tokens_low", 100),
                        high=cfg.get("prompt_tokens_high", 200),
                    )

                    for rep_idx in range(reps):
                        rep_label = (
                            f"{phase_label}_{model_name}_" f"{level_name}_rep{rep_idx}"
                        )
                        session_name = f"tr132_{rep_label}"
                        trace_path = traces_dir / f"{rep_label}.nsys-rep"

                        log.info("  Rep %d/%d: %s", rep_idx + 1, reps, rep_label)

                        rep_result = {
                            "rep": rep_idx,
                            "label": rep_label,
                            "status": "pending",
                        }

                        handle = None
                        try:
                            handle = nsys.start_session(
                                trace_path, session_name=session_name
                            )

                            t0 = time.perf_counter()
                            agent_results = asyncio.run(
                                run_n_agent_test(
                                    backend=backend,
                                    n_agents=n_agents,
                                    requests_per_agent=req_per_agent,
                                    prompts=prompts,
                                    max_tokens=max_tokens,
                                )
                            )
                            elapsed_s = time.perf_counter() - t0

                            rep_path = nsys.stop_session(handle)
                            handle = None

                            _write_agent_results_to_csv(
                                csv_writer,
                                agent_results,
                                phase_label,
                                backend_name,
                                model_name,
                                n_agents,
                                rep_idx,
                            )
                            csv_file.flush()

                            nsys.stats_csv(rep_path, NSYS_REPORTS, exports_dir)
                            parsed = parse_all_reports(exports_dir, rep_label)

                            metrics = _extract_rep_metrics(
                                agent_results, parsed, elapsed_s, n_agents, rep_path
                            )
                            rep_result.update(metrics)
                            rep_result["status"] = "ok"

                            max_concurrent = metrics["max_concurrent_kernels"]

                            batching = _check_batching(
                                n_agents, max_concurrent, backend_name, model_name
                            )
                            rep_result["batching_check"] = batching

                            log.info(
                                "    OK: %d/%d req, %.1f TPS/agent, "
                                "%d kernels, %.1f%% GPU, "
                                "concurrent=%d, batching=%s",
                                metrics["n_ok"],
                                metrics["n_total"],
                                metrics["per_agent_tps"],
                                metrics["kernel_count"],
                                metrics["gpu_utilization_pct"],
                                max_concurrent,
                                batching.get("batching_confirmed", "?"),
                            )

                        except Exception as e:
                            log.error("    Rep %d FAILED: %s", rep_idx, e)
                            rep_result["status"] = f"error: {e}"
                            if handle is not None:
                                nsys.cancel_session(handle)

                        level_results["reps"].append(rep_result)

                        if rep_idx < reps - 1:
                            time.sleep(cooldown_s)

                    # After all reps for N=8, check container logs
                    if n_agents > 1:
                        docker_name = backend_cfg.get(
                            "docker_name", f"tr132-{backend_name}"
                        )
                        container_check = _check_container_batch_size(
                            backend_name, docker_name
                        )
                        level_results["container_batch_check"] = container_check
                        if container_check.get("found_batch_info"):
                            log.info(
                                "  Container batch info: %s",
                                container_check.get("batch_log_lines", [])[:3],
                            )

                    model_results["n_levels"][level_name] = level_results

            except Exception as e:
                log.error("Backend %s failed for %s: %s", backend_name, model_name, e)
                model_results["error"] = str(e)

            finally:
                log.info("Stopping %s container", backend_name)
                try:
                    backend.stop()
                except Exception as e:
                    log.warning("Backend stop error: %s", e)
                time.sleep(cooldown_s)

            results["models"][model_name] = model_results

    finally:
        csv_file.close()
        log.info("Per-request CSV saved: %s", csv_path)

    results_path = run_dir / f"{phase_label}_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    log.info("Phase results saved: %s", results_path)

    return results
