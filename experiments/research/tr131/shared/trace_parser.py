"""Parse nsys stats CSV exports into analysis-ready data structures."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

log = logging.getLogger("tr131.trace_parser")


def _read_csv(path: Path) -> list[dict]:
    """Read CSV, skip comment lines (nsys prepends metadata)."""
    rows = []
    with open(path, encoding="utf-8") as f:
        # Skip lines until we find the header
        lines = f.readlines()

    # Find header line (first non-empty, non-comment line)
    header_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("="):
            header_idx = i
            break

    # Parse from header
    data_lines = lines[header_idx:]
    if not data_lines:
        return []

    reader = csv.DictReader(data_lines)
    for row in reader:
        rows.append(row)
    return rows


def _safe_float(val: str | None) -> float:
    """Convert string to float, return 0.0 on failure."""
    if val is None:
        return 0.0
    val = val.strip().replace(",", "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val: str | None) -> int:
    """Convert string to int, return 0 on failure."""
    if val is None:
        return 0
    val = val.strip().replace(",", "")
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def parse_cuda_api_sum(csv_path: Path) -> dict:
    """Parse cuda_api_sum: CUDA API call summary.

    Returns dict with total calls, top APIs by time, etc.
    """
    rows = _read_csv(csv_path)
    if not rows:
        return {"total_calls": 0, "apis": []}

    apis = []
    total_time_ns = 0
    total_calls = 0

    for row in rows:
        # nsys CSV columns vary; common: Time(%), Total Time (ns), Num Calls, Name
        name = row.get("Name", row.get("name", "unknown"))
        time_ns = _safe_float(row.get("Total Time (ns)", row.get("total_time", "0")))
        num_calls = _safe_int(row.get("Num Calls", row.get("num_calls", "0")))
        time_pct = _safe_float(row.get("Time(%)", row.get("time_pct", "0")))

        total_time_ns += time_ns
        total_calls += num_calls
        apis.append(
            {
                "name": name,
                "time_ns": time_ns,
                "time_ms": time_ns / 1e6,
                "num_calls": num_calls,
                "time_pct": time_pct,
            }
        )

    # Sort by time descending
    apis.sort(key=lambda x: x["time_ns"], reverse=True)

    return {
        "total_calls": total_calls,
        "total_time_ms": total_time_ns / 1e6,
        "top_10": apis[:10],
        "all": apis,
    }


def parse_kernel_summary(csv_path: Path) -> dict:
    """Parse cuda_gpu_kern_sum: GPU kernel execution summary.

    Returns kernel stats: top kernels, total GPU time, etc.
    """
    rows = _read_csv(csv_path)
    if not rows:
        return {"total_kernels": 0, "kernels": []}

    kernels = []
    total_time_ns = 0
    total_instances = 0

    for row in rows:
        name = row.get("Name", row.get("name", "unknown"))
        time_ns = _safe_float(row.get("Total Time (ns)", row.get("total_time", "0")))
        instances = _safe_int(row.get("Instances", row.get("instances", "0")))
        avg_ns = _safe_float(row.get("Avg (ns)", row.get("avg_time", "0")))
        min_ns = _safe_float(row.get("Min (ns)", row.get("min_time", "0")))
        max_ns = _safe_float(row.get("Max (ns)", row.get("max_time", "0")))

        total_time_ns += time_ns
        total_instances += instances
        kernels.append(
            {
                "name": name,
                "total_time_ns": time_ns,
                "total_time_ms": time_ns / 1e6,
                "instances": instances,
                "avg_ms": avg_ns / 1e6,
                "min_ms": min_ns / 1e6,
                "max_ms": max_ns / 1e6,
            }
        )

    kernels.sort(key=lambda x: x["total_time_ns"], reverse=True)

    # Classify kernels
    gemm_time = sum(
        k["total_time_ns"]
        for k in kernels
        if "gemm" in k["name"].lower()
        or "gemv" in k["name"].lower()
        or "cutlass" in k["name"].lower()
    )
    attn_time = sum(
        k["total_time_ns"]
        for k in kernels
        if "attention" in k["name"].lower()
        or "flash" in k["name"].lower()
        or "softmax" in k["name"].lower()
    )
    other_time = total_time_ns - gemm_time - attn_time

    return {
        "total_instances": total_instances,
        "total_gpu_time_ms": total_time_ns / 1e6,
        "top_10": kernels[:10],
        "kernel_classification": {
            "gemm_ms": gemm_time / 1e6,
            "gemm_pct": gemm_time / total_time_ns * 100 if total_time_ns > 0 else 0,
            "attention_ms": attn_time / 1e6,
            "attention_pct": (
                attn_time / total_time_ns * 100 if total_time_ns > 0 else 0
            ),
            "other_ms": other_time / 1e6,
            "other_pct": other_time / total_time_ns * 100 if total_time_ns > 0 else 0,
        },
        "all": kernels,
    }


def parse_kernel_exec_trace(csv_path: Path) -> dict:
    """Parse cuda_kern_exec_trace: kernel launch-to-execution timeline.

    This is the KEY report for measuring serialization/overlap.
    """
    rows = _read_csv(csv_path)
    if not rows:
        return {"n_launches": 0}

    launches = []
    for row in rows:
        start = _safe_float(row.get("Start (ns)", row.get("start", "0")))
        duration = _safe_float(row.get("Duration (ns)", row.get("duration", "0")))
        name = row.get("Name", row.get("name", "unknown"))
        launches.append(
            {
                "start_ns": start,
                "end_ns": start + duration,
                "duration_ns": duration,
                "name": name,
            }
        )

    if not launches:
        return {"n_launches": 0}

    launches.sort(key=lambda x: x["start_ns"])

    # Compute overlap and gaps
    total_span_ns = launches[-1]["end_ns"] - launches[0]["start_ns"]
    gpu_active_ns = 0
    max_concurrent = 1
    gaps = []

    # Merge overlapping intervals to compute active time
    merged = []
    for launch in launches:
        if merged and launch["start_ns"] <= merged[-1]["end_ns"]:
            merged[-1]["end_ns"] = max(merged[-1]["end_ns"], launch["end_ns"])
        else:
            if merged:
                gap = launch["start_ns"] - merged[-1]["end_ns"]
                if gap > 0:
                    gaps.append(gap)
            merged.append({"start_ns": launch["start_ns"], "end_ns": launch["end_ns"]})

    gpu_active_ns = sum(m["end_ns"] - m["start_ns"] for m in merged)
    gpu_idle_ns = total_span_ns - gpu_active_ns

    # Count max concurrent kernels (sweep line)
    events = []
    for l in launches:
        events.append((l["start_ns"], 1))
        events.append((l["end_ns"], -1))
    events.sort()
    concurrent = 0
    for _, delta in events:
        concurrent += delta
        max_concurrent = max(max_concurrent, concurrent)

    # Time spent at different concurrency levels
    events_sorted = sorted(events)
    concurrency_time = {}
    prev_time = events_sorted[0][0] if events_sorted else 0
    curr_level = 0
    for t, delta in events_sorted:
        if t > prev_time:
            dt = t - prev_time
            concurrency_time[curr_level] = concurrency_time.get(curr_level, 0) + dt
            prev_time = t
        curr_level += delta

    return {
        "n_launches": len(launches),
        "total_span_ms": total_span_ns / 1e6,
        "gpu_active_ms": gpu_active_ns / 1e6,
        "gpu_idle_ms": gpu_idle_ns / 1e6,
        "gpu_utilization_pct": (
            gpu_active_ns / total_span_ns * 100 if total_span_ns > 0 else 0
        ),
        "max_concurrent_kernels": max_concurrent,
        "n_gaps": len(gaps),
        "mean_gap_us": sum(gaps) / len(gaps) / 1e3 if gaps else 0,
        "max_gap_us": max(gaps) / 1e3 if gaps else 0,
        "concurrency_time_ms": {
            str(k): v / 1e6 for k, v in sorted(concurrency_time.items())
        },
    }


def parse_memory_summary(csv_path: Path) -> dict:
    """Parse cuda_gpu_mem_time_sum: GPU memory operation summary."""
    rows = _read_csv(csv_path)
    if not rows:
        return {"total_ops": 0}

    ops = []
    total_time_ns = 0

    for row in rows:
        name = row.get("Name", row.get("name", row.get("Operation", "unknown")))
        time_ns = _safe_float(row.get("Total Time (ns)", row.get("total_time", "0")))
        num_ops = _safe_int(
            row.get("Num Calls", row.get("Count", row.get("num_calls", "0")))
        )
        total_time_ns += time_ns
        ops.append(
            {
                "name": name,
                "time_ms": time_ns / 1e6,
                "num_ops": num_ops,
            }
        )

    return {
        "total_ops": sum(o["num_ops"] for o in ops),
        "total_time_ms": total_time_ns / 1e6,
        "operations": ops,
    }


def parse_osrt_summary(csv_path: Path) -> dict:
    """Parse osrt_sum: OS runtime summary (thread scheduling, waits)."""
    rows = _read_csv(csv_path)
    if not rows:
        return {"total_calls": 0}

    calls = []
    total_time_ns = 0

    for row in rows:
        name = row.get("Name", row.get("name", "unknown"))
        time_ns = _safe_float(row.get("Total Time (ns)", row.get("total_time", "0")))
        num_calls = _safe_int(row.get("Num Calls", row.get("num_calls", "0")))
        total_time_ns += time_ns
        calls.append(
            {
                "name": name,
                "time_ms": time_ns / 1e6,
                "num_calls": num_calls,
            }
        )

    calls.sort(key=lambda x: x["time_ms"], reverse=True)

    return {
        "total_calls": sum(c["num_calls"] for c in calls),
        "total_time_ms": total_time_ns / 1e6,
        "top_10": calls[:10],
    }


def parse_all_reports(exports_dir: Path, trace_stem: str) -> dict:
    """Parse all available nsys stats CSVs for a given trace."""
    result = {}
    parsers = {
        "cuda_api_sum": parse_cuda_api_sum,
        "cuda_gpu_kern_sum": parse_kernel_summary,
        "cuda_kern_exec_trace": parse_kernel_exec_trace,
        "cuda_gpu_mem_time_sum": parse_memory_summary,
        "osrt_sum": parse_osrt_summary,
    }

    for report_name, parser_fn in parsers.items():
        # Find matching CSV
        pattern = f"{trace_stem}*{report_name}*.csv"
        candidates = list(exports_dir.glob(pattern))
        if candidates:
            try:
                result[report_name] = parser_fn(candidates[0])
                log.debug("Parsed %s: %s", report_name, candidates[0].name)
            except Exception as e:
                log.warning("Failed to parse %s: %s", report_name, e)
                result[report_name] = {"error": str(e)}
        else:
            log.debug("No CSV for %s (pattern: %s)", report_name, pattern)

    return result
