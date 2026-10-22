"""Bounded categorical diagnostics for the isolated pinned Ollama CPU runtime."""

from __future__ import annotations

import json
import math
import re
import shlex
import sys
from pathlib import Path
from typing import TextIO

# Keep failure diagnostics smaller than the provider log and independent of its labels.
MAX_LINE_BYTES = 8192
MAX_LOG_BYTES = 4 * 1024**2
MAX_RECORDS = 16
MAX_BUFFER_ENTRIES = 256
MAX_MEMORY_BYTES = 2**63 - 1
MAX_LAYERS = 65536
MAX_LAYER_DIGITS = len(str(MAX_LAYERS))
MAX_GPU_INDEX = 31
TAIL_CHARACTERS = 8000
MAX_TAIL_BYTES = TAIL_CHARACTERS * 4
MIB = 1024**2

CPU_EXCLUSIONS = {
    "CUDA_VISIBLE_DEVICES": "-1",
    "ROCR_VISIBLE_DEVICES": "-1",
    "GGML_VK_VISIBLE_DEVICES": "-1",
    "OLLAMA_VULKAN": "0",
    # Pinned llama.cpp b11232 disables AMX extra buffers when repacking is off.
    "LLAMA_ARG_REPACK": "0",
}
COMPONENTS = {"load_tensors", "llama_kv_cache", "llama_context", "sched_reserve"}
GPU_BACKENDS = {"CUDA": "cuda", "ROCm": "rocm", "Vulkan": "vulkan", "MTL": "metal"}
_LAUNCH = re.compile(
    r"^time=[0-9TZ:.+\-]+ level=INFO source=llama_server\.go:[0-9]+ "
    r'msg="starting llama-server" cmd=(.+)$'
)
_OFFLOAD = re.compile(r"^load_tensors:\s+offloaded ([0-9]+)/([0-9]+) layers to GPU$")
_BUFFER = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*):\s+(\S+)\s+(model|KV|compute|output|RS)"
    r"\s+buffer size\s*=\s*(\S+)\s+MiB\s*$"
)
_GPU = re.compile(r"^(CUDA|ROCm|Vulkan|MTL)([0-9]{1,2})(?:_(Mapped|REPACK|Private))?$")
_MEMORY_NUMBER = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_INTEGER = re.compile(r"^-?[0-9]+$")
_LOADED = re.compile(r"^srv\s+llama_server:\s+model loaded$")


def cpu_server_environment(parent: dict) -> dict:
    """Constrain owned daemon discovery and CPU buffers without mutating its caller."""
    return dict(parent) | CPU_EXCLUSIONS


def _ngl(line: str) -> tuple[int | None, str]:
    match = _LAUNCH.fullmatch(line)
    if match is None:
        return None, "invalid"
    command = match[1]
    try:
        if command.startswith('"'):
            command = json.loads(command)
        if any(ord(char) < 32 for char in command):
            return None, "invalid"
        arguments = shlex.split(command)
    except (ValueError, TypeError):
        return None, "invalid"
    positions = [i for i, arg in enumerate(arguments) if arg == "-ngl"]
    if not positions:
        return None, "missing"
    if len(positions) != 1 or positions[0] + 1 == len(arguments):
        return None, "invalid"
    value = arguments[positions[0] + 1]
    if len(value) > 8 or _INTEGER.fullmatch(value) is None:
        return None, "invalid"
    number = int(value)
    return (number, "known") if -1 <= number <= MAX_LAYERS else (None, "invalid")


def _record(index: int, line: str) -> dict:
    ngl, state = _ngl(line)
    return {
        "index": index,
        "ngl": ngl,
        "ngl_state": state,
        "offloaded_layers": None,
        "total_layers": None,
        "offload_state": "missing",
        "model_loaded": False,
        "buffer_bytes": {"cpu": 0, "amx": 0, "gpu": 0},
        "buffers": [],
        "unknown_startup_lines": 0,
        "invalid_startup_lines": 0,
        "buffer_limit_exceeded": False,
        "startup_facts_complete": False,
    }


def _backend(name: str) -> tuple[str, int | None, str, str] | None:
    if name in {"CPU", "CPU_Mapped", "CPU_REPACK", "BLAS", "AMX"}:
        backend = {"BLAS": "blas", "AMX": "amx"}.get(name, "cpu")
        storage = {"CPU_Mapped": "mapped", "CPU_REPACK": "repack"}.get(name, "default")
        return backend, None, storage, "amx" if name == "AMX" else "cpu"
    if name in {"CUDA_Host", "ROCm_Host", "Vulkan_Host"}:
        return GPU_BACKENDS[name.split("_")[0]], None, "host", "cpu"
    match = _GPU.fullmatch(name)
    if match is None or int(match[2]) > MAX_GPU_INDEX:
        return None
    return GPU_BACKENDS[match[1]], int(match[2]), (match[3] or "default").lower(), "gpu"


