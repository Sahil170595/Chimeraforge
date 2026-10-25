"""Regenerable original-fleet CLI/API protocol controls, never inference evidence."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import threading
from typing import Any

from ci_native_stream import frames
from ci_secure_monitor import certificates

MEMBERS = 3
REQUESTS = 6
FIXTURE_JOIN_SECONDS = 5


@contextmanager
def server(
    model: str,
    backend: str,
    cap: int,
    prompt_tokens: int,
    *,
    paths: dict[str, Path] | None = None,
    token: str | None = None,
    short: bool = False,
    preflight: bool = False,
) -> Iterator[tuple[str, list[dict]]]:
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            return

        def response(self, code: int, raw: bytes, content: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def admitted(self) -> str | None:
            member, _, route = self.path.strip("/").partition("/")
            authorized = token is None or self.headers.get("Authorization") == "Bearer " + token
            calls.append(
                {
                    "member": member,
                    "route": route,
                    "method": self.command,
                    "authorized": authorized,
                    "client_certificate": bool(self.connection.getpeercert())
                    if isinstance(self.connection, ssl.SSLSocket)
                    else False,
                }
            )
            if not authorized:
                self.response(401, b"{}")
                return None
            return route

        def do_GET(self) -> None:
            route = self.admitted()
            if route is None:
                return
            if preflight and route == "health" and self.path.startswith("/r2/"):
                self.response(503, b"{}")
                return
            info = {
                "version": "controlled-protocol",
                "dtype": "float16",
                "tp_size": 2,
                "pp_size": 1,
                "max_total_num_tokens": 2048,
            }
            if backend == "vllm":
                info = {
                    "version": "controlled-protocol",
                    "vllm_config": {
                        "model_config": {"dtype": "float16", "max_model_len": 2048},
                        "parallel_config": {
                            "tensor_parallel_size": 2,
                            "pipeline_parallel_size": 1,
                            "data_parallel_size": 1,
                        },
                    },
                }
            values = {
                "health": {},
                "version": {"version": "controlled-protocol"},
                "v1/models": {"data": [{"id": model}]},
                "server_info?config_format=json": info,
                "server_info": info,
                "get_server_info": info,
                "model_info": {"served_model_name": model},
            }
            self.response(
                200 if route in values else 404, json.dumps(values.get(route, {})).encode()
            )

        def do_POST(self) -> None:
            route = self.admitted()
            if route is None:
                return
            assert route == "v1/completions"
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert request["model"] == model and request["max_tokens"] == cap
            assert request["stream"] is True
            self.response(
                200,
                frames(
                    backend, "complete", output_tokens=cap - int(short), prompt_tokens=prompt_tokens
                ),
                "text/event-stream",
            )

    listener = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    listener.daemon_threads = False
    listener.block_on_close = True
    if paths:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(paths["server"], paths["server_key"])
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=paths["ca"])
        listener.socket = context.wrap_socket(listener.socket, server_side=True)
    worker = threading.Thread(target=listener.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        yield f"{'https' if paths else 'http'}://127.0.0.1:{listener.server_port}", calls
    finally:
        listener.shutdown()
        listener.server_close()
        worker.join(FIXTURE_JOIN_SECONDS)
        assert not worker.is_alive()


def accept(cwd: Path, env: dict, saved: Path) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge import api

    original = saved.read_bytes()
    data = json.loads(original)
    paths = certificates(cwd / "fleet-trace-tls")
    controls = []
    for backend in ("vllm", "sglang"):
        index = next(
            i
            for i, row in enumerate(data["result"]["candidates"])
            if row["backend"] == backend and row["quant"] == "FP16" and row["n_agents"] == MEMBERS
        )
        candidate = data["result"]["candidates"][index]
        cap, model = candidate["decode_tokens_per_req"], candidate["model"]
        requests = [
            {
                "request_id": f"trace-{i}",
                "prompt": f"private-fleet-prompt-{i}",
                "max_output_tokens": cap,
                "arrival_offset_s": 0,
            }
            for i in range(REQUESTS)
        ]
        routes = [
            {"request_id": row["request_id"], "endpoint_id": f"member-{i % MEMBERS + 1}"}
            for i, row in enumerate(requests)
        ]
        work, routing = cwd / "fleet-trace-work.json", cwd / "fleet-trace-routes.json"
        work.write_text(json.dumps(requests), encoding="utf-8")
        routing.write_text(json.dumps(routes), encoding="utf-8")
        work_raw, route_raw = work.read_bytes(), routing.read_bytes()
        for mode in ("complete", "mtls", "short", "preflight"):
            secure = mode == "mtls"
            with server(
                model,
                backend,
                cap,
                data["inputs"]["prompt_tokens"],
                paths=paths if secure else None,
                token="FixtureFleetToken79" if secure else None,
                short=mode == "short",
                preflight=mode == "preflight",
            ) as (url, calls):
                endpoints = tuple(
                    api.FleetEndpoint(f"member-{i}", url + f"/r{i}") for i in range(1, MEMBERS + 1)
                )
                connections = (
                    None
                    if not secure
                    else {
                        row.id: api.MonitorConnection(
                            row.url,
                            ca_bundle=paths["ca"],
                            client_cert=paths["client"],
                            client_key=paths["client_key"],
                            bearer_token="FixtureFleetToken79",
                        )
                        for row in endpoints
                    }
                )
                direct = asyncio.run(
                    api.replay_fleet_trace(
                        saved,
                        work,
                        endpoints,
                        routing,
                        candidate_index=index,
                        concurrency=MEMBERS,
                        request_timeout=5,
                        trace_timeout=10,
                        connections=connections,
                    )
                ).to_dict()
                wanted = int(mode in ("short", "preflight"))
                args = [
                    "trace-fleet",
                    str(work),
                    "--from-plan",
                    str(saved),
                    "--routes",
                    str(routing),
                    "--candidate-index",
                    str(index),
                    "--concurrency",
                    str(MEMBERS),
                    "--json",
                ]
                for endpoint in endpoints:
                    args += ["--endpoint", f"{endpoint.id}={endpoint.url}"]
                    if secure:
                        for flag, value in (
                            ("--ca-bundle", paths["ca"]),
                            ("--client-cert", paths["client"]),
                            ("--client-key", paths["client_key"]),
                            ("--bearer-env", "CF_FLEET_TOKEN79"),
                        ):
                            args += [flag, f"{endpoint.id}={value}"]
                cli = json.loads(
                    run_cli(args, cwd, dict(env, CF_FLEET_TOKEN79="FixtureFleetToken79"), wanted)
                )
                for report in (direct, cli):
                    assert api.load_fleet_trace(report).to_dict() == report
                    assert report["exit_code"] == wanted
                    assert report["plan"]["snapshot"] == data
                    assert report["cleanup"]["state"] == "completed"
                    assert [row["row_indices"] for row in report["slots"]] == [
                        [0, 3],
                        [1, 4],
                        [2, 5],
                    ]
                    assert report["native_trace"]["execution"]["planned"] == REQUESTS
                    assert report["native_trace"]["execution"]["completed"] == (
                        0 if mode == "preflight" else REQUESTS
                    )
                    assert "private-fleet-prompt" not in json.dumps(report)
                    assert "FixtureFleetToken79" not in json.dumps(report)
                assert all(
                    row["authorized"] and (not secure or row["client_certificate"]) for row in calls
                )
                generated = [row for row in calls if row["method"] == "POST"]
                assert len(generated) == (0 if mode == "preflight" else 2 * REQUESTS)
                controls.append(
                    {
                        "backend": backend,
                        "mode": mode,
                        "api_exit": direct["exit_code"],
                        "cli_exit": cli["exit_code"],
                        "original_replicas": MEMBERS,
                        "rows_per_interface": REQUESTS,
                        "generation_contacts": len(generated),
                        "all_owned_resources_closed": True,
                    }
                )
        assert work.read_bytes() == work_raw and routing.read_bytes() == route_raw
    assert saved.read_bytes() == original
    return {
        "controls": controls,
        "original_bytes_unchanged": True,
        "scope": (
            "one local protocol listener with three declared paths per control; "
            "no inference, GPU, physical independence or capacity qualification"
        ),
        "fixture_resources": "closed",
    }


def main() -> int:
    import argparse
    import os
    import tempfile
    from chimeraforge import __version__, api

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cf-fleet-trace-") as temporary:
        cwd = Path(temporary)
        saved = cwd / "saved.json"
        artifact = api.plan(
            api.PlanRequest(
                models=["ci/manual-fleet"],
                overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                hardware="RTX 4090 24GB",
                platform="linux",
                tensor_parallel=2,
                request_rate=128,
                latency_slo=10000,
                quality_target=0,
                budget=1e8,
                allow_network=False,
            )
        )
        artifact.save(saved)
        result = accept(cwd, dict(os.environ), saved)
    root = Path(__file__).resolve().parents[1]
    files = [
        Path(__file__),
        *sorted((root / "src/chimeraforge/bench").glob("fleet_trace*.py")),
        root / "src/chimeraforge/bench/trace.py",
        root / "src/chimeraforge/bench/plan_trace.py",
        root / "src/chimeraforge/bench/serving_binding.py",
        root / "src/chimeraforge/api.py",
        root / "src/chimeraforge/commands/trace_fleet.py",
    ]
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "evidence": (
            "source CLI/API protocol controls; not installed distribution or native inference proof"
        ),
        "result": result,
        "source_sha256": {
            str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in files
        },
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"controls": len(result["controls"]), "resources": "closed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
