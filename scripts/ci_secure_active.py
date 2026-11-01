"""Owned CPU HTTPS streaming fixtures; no real engine or performance qualification."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import threading
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact
    from chimeraforge.monitor_connection import MonitorConnection

from ci_secure_monitor import certificates

MODEL = "ci/manual-active"
OUTPUT_CAP = 4
PROMPT_TOKENS = 8
STREAM_GAP_SECONDS = 0.03
FIXTURE_JOIN_SECONDS = 5


def packets(output_tokens: int = OUTPUT_CAP) -> tuple[bytes, bytes]:
    def event(value: dict) -> bytes:
        return ("data: " + json.dumps(value) + "\n\n").encode()

    first = event(
        {"choices": [{"index": 0, "text": "fixture", "token_ids": [10], "finish_reason": None}]}
    )
    final = event(
        {
            "choices": [
                {
                    "index": 0,
                    "text": " tail",
                    "token_ids": list(range(11, 10 + output_tokens)),
                    "finish_reason": "length",
                }
            ]
        }
    )
    final += event(
        {
            "choices": [],
            "usage": {
                "completion_tokens": output_tokens,
                "prompt_tokens": PROMPT_TOKENS,
                "total_tokens": output_tokens + PROMPT_TOKENS,
            },
        }
    )
    return first, final + b"data: [DONE]\n\n"


@contextmanager
def server(
    paths: dict[str, Path],
    *,
    backend: str,
    cap: int = OUTPUT_CAP,
    token: str | None = None,
    mtls: bool = False,
    wrong_host: bool = False,
    redirect: str | None = None,
    malformed: bool = False,
    echo: str | None = None,
    release: threading.Event | None = None,
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    calls: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:
            return

        def respond(self, code: int, raw: bytes, content: str = "application/json") -> None:
            self.send_response(code, echo)
            if echo:
                self.send_header("X-Fictional-Provider", echo)
            self.send_header("Content-Type", content)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            self.wfile.flush()

        def admitted(self) -> bool:
            authorized = token is None or self.headers.get("Authorization") == "Bearer " + token
            calls.append(
                {
                    "route": self.path.strip("/"),
                    "method": self.command,
                    "authorized": authorized,
                    "client_certificate": bool(self.connection.getpeercert()),
                }
            )
            if not authorized:
                self.respond(401, b"{}")
                return False
            if redirect:
                self.send_response(307)
                self.send_header("Location", redirect)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return False
            return True

        def do_GET(self) -> None:
            if not self.admitted():
                return
            model = {"dtype": "float16", "max_model_len": 2048}
            parallel = {
                "tensor_parallel_size": 1,
                "pipeline_parallel_size": 1,
                "data_parallel_size": 1,
            }
            info = {
                "version": "0.5.20",
                "dtype": "float16",
                "tp_size": 1,
                "pp_size": 1,
                "max_total_num_tokens": 2048,
            }
            if backend == "vllm":
                info = {
                    "version": "0.30.0",
                    "vllm_config": {"model_config": model, "parallel_config": parallel},
                }
            values = {
                "health": {},
                "version": {"version": "0.30.0"},
                "v1/models": {"data": [{"id": MODEL}]},
                "server_info?config_format=json": info,
                "server_info": info,
                "get_server_info": info,
                "model_info": {"served_model_name": MODEL},
            }
            route = self.path.strip("/")
            self.respond(
                200 if route in values else 404, json.dumps(values.get(route, {})).encode()
            )

        def do_POST(self) -> None:
            size = int(self.headers["Content-Length"])
            request = json.loads(self.rfile.read(size))
            if not self.admitted():
                return
            assert self.path == "/v1/completions"
            assert request["model"] == MODEL and request["max_tokens"] == cap
            assert request["stream"] is True
            first, final = packets(cap)
            if malformed:
                first, final = b"data: not-json\n\n", b"data: [DONE]\n\n"
            self.send_response(200, echo)
            if echo:
                self.send_header("X-Fictional-Provider", echo)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(first) + len(final)))
            self.end_headers()
            self.wfile.write(first)
            self.wfile.flush()
            if release is None:
                time.sleep(STREAM_GAP_SECONDS)
            else:
                assert release.wait(FIXTURE_JOIN_SECONDS), "fixture stream was not released"
            self.wfile.write(final)
            self.wfile.flush()

    listener = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    listener.daemon_threads = False
    listener.block_on_close = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    identity = "wrong_host" if wrong_host else "server"
    context.load_cert_chain(paths[identity], paths[identity + "_key"])
    if mtls:
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=paths["ca"])
    listener.socket = context.wrap_socket(listener.socket, server_side=True)
    worker = threading.Thread(target=listener.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        yield f"https://127.0.0.1:{listener.server_port}", calls
    finally:
        listener.shutdown()
        listener.server_close()
        worker.join(FIXTURE_JOIN_SECONDS)
        assert not worker.is_alive(), "secure active fixture listener did not close"


def seed() -> tuple[PlanArtifact, dict[str, int]]:
    """One offline native plan, with unchanged original candidate choices."""
    from chimeraforge import api

    saved = api.plan(
        api.PlanRequest(
            models=[MODEL],
            overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            request_rate=0.1,
            latency_slo=100000,
            avg_tokens=OUTPUT_CAP,
            prompt_tokens=PROMPT_TOKENS,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    indices = {
        backend: next(
            i
            for i, row in enumerate(saved.to_dict()["result"]["candidates"])
            if row["backend"] == backend
            and row["quant"] == "FP16"
            and row["n_agents"] == row["tensor_parallel"] == row["pipeline_parallel"] == 1
        )
        for backend in ("vllm", "sglang")
    }
    return saved, indices


async def invoke(
    mode: str,
    saved: PlanArtifact,
    index: int,
    backend: str,
    url: str,
    connection: MonitorConnection,
) -> tuple[Any, dict[str, Any]]:
    from chimeraforge import api
    from chimeraforge.bench.metrics import result_to_dict
    from chimeraforge.bench.runner import run_benchmark
    from chimeraforge.bench.trace_workload import TraceRequest

    options: dict[str, Any] = {"model": MODEL, "base_url": url, "connection": connection}
    receipt: Any
    rows = [TraceRequest("one", "fixture", OUTPUT_CAP, 0)]
    if mode == "bench":
        receipt = await run_benchmark(
            MODEL,
            backend,
            runs=1,
            prompt="fixture",
            options={"max_tokens": OUTPUT_CAP},
            base_url=url,
            connection=connection,
        )
        assert (
            receipt.aggregate.count == 1
            and receipt.individual_runs[0].tokens_generated == OUTPUT_CAP
        )
        return receipt, result_to_dict(receipt)
    if mode == "trace":
        receipt = await api.replay_trace(rows, backend=backend, **options)
        report = receipt.to_dict()
        assert report["exit_code"] == 0 and report["execution"]["completed"] == 1, report
    elif mode == "saved-bench":
        receipt = await api.benchmark_plan(saved, candidate_index=index, runs=1, **options)
        report = receipt.to_dict()
        assert report["execution"]["successful_count"] == 1, report
    else:
        receipt = await api.replay_plan_trace(saved, rows, candidate_index=index, **options)
        report = receipt.to_dict()
        assert report["native_trace"]["execution"]["completed"] == 1, report
    return receipt, report


def accept(cwd: Path, env: dict, checkout: Path | None = None) -> dict:
    """Consume real public APIs and CLI against owned TLS protocol fixtures."""
    import asyncio
    import hashlib

    from ci_installed_acceptance import assert_installed_origin, assert_installed_modules, run_cli
    from chimeraforge import __version__, api
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError

    loaded_before = None
    if checkout is not None:
        assert_installed_origin(api.__file__, checkout)
        loaded_before = assert_installed_modules(checkout)
    cwd.mkdir(parents=True, exist_ok=True)
    saved, indices = seed()
    source, workload = cwd / "plan.json", cwd / "workload.json"
    saved.save(source)
    workload.write_text(
        json.dumps(
            [
                {
                    "request_id": "one",
                    "prompt": "fixture",
                    "max_output_tokens": OUTPUT_CAP,
                    "arrival_offset_s": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    held = (source.read_bytes(), workload.read_bytes())
    paths = certificates(cwd / "tls")
    token = "FixtureActiveToken_82"
    cli_env = {**env, "CF_FIXTURE_ACTIVE82": token}
    positive, negative, aliases = [], [], []
    receipts = {}
    for backend in ("vllm", "sglang"):
        for mtls in (False, True):
            for mode in ("bench", "trace", "saved-bench", "saved-trace"):
                cap = 256 if mode == "bench" else OUTPUT_CAP
                with server(
                    paths, backend=backend, cap=cap, token=token, mtls=mtls, echo=token
                ) as (url, calls):
                    connection = MonitorConnection(
                        url,
                        ca_bundle=paths["ca"],
                        bearer_token=token,
                        client_cert=paths["client"] if mtls else None,
                        client_key=paths["client_key"] if mtls else None,
                    )
                    # The ordinary API accepts a cap; ordinary CLI retains its native default256.
                    if mode == "bench":
                        with server(paths, backend=backend, token=token, mtls=mtls, echo=token) as (
                            api_url,
                            api_calls,
                        ):
                            api_connection = MonitorConnection(
                                api_url,
                                ca_bundle=paths["ca"],
                                bearer_token=token,
                                client_cert=paths["client"] if mtls else None,
                                client_key=paths["client_key"] if mtls else None,
                            )
                            receipt, report = asyncio.run(
                                invoke(
                                    mode, saved, indices[backend], backend, api_url, api_connection
                                )
                            )
                            assert api_calls and all(
                                row["authorized"] and row["client_certificate"] == mtls
                                for row in api_calls
                            )
                    else:
                        receipt, report = asyncio.run(
                            invoke(mode, saved, indices[backend], backend, url, connection)
                        )
                    receipts[mode] = receipt
                    assert token not in json.dumps(report)
                    flags = [
                        "--model",
                        MODEL,
                        "--base-url",
                        url,
                        "--secure",
                        "--bearer-env",
                        "CF_FIXTURE_ACTIVE82",
                        "--ca-bundle",
                        str(paths["ca"]),
                        "--json",
                    ]
                    if mtls:
                        flags += [
                            "--client-cert",
                            str(paths["client"]),
                            "--client-key",
                            str(paths["client_key"]),
                        ]
                    if "bench" in mode:
                        arguments = [
                            "bench",
                            "--runs",
                            "1",
                            "--output-dir",
                            str(cwd / "results"),
                            *flags,
                        ]
                        arguments += (
                            ["--plan", str(source), "--candidate-index", str(indices[backend])]
                            if mode == "saved-bench"
                            else ["--backend", backend]
                        )
                    else:
                        arguments = ["trace", str(workload), *flags]
                        arguments += (
                            ["--from-plan", str(source), "--candidate-index", str(indices[backend])]
                            if mode == "saved-trace"
                            else ["--backend", backend]
                        )
                    cli_report = json.loads(
                        run_cli(
                            arguments,
                            cwd,
                            cli_env,
                            forbidden=(token, "CF_FIXTURE_ACTIVE82", str(paths["client_key"])),
                        )
                    )
                    assert token not in json.dumps(cli_report)
                    assert calls and all(
                        row["authorized"] and row["client_certificate"] == mtls for row in calls
                    )
                    if mode != "bench":
                        metadata = (
                            "server_info?config_format=json" if backend == "vllm" else "model_info"
                        )
                        assert sum(row["route"] == metadata for row in calls) == 4, calls
                    positive.append(
                        {
                            "backend": backend,
                            "mode": mode,
                            "mutual_tls": mtls,
                            "api": "completed",
                            "cli": "completed",
                            "authorized_routes": sorted({row["route"] for row in calls}),
                            "before_after_metadata": mode != "bench",
                        }
                    )
        for mtls in (False, True):
            with server(paths, backend=backend, mtls=mtls) as (url, calls):
                connection = MonitorConnection(
                    url,
                    ca_bundle=paths["ca"],
                    client_cert=paths["client"] if mtls else None,
                    client_key=paths["client_key"] if mtls else None,
                )
                _, report = asyncio.run(
                    invoke("trace", saved, indices[backend], backend, url, connection)
                )
                flags = (
                    [
                        "--client-cert",
                        str(paths["client"]),
                        "--client-key",
                        str(paths["client_key"]),
                    ]
                    if mtls
                    else []
                )
                cli = json.loads(
                    run_cli(
                        [
                            "trace",
                            str(workload),
                            "--model",
                            MODEL,
                            "--backend",
                            backend,
                            "--base-url",
                            url,
                            "--secure",
                            "--ca-bundle",
                            str(paths["ca"]),
                            *flags,
                            "--json",
                        ],
                        cwd,
                        cli_env,
                    )
                )
                assert report["exit_code"] == cli["exit_code"] == 0 and all(
                    row["client_certificate"] == mtls for row in calls
                )
                positive.append(
                    {
                        "backend": backend,
                        "mode": "trace",
                        "bearer": False,
                        "mutual_tls": mtls,
                        "api": "completed",
                        "cli": "completed",
                        "authorized_routes": sorted({row["route"] for row in calls}),
                        "before_after_metadata": True,
                    }
                )
        for fault in (
            "wrong-ca",
            "wrong-host",
            "wrong-token",
            "missing-client",
            "redirect",
            "malformed-sse",
        ):
            with (
                server(paths, backend=backend) as (other_url, other_calls),
                server(
                    paths,
                    backend=backend,
                    token=token,
                    mtls=fault == "missing-client",
                    wrong_host=fault == "wrong-host",
                    redirect=other_url if fault == "redirect" else None,
                    malformed=fault == "malformed-sse",
                ) as (url, calls),
            ):
                ca = paths["wrong_ca"] if fault == "wrong-ca" else paths["ca"]
                supplied = "wrong" if fault == "wrong-token" else token
                connection = MonitorConnection(url, ca_bundle=ca, bearer_token=supplied)
                from chimeraforge.bench.trace_workload import TraceRequest

                report = asyncio.run(
                    api.replay_trace(
                        [TraceRequest("one", "fixture", OUTPUT_CAP, 0)],
                        model=MODEL,
                        backend=backend,
                        base_url=url,
                        connection=connection,
                    )
                ).to_dict()
                assert report["exit_code"] == 1 and report["execution"]["completed"] == 0, report
                cli_report = json.loads(
                    run_cli(
                        [
                            "trace",
                            str(workload),
                            "--model",
                            MODEL,
                            "--backend",
                            backend,
                            "--base-url",
                            url,
                            "--secure",
                            "--bearer-env",
                            "CF_FIXTURE_ACTIVE82",
                            "--ca-bundle",
                            str(ca),
                            "--json",
                        ],
                        cwd,
                        {**cli_env, "CF_FIXTURE_ACTIVE82": supplied},
                        expected_code=1,
                        forbidden=(token, "CF_FIXTURE_ACTIVE82"),
                    )
                )
                assert cli_report["execution"]["completed"] == 0 and not other_calls
                if fault != "malformed-sse":
                    assert not any(row["method"] == "POST" for row in calls)
                negative.append(
                    {
                        "backend": backend,
                        "fault": fault,
                        "api_exit": 1,
                        "cli_exit": 1,
                        "second_origin_contacts": len(other_calls),
                    }
                )
    before = {name: path.read_bytes() for name, path in paths.items()}
    for mode in ("trace", "saved-trace", "saved-bench"):
        for role in ("ca", "client", "client_key"):
            try:
                receipts[mode].save(paths[role])
            except (api.PlanError, MonitorConnectionError):
                aliases.append({"mode": mode, "input": role, "api_refused": True})
            else:
                raise AssertionError("TLS input was not protected")
    assert {name: path.read_bytes() for name, path in paths.items()} == before
    assert held == (source.read_bytes(), workload.read_bytes())
    return {
        "version": __version__,
        "positive": positive,
        "negative": negative,
        "output_aliases": aliases,
        "positive_invocations": 2 * len(positive),
        "negative_invocations": 2 * len(negative),
        "source_sha256": hashlib.sha256(held[0]).hexdigest(),
        "workload_sha256": hashlib.sha256(held[1]).hexdigest(),
        "source_bytes_unchanged": True,
        "installed_module_provenance": (
            {"before": loaded_before, "after": assert_installed_modules(checkout)}
            if checkout is not None
            else None
        ),
        "owned_fixture_listeners_and_handlers_closed": True,
        "scope": (
            "owned CPU HTTPS protocol fixtures; "
            "no actual engine, model, GPU or performance qualification"
        ),
    }


def main() -> int:
    import argparse
    from datetime import datetime, timezone
    import hashlib
    import os
    import tempfile

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cf-secure-active-") as temporary:
        result = accept(args.work_dir or Path(temporary), dict(os.environ))
    root = Path(__file__).resolve().parents[1]
    sources = [
        "scripts/ci_secure_active.py",
        "src/chimeraforge/transport_logging.py",
        "src/chimeraforge/monitor_connection.py",
        "src/chimeraforge/bench/backends/__init__.py",
        "src/chimeraforge/bench/backends/base.py",
        "src/chimeraforge/bench/runner.py",
        "src/chimeraforge/bench/plan.py",
        "src/chimeraforge/bench/trace.py",
        "src/chimeraforge/bench/plan_trace.py",
        "src/chimeraforge/api.py",
        "src/chimeraforge/commands/bench.py",
        "src/chimeraforge/commands/trace.py",
        "src/chimeraforge/commands/bench_plan.py",
        "src/chimeraforge/bench/backends/vllm.py",
        "src/chimeraforge/bench/backends/sglang.py",
        "src/chimeraforge/monitor.py",
        "src/chimeraforge/plan_monitor.py",
        "src/chimeraforge/fleet_monitor.py",
        "src/chimeraforge/bench/fleet_trace.py",
        "scripts/ci_installed_acceptance.py",
    ]
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "evidence": (
            "source CLI/API owned CPU HTTPS protocol fixtures; "
            "not installed or physical qualification"
        ),
        "result": result,
        "source_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources
        },
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