def _buffer(record: dict, table: dict, match: re.Match) -> None:
    component, name, kind, amount = match.groups()
    backend = _backend(name)
    if component not in COMPONENTS or backend is None:
        record["unknown_startup_lines"] += 1
        return
    if len(amount) > 32 or _MEMORY_NUMBER.fullmatch(amount) is None:
        record["invalid_startup_lines"] += 1
        return
    value = float(amount) * MIB
    if not math.isfinite(value) or not 0 <= int(value) <= MAX_MEMORY_BYTES:
        record["invalid_startup_lines"] += 1
        return
    family, device, storage, category = backend
    key = component, family, device, storage, kind
    if key not in table and len(table) >= MAX_BUFFER_ENTRIES:
        record["buffer_limit_exceeded"] = True
        return
    row = {
        "component": component,
        "backend": family,
        "device": device,
        "storage": storage,
        "kind": kind,
        "bytes": int(value),
    }
    # Upstream replaces repeated component/backend/kind lines during fit/probe/load.
    total = sum(item[0]["bytes"] for key_, item in table.items() if key_ != key) + int(value)
    if total > MAX_MEMORY_BYTES:
        record["invalid_startup_lines"] += 1
        return
    table[key] = row, category


def runtime_observation(data: bytes, *, truncated: bool = False) -> dict:
    """Project startup log facts, never a hardware or CPU-placement qualification."""
    truncated = truncated or len(data) > MAX_LOG_BYTES
    data = data[:MAX_LOG_BYTES]
    try:
        data.decode("utf-8")
        decode_errors = False
    except UnicodeDecodeError:
        decode_errors = True
    report: dict = {
        "schema_version": 1,
        "stage": "cpu_runtime_startup",
        "record_basis": "ordered_launch_log_segments",
        "log_state": "read",
        "log_bytes_read": len(data),
        "log_truncated": truncated,
        "decode_errors": decode_errors,
        "partial_line": bool(data and not data.endswith(b"\n")),
        "overlong_lines": 0,
        "record_limit_exceeded": False,
        "unbound_startup_lines": 0,
        "startup_facts_complete": False,
        "records": [],
    }
    current = None
    tables: list[dict] = []
    for raw_line in data.split(b"\n"):
        if len(raw_line) > MAX_LINE_BYTES:
            report["overlong_lines"] += 1
            current = None
            continue
        try:
            line = raw_line.decode("utf-8").rstrip("\r")
        except UnicodeDecodeError:
            current = None
            continue
        if 'msg="starting llama-server"' in line:
            if len(report["records"]) >= MAX_RECORDS:
                report["record_limit_exceeded"] = True
                current = None
                continue
            current = _record(len(report["records"]) + 1, line)
            report["records"].append(current)
            tables.append({})
            continue
        relevant = "buffer size" in line or "layers to GPU" in line or _LOADED.fullmatch(line)
        if not relevant:
            continue
        if current is None:
            report["unbound_startup_lines"] += 1
            continue
        if _LOADED.fullmatch(line):
            current["model_loaded"] = True
        elif match := _OFFLOAD.fullmatch(line):
            if max(len(match[1]), len(match[2])) > MAX_LAYER_DIGITS:
                current["offload_state"] = "invalid"
                current["invalid_startup_lines"] += 1
                continue
            loaded, total = int(match[1]), int(match[2])
            previous = current["offloaded_layers"], current["total_layers"]
            if not 0 <= loaded <= total <= MAX_LAYERS or total == 0:
                current["offload_state"] = "invalid"
                current["invalid_startup_lines"] += 1
            elif previous != (None, None) and previous != (loaded, total):
                current["offload_state"] = "conflicting"
                current["invalid_startup_lines"] += 1
            elif current["offload_state"] not in {"invalid", "conflicting"}:
                current.update(offloaded_layers=loaded, total_layers=total, offload_state="known")
        elif match := _BUFFER.fullmatch(line):
            _buffer(current, tables[-1], match)
        else:
            current["unknown_startup_lines"] += 1
    for record, table in zip(report["records"], tables):
        record["buffers"] = [row for row, _category in table.values()]
        for row, category in table.values():
            record["buffer_bytes"][category] += row["bytes"]
        record["startup_facts_complete"] = bool(
            record["ngl_state"] == record["offload_state"] == "known"
            and record["model_loaded"]
            and record["buffers"]
            and not record["unknown_startup_lines"]
            and not record["invalid_startup_lines"]
            and not record["buffer_limit_exceeded"]
        )
    report["startup_facts_complete"] = bool(
        report["records"]
        and all(row["startup_facts_complete"] for row in report["records"])
        and not any(
            report[name]
            for name in (
                "log_truncated",
                "decode_errors",
                "partial_line",
                "overlong_lines",
                "record_limit_exceeded",
                "unbound_startup_lines",
            )
        )
    )
    return report


def read_runtime_observation(path: Path) -> dict:
    """Read a bounded prefix and expose an unavailable/truncated log explicitly."""
    try:
        with path.open("rb") as source:
            data = source.read(MAX_LOG_BYTES + 1)
    except OSError:
        report = runtime_observation(b"")
        report["log_state"] = "unavailable"
        return report
    return runtime_observation(data)


def print_runtime_failure(path: Path, *, stream: TextIO | None = None) -> None:
    """Print categorical facts before the existing, separately bounded raw log tail."""
    stream = sys.stderr if stream is None else stream
    print(
        json.dumps({"cpu_runtime_observation": read_runtime_observation(path)}, sort_keys=True),
        file=stream,
        flush=True,
    )
    try:
        with path.open("rb") as source:
            source.seek(0, 2)
            source.seek(max(0, source.tell() - MAX_TAIL_BYTES))
            tail = source.read(MAX_TAIL_BYTES).decode("utf-8", errors="replace")[-TAIL_CHARACTERS:]
    except OSError:
        tail = "[server log tail unavailable]"
    print(tail, file=stream, flush=True)
