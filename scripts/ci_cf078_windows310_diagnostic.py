"""Bounded unchanged-test Windows diagnostics; no clocks or runtime behavior replaced."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import ssl
import subprocess
import sys
import time
from typing import Any

import httpx
import pytest

FEATURE_BASE = "bdf44e6c73e74c1ca0d5910323c4a56799942cc1"
MAX_METRICS_ATTEMPTS = 100
MAX_TLS_ATTEMPTS = 12
MAX_READY_ATTEMPTS = 10
MAX_READY_TURNS = 10000
METRICS_NODE = (
    "tests/test_fleet_monitor_transport.py::"
    "test_unexpected_metrics_stream_failure_retains_context_and_owned_cleanup[breach-2-3]"
)
TLS_NODE = (
    "tests/test_secure_monitor.py::"
    "test_secure_owned_pools_clients_streams_and_tasks_close[deadline]"
)
SOURCE_FILES = (
    "uv.lock",
    "pyproject.toml",
    "src/chimeraforge/fleet_monitor.py",
    "src/chimeraforge/fleet_monitor_transport.py",
    "src/chimeraforge/monitor.py",
    "src/chimeraforge/monitor_connection.py",
    "src/chimeraforge/bench/serving.py",
    "tests/test_fleet_monitor_transport.py",
    "tests/test_secure_monitor.py",
)


def source_hashes(root: Path) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


class NativeObserver:
    """Read native values at existing call/return boundaries, without altering them."""

    def __init__(self, ready_work: bool = False) -> None:
        self.windows: list[dict[str, Any]] = []
        self.cleanup: list[dict[str, Any]] = []
        self.reports: list[dict[str, Any]] = []
        self.pools: list[Any] = []
        self.clients: list[httpx.AsyncClient] = []
        self.metadata_started = 0
        self.metadata_completed = 0
        self.ready_work = ready_work
        self.ready_turns = 0

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(
        self, item: pytest.Item, nextitem: pytest.Item | None
    ) -> Iterator[None]:
        from chimeraforge import api, fleet_monitor
        from chimeraforge.bench import serving
        from chimeraforge.monitor import MonitorError

        native_window = fleet_monitor.evaluate_window
        native_cleanup = fleet_monitor._cleanup
        native_monitor = api.monitor_fleet
        native_observe = serving.observe_backend
        native_pool = fleet_monitor.OwnedPool
        native_client_init = httpx.AsyncClient.__init__

        def window(*args: Any, **kwargs: Any) -> Any:
            row: dict[str, Any] = {"seconds": kwargs["seconds"]}
            self.windows.append(row)
            try:
                result = native_window(*args, **kwargs)
            except MonitorError as exc:
                row.update(error="MonitorError", message=str(exc))
                raise
            row["outcome"] = result.outcome
            return result

        async def cleanup(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            row: dict[str, Any] = {
                "metadata_started_at_entry": self.metadata_started,
                "metadata_completed_at_entry": self.metadata_completed,
                "worker_states_at_entry": [
                    {"done": task.done(), "cancelled": task.cancelled()} for task in args[0]
                ],
                "slot_observations_at_entry": [len(value.slot.observations) for value in args[1]],
            }
            self.cleanup.append(row)
            try:
                result = await native_cleanup(*args, **kwargs)
            except BaseException as exc:
                row["exception_class"] = type(exc).__name__
                raise
            row.update(flags=result, elapsed_seconds=time.perf_counter() - start)
            return result

        async def observe(*args: Any, **kwargs: Any) -> Any:
            self.metadata_started += 1
            result = await native_observe(*args, **kwargs)
            self.metadata_completed += 1
            return result

        async def monitor(*args: Any, **kwargs: Any) -> Any:
            stop = asyncio.Event()

            async def ready() -> None:
                for _ in range(MAX_READY_TURNS):
                    if stop.is_set():
                        break
                    self.ready_turns += 1
                    await asyncio.sleep(0)

            worker = asyncio.create_task(ready()) if self.ready_work else None
            try:
                result = await native_monitor(*args, **kwargs)
            finally:
                stop.set()
                if worker is not None:
                    if not worker.done():
                        worker.cancel()
                    await asyncio.gather(worker, return_exceptions=True)
            self.reports.append(
                {
                    "cleanup": result.cleanup,
                    "budget": result.budget,
                    "exit_code": result.exit_code,
                    "metadata_started": self.metadata_started,
                    "metadata_completed": self.metadata_completed,
                    "slots": [
                        {
                            "state": value.state,
                            "error": value.error,
                            "windows": len(value.windows),
                            "observations": len(value.observations),
                        }
                        for value in result.slots
                    ],
                }
            )
            return result

        def pool(*args: Any, **kwargs: Any) -> Any:
            result = native_pool(*args, **kwargs)
            self.pools.append(result)
            return result

        def client_init(instance: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
            native_client_init(instance, *args, **kwargs)
            self.clients.append(instance)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(fleet_monitor, "evaluate_window", window)
            patch.setattr(fleet_monitor, "_cleanup", cleanup)
            patch.setattr(serving, "observe_backend", observe)
            patch.setattr(api, "monitor_fleet", monitor)
            patch.setattr(fleet_monitor, "OwnedPool", pool)
            patch.setattr(httpx.AsyncClient, "__init__", client_init)
            yield

    def record(self) -> dict[str, Any]:
        return {
            "windows": self.windows,
            "cleanup_phases": self.cleanup,
            "reports": self.reports,
            "owned_pool_flags": [
                {"closed": value.closed, "remaining_streams": len(value.streams)}
                for value in self.pools
            ],
            "client_closed_flags": [value.is_closed for value in self.clients],
            "controlled_ready_turns": self.ready_turns,
        }


def native_identities() -> dict[str, Any]:
    from chimeraforge import api, fleet_monitor
    from chimeraforge.bench import serving

    return {
        "api_monitor": api.monitor_fleet,
        "window": fleet_monitor.evaluate_window,
        "cleanup": fleet_monitor._cleanup,
        "metadata": serving.observe_backend,
        "pool": fleet_monitor.OwnedPool,
        "client_class": httpx.AsyncClient,
        "client_init": httpx.AsyncClient.__init__,
    }


def run_case(node: str, attempt: int, phase: str) -> dict[str, Any]:
    observer = NativeObserver(ready_work=phase == "controlled-ready")
    native = native_identities()
    stdout, stderr = io.StringIO(), io.StringIO()
    started = time.perf_counter()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = int(
            pytest.main([node, "-q", "--tb=short", "-p", "no:cacheprovider"], plugins=[observer])
        )
    restored = native_identities()
    assert all(restored[name] is value for name, value in native.items()), (
        "observer restoration failed after fixture teardown"
    )
    captured = stdout.getvalue() + stderr.getvalue()
    return {
        "node": node,
        "attempt": attempt,
        "phase": phase,
        "pytest_exit": code,
        "elapsed_seconds": time.perf_counter() - started,
        "pytest_summaries": re.findall(r"\d+ (?:passed|failed)[^\r\n]*", captured)[-1:],
        "captured_output_sha256": hashlib.sha256(captured.encode()).hexdigest(),
        "native_identities_restored": True,
        **observer.record(),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    frozen = source_hashes(root)
    allowed = [
        ".github/workflows/cf078-windows310-diagnostic.yml",
        "scripts/ci_cf078_windows310_diagnostic.py",
    ]
    parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], text=True).strip()
    delta = subprocess.check_output(
        ["git", "diff", "--name-only", FEATURE_BASE, "HEAD"], text=True
    ).splitlines()
    assert parent == FEATURE_BASE and sorted(delta) == allowed
    metadata = {
        "python": sys.version,
        "os": platform.platform(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "expected_feature_base": FEATURE_BASE,
        "git_delta": delta,
        "parent_verified": True,
        "openssl": ssl.OPENSSL_VERSION,
        "sdk_versions": {
            name: importlib.metadata.version(name)
            for name in ("httpx", "httpcore", "anyio", "pytest", "pytest-asyncio")
        },
        "monotonic": vars(time.get_clock_info("monotonic")),
        "perf_counter": vars(time.get_clock_info("perf_counter")),
        "source_sha256": frozen,
        "stdlib_sha256": {
            name: hashlib.sha256(Path(asyncio.__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("tasks.py", "base_events.py", "windows_events.py")
        },
        "scope": "unchanged native tests; thin boundary observers; no clock/budget/body changes",
    }
    print(json.dumps({"event": "sdk", **metadata}), flush=True)
    results = []
    phases = (
        (METRICS_NODE, MAX_METRICS_ATTEMPTS, "baseline"),
        (METRICS_NODE, MAX_READY_ATTEMPTS, "controlled-ready"),
        (TLS_NODE, MAX_TLS_ATTEMPTS, "tls-baseline"),
    )
    for node, maximum, phase in phases:
        if phase == "controlled-ready" and any(value["pytest_exit"] for value in results):
            continue
        for attempt in range(1, maximum + 1):
            assert source_hashes(root) == frozen
            result = run_case(node, attempt, phase)
            assert source_hashes(root) == frozen
            results.append(result)
            print(json.dumps({"event": "case", **result}, allow_nan=False), flush=True)
            if result["pytest_exit"] not in (0, 1):
                break
            if node == METRICS_NODE and result["pytest_exit"]:
                break
    summary = {
        "event": "summary",
        "cases": len(results),
        "failures": sum(value["pytest_exit"] != 0 for value in results),
        "source_unchanged": source_hashes(root) == frozen,
        "metrics_attempts": sum(value["node"] == METRICS_NODE for value in results),
        "tls_attempts": sum(value["node"] == TLS_NODE for value in results),
        "controlled_ready_attempts": sum(value["phase"] == "controlled-ready" for value in results),
    }
    print(json.dumps(summary), flush=True)
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write("```json\n" + json.dumps(summary, indent=2) + "\n```\n")
    return int(bool(summary["failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
