"""Accept the cached exporter through native CPU protocol and real OS CLI paths."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Iterator

import httpx

from ci_monitor_fleet import _histogram

WAIT_SECONDS = 15
CLI_RUN_SECONDS = 3
POLL_SECONDS = 2


@contextmanager
def _server(model: str) -> Iterator[tuple[list[str], dict[str, Any]]]:
    state: dict[str, Any] = {"requests": 0, "metrics": {}}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state["requests"] += 1
            prefix, _, route = self.path[1:].partition("/")
            if route == "metrics":
                count = state["metrics"].get(prefix, 0)
                state["metrics"][prefix] = count + 1
                raw = _histogram(model, 100 + 20 * count)
                raw += raw.replace(
                    b"vllm:time_to_first_token_seconds",
                    b"vllm:request_time_per_output_token_seconds",
                )
            else:
                value = (
                    {"version": "0.30.0"}
                    if route == "version"
                    else {"data": [{"id": model}]}
                    if route == "v1/models"
                    else {}
                )
                raw = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = False
    server.block_on_close = True
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        yield [f"http://127.0.0.1:{server.server_port}/r{i}/metrics" for i in range(3)], state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(WAIT_SECONDS)
        assert not worker.is_alive()


def _request(urls: list[str]) -> Any:
    from chimeraforge import api

    return api.FleetMonitorRequest(
        tuple(api.FleetEndpoint(f"private-slot-{i + 1}", url) for i, url in enumerate(urls)),
        interval=0.01,
        ttft_slo=500,
        observation_seconds=5,
    )


async def _published(running: Any, sequence: int = 0) -> Any:
    deadline = asyncio.get_running_loop().time() + WAIT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        snapshot = running.snapshot()
        if snapshot.sequence > sequence and snapshot.state == "fresh":
            return snapshot
        await asyncio.sleep(0.01)
    raise AssertionError("native exporter snapshot unavailable")


async def _api(
    saved: Path,
    index: int,
    urls: list[str],
    requests: Callable[[], int],
    connections: Any = None,
) -> dict:
    from chimeraforge import api

    config = api.FleetExporterConfig(
        port=0,
        poll_seconds=POLL_SECONDS,
        stale_after_seconds=1,
    )
    async with api.serve_fleet_exporter(
        saved,
        _request(urls),
        candidate_index=index,
        config=config,
        connections=connections,
    ) as running:
        first = await _published(running)
        assert first.native_exit_code == 0 and first.original_replicas == 3
        assert all(f'replica="replica-{i}"'.encode() in first.body for i in (1, 2, 3))
        assert b"private-slot" not in first.body and all(
            url.encode() not in first.body for url in urls
        )
        before = requests()
        async with httpx.AsyncClient(
            trust_env=False,
            timeout=3,
            limits=httpx.Limits(
                max_connections=5, max_keepalive_connections=5, keepalive_expiry=0.5
            ),
        ) as client:
            responses = await asyncio.gather(*[client.get(running.metrics_url) for _ in range(5)])
            assert all(row.status_code == 200 and row.content == first.body for row in responses)
            assert requests() == before
            await asyncio.sleep(1.02)
            stale = await client.get(running.metrics_url)
            snapshot = running.snapshot()
            assert snapshot.state == "stale" and snapshot.native_exit_code == 4
            assert stale.content == snapshot.body and requests() == before
            assert b"chimeraforge_fleet_slot_p95_lower_ms{" not in snapshot.body
            assert b"chimeraforge_fleet_slot_samples{" not in snapshot.body
        later = await _published(running, first.sequence)
        assert later.native_exit_code == 0
    assert running.closed and running.listener_joined and running.worker_joined
    assert running.snapshot().state == "stopped"
    before = requests()
    await asyncio.sleep(0.03)
    assert requests() == before
    return {
        "replicas": 3,
        "cache_scrapes": 5,
        "scrape_backend_requests": 0,
        "stale_unknown": True,
        "native_poll_resumed": True,
        "safe_labels": True,
        "listener_joined": True,
        "worker_joined": True,
    }


def _cli(cwd: Path, env: dict, saved: Path, index: int, urls: list[str], state: dict) -> dict:
    common = [
        "monitor-fleet-exporter",
        "--from-plan",
        str(saved),
        "--candidate-index",
        str(index),
        "--interval",
        "0.01",
        "--observation-seconds",
        "5",
        "--ttft-slo",
        "500",
        "--listen-port",
        "0",
        "--poll-seconds",
        str(POLL_SECONDS),
    ]
    for i, url in enumerate(urls):
        common += ["--endpoint", f"private-slot-{i + 1}={url}"]
    stdout, stderr = cwd / "exporter-cli.stdout", cwd / "exporter-cli.stderr"
    args = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "chimeraforge",
        *common,
        "--run-seconds",
        str(CLI_RUN_SECONDS),
    ]
    with stdout.open("wb") as out, stderr.open("wb") as err:
        child = subprocess.Popen(
            args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err
        )
        try:
            deadline = time.monotonic() + WAIT_SECONDS
            ready = None
            while time.monotonic() < deadline:
                raw = stdout.read_bytes()
                assert len(raw) <= 16384
                if b"\n" in raw:
                    ready = json.loads(raw.splitlines()[0])
                    break
                assert child.poll() is None, stderr.read_bytes()
                time.sleep(0.01)
            assert ready and ready["kind"] == "chimeraforge.fleet-exporter-ready"
            assert ready["replicas"] == 3 and ready["process_exit_is_qualification"] is False
            with httpx.Client(trust_env=False, timeout=3) as client:
                while time.monotonic() < deadline:
                    response = client.get(ready["metrics_url"])
                    if b'chimeraforge_fleet_qualification{outcome="pass"} 1' in response.content:
                        break
                    time.sleep(0.01)
                else:
                    raise AssertionError("native CLI exporter never published")
                before = state["requests"]
                for _ in range(5):
                    assert client.get(ready["metrics_url"]).content == response.content
                assert state["requests"] == before
            code = child.wait(WAIT_SECONDS)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(WAIT_SECONDS)
    assert code == 0, stderr.read_bytes()
    rows = [json.loads(row) for row in stdout.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 and rows[-1] == {
        "kind": "chimeraforge.fleet-exporter-closed",
        "listener_joined": True,
        "worker_joined": True,
    }
    assert b"Traceback" not in stderr.read_bytes()
    return {
        "process_exit": code,
        "cache_scrapes": 5,
        "scrape_backend_requests": 0,
        "ready_and_closed": True,
        "child_joined": True,
    }


def accept(cwd: Path, env: dict, saved: Path, index: int | None = None) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge import api

    cwd.mkdir(parents=True, exist_ok=True)
    before = saved.read_bytes()
    held = api.load_plan(saved)
    candidates = held.to_dict()["result"]["candidates"]
    if index is None:
        index = next(
            i
            for i, c in enumerate(candidates)
            if c["n_agents"] == 3 and c["backend"] == "vllm" and c["quant"] == "FP16"
        )
    candidate = candidates[index]
    assert candidate["n_agents"] == 3 and candidate["backend"] == "vllm"
    with _server(candidate["model"]) as (urls, state):
        direct = asyncio.run(_api(saved, index, urls, lambda: state["requests"]))
        cli = _cli(cwd, env, saved, index, urls, state)
        before_invalid = state["requests"]
        arguments = [
            "monitor-fleet-exporter",
            "--from-plan",
            str(saved),
            "--candidate-index",
            str(index),
            "--listen-port",
            "0",
            "--run-seconds",
            "0.1",
        ]
        for i, url in enumerate(urls):
            arguments += ["--endpoint", f"private-slot-{i + 1}={url if i < 2 else 'invalid'}"]
        run_cli(arguments, cwd, env, 1, forbidden=("invalid-private-secret",))
        assert state["requests"] == before_invalid
    from ci_secure_monitor import certificates, server

    paths = certificates(cwd / "exporter-tls")
    with server(
        paths, model=candidate["model"], token="FictionalExporter91", mtls=True, vllm_tpot=True
    ) as (
        url,
        calls,
    ):
        endpoints = [url + f"/r{i}/metrics" for i in (1, 2, 3)]
        connection = api.MonitorConnection(
            url,
            bearer_token="FictionalExporter91",
            ca_bundle=paths["ca"],
            client_cert=paths["client"],
            client_key=paths["client_key"],
        )
        secure = asyncio.run(
            _api(
                saved,
                index,
                endpoints,
                lambda: len(calls),
                {f"private-slot-{i}": connection for i in (1, 2, 3)},
            )
        )
        assert calls and all(row["authorized"] and row["client_certificate"] for row in calls)
    assert saved.read_bytes() == before
    return {
        "kind": "chimeraforge.fleet-exporter-acceptance",
        "api": direct,
        "os_cli": cli,
        "secure_api": secure,
        "late_invalid_precontact": True,
        "source_sha256": hashlib.sha256(before).hexdigest(),
        "source_bytes_held": True,
        "scope": "CPU controlled native protocol; not an engine",
    }


def record(path: Path, checkout: Path, work: Path) -> None:
    import os
    from datetime import datetime, timezone
    from chimeraforge import __version__, api

    assert not path.exists() and not work.exists()
    assert api.__file__ is not None and Path(api.__file__).resolve().is_relative_to(
        (checkout / "src/chimeraforge").resolve()
    )
    names = sorted(
        set(
            subprocess.check_output(
                [
                    "git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "src/chimeraforge",
                ],
                cwd=checkout,
            )
            .decode()
            .splitlines()
        )
        | {
            str(p.relative_to(checkout)).replace("\\", "/")
            for p in (checkout / "scripts").glob("ci_*.py")
        }
        | {
            "scripts/probe_mcp_stdio.py",
            "pyproject.toml",
            "server.json",
            "uv.lock",
            ".github/workflows/ci.yml",
        }
    )
    before = {name: hashlib.sha256((checkout / name).read_bytes()).hexdigest() for name in names}
    work.mkdir(parents=True)
    saved = work / "plan.json"
    api.plan(
        api.PlanRequest(
            models=["ci/manual-fleet"],
            overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=128,
            latency_slo=10000,
            tpot_slo=1000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    ).save(saved)
    result = accept(work, dict(os.environ), saved)
    assert all(
        hashlib.sha256((checkout / name).read_bytes()).hexdigest() == value
        for name, value in before.items()
    )
    result.update(
        captured_at=datetime.now(timezone.utc).isoformat(),
        tool_version=__version__,
        source_profile="editable source; installed artifact qualification separate",
        source_sha256=before,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    record(args.record, args.checkout, args.work_dir)
