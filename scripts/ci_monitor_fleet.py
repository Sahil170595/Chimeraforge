"""Installed passive monitoring of three declared native replicas on local protocol fixtures."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any, Iterator


def _histogram(model: str, count: int) -> bytes:
    name = "vllm:time_to_first_token_seconds"
    labels = f'model_name={json.dumps(model)},engine="0"'
    rows = [f"# TYPE {name} histogram"]
    rows.extend(
        f'{name}_bucket{{{labels},le="{edge}"}} {count}' for edge in ("0.1", "0.5", "1.0", "+Inf")
    )
    rows += [f"{name}_count{{{labels}}} {count}", f"{name}_sum{{{labels}}} {count * 0.05}"]
    return ("\n".join(rows) + "\n").encode()


@contextmanager
def _server(model: str) -> Iterator[tuple[list[str], dict[str, int]]]:
    counts: dict[str, int] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            prefix, _, route = self.path[1:].partition("/")
            if route == "metrics":
                number = counts.get(prefix, 0)
                counts[prefix] = number + 1
                raw = _histogram(model, 100 + 20 * number)
            else:
                data = (
                    {"version": "0.30.0"}
                    if route == "version"
                    else {"data": [{"id": model}]}
                    if route == "v1/models"
                    else {}
                )
                raw = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    worker.start()
    try:
        yield [f"http://127.0.0.1:{server.server_port}/r{i}/metrics" for i in range(3)], counts
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
        assert not worker.is_alive(), "passive fixture server failed to close"


def accept(cwd: Path, env: dict, saved: Path, index: int) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge import api
    from chimeraforge.fleet_monitor import FleetEndpoint, FleetMonitorRequest, prometheus_text

    original = saved.read_bytes()
    data = json.loads(original)
    candidate = data["result"]["candidates"][index]
    assert (
        candidate["n_agents"] == 3
        and candidate["gpus_total"] == 6
        and candidate["backend"] == "vllm"
    )
    prometheus = cwd / "fleet-monitor.prom"
    with _server(candidate["model"]) as (urls, counts):
        endpoints = tuple(FleetEndpoint(f"replica-{i + 1}", url) for i, url in enumerate(urls))
        request = FleetMonitorRequest(
            endpoints, interval=0.01, ttft_slo=500, observation_seconds=10
        )
        direct = asyncio.run(api.monitor_fleet(saved, request, candidate_index=index))
        assert direct.exit_code == 0 and direct.cleanup["state"] == "completed", direct.to_dict()
        assert all(
            len(slot.windows) == 1 and slot.windows[0].metrics["ttft"].samples == 20
            for slot in direct.slots
        )
        counts.clear()
        common = [
            "monitor-fleet",
            "--from-plan",
            str(saved),
            "--candidate-index",
            str(index),
            "--interval",
            "0.01",
            "--ttft-slo",
            "500",
            "--observation-seconds",
            "10",
            "--json",
        ]
        for endpoint in endpoints:
            common += ["--endpoint", f"{endpoint.id}={endpoint.url}"]
        observed = json.loads(run_cli([*common, "--prometheus", str(prometheus)], cwd, env))
        assert observed["exit_code"] == 0 and observed["declared_coverage"]["complete"] == 3
        assert [slot["id"] for slot in observed["slots"]] == [value.id for value in endpoints]
        assert all(slot["binding"]["identity"]["state"] == "matched" for slot in observed["slots"])
        assert all(
            slot["binding"]["configuration"]["fields"]["replicas"]["expected"] == 3
            for slot in observed["slots"]
        )
        text = prometheus.read_text()
        headers = [line for line in text.splitlines() if line.startswith("# TYPE")]
        assert len(headers) == len(set(headers)) and all(
            f'replica="{value.id}"' in text for value in endpoints
        )
        assert "chimeraforge_fleet_qualification" in prometheus_text(direct)
        partial = json.loads(run_cli([*common, "--max-requests", "1"], cwd, env, 4))
        assert len(partial["slots"]) == 3 and partial["budget"]["requests"] == 1
        assert (
            partial["budget"]["termination"] == "request_limit"
            and partial["cleanup"]["state"] == "completed"
        )
    assert saved.read_bytes() == original
    return {
        "scope": "complete declared endpoint coverage of local passive protocol fixtures",
        "native_replicas": 3,
        "gpus_total": 6,
        "complete_declared_slots": 3,
        "api_exit": direct.exit_code,
        "cli_exit": observed["exit_code"],
        "partial_exit": partial["exit_code"],
        "identity": "matched",
        "configuration": "unverified",
        "windows_per_endpoint": 1,
        "samples_per_window": 20,
        "source_bytes_unchanged": True,
        "source_plan_sha256": hashlib.sha256(original).hexdigest(),
        "prometheus": "per-replica; one header per family",
        "fixture_resources": "closed",
        "gpu_execution": "unverified",
        "physical_independence": "unverified",
    }
