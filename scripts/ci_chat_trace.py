"""Native chat wire/CLI/receiving controls; protocol fixtures are not inference."""

from __future__ import annotations

import asyncio
import argparse
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import tempfile
from typing import Any, TypedDict

MODEL = "ci/manual-chat"
JOIN_SECONDS = 5
REPLICAS = 3


class ProtocolState(TypedDict):
    backend: str
    usage: bool
    short: bool


def workload(cap: int = 8, count: int = 2) -> list[dict]:
    return [
        {
            "request_id": f"chat-{i}",
            "mode": "chat",
            "messages": [
                {"role": "system", "content": "PrivateChat89 system \u03bb"},
                {"role": "user", "content": f"PrivateChat89 request {i}"},
            ],
            "max_output_tokens": cap,
            "arrival_offset_s": i * 0.001,
            "temperature": float(i % 3) / 4,
        }
        for i in range(count)
    ]


def typed(rows: list[dict]) -> list:
    from chimeraforge import api

    return [
        api.ChatTraceRequest(
            r["request_id"],
            tuple(api.ChatMessage(**m) for m in r["messages"]),
            r["max_output_tokens"],
            r["arrival_offset_s"],
            r["temperature"],
        )
        for r in rows
    ]


def frames(backend: str, count: int, *, usage: bool) -> bytes:
    def event(value: dict) -> bytes:
        return ("data: " + json.dumps(value) + "\n\n").encode()

    if backend == "ollama":
        terminal = {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": "stop",
        }
        if usage:
            terminal.update(
                eval_count=count,
                prompt_eval_count=512,
                eval_duration=10000000,
                prompt_eval_duration=1000000,
                total_duration=11000000,
            )
        return (
            (
                json.dumps(
                    {
                        "message": {"role": "assistant", "content": "PrivateChat89 output"},
                        "done": False,
                    }
                )
                + "\n"
            )
            + json.dumps(terminal)
            + "\n"
        ).encode()
    body = event(
        {
            "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}
            ]
        }
    )
    body += event(
        {
            "choices": [
                {"index": 0, "delta": {"content": "PrivateChat89 output"}, "finish_reason": None}
            ]
        }
    )
    body += event({"choices": [{"index": 0, "delta": {}, "finish_reason": "length"}]})
    if usage:
        body += event(
            {
                "choices": [],
                "usage": {
                    "completion_tokens": count,
                    "prompt_tokens": 512,
                    "total_tokens": 512 + count,
                },
            }
        )
    return body + b"data: [DONE]\n\n"


@contextmanager
def server() -> Iterator[tuple[str, ProtocolState, list[dict[str, Any]]]]:
    state: ProtocolState = {"backend": "vllm", "usage": True, "short": False}
    calls: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return  # Never log private fixture messages or HTTP paths.

        def response(
            self, raw: bytes, content: str = "application/json", status: int = 200
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            route = "/" + self.path.split("/", 2)[-1] if self.path.startswith("/m") else self.path
            calls.append({"method": "GET", "route": route})
            if route == "/":
                self.response(b"Ollama is running", "text/plain")
                return
            values = {
                "/health": {},
                "/version": {"version": "controlled-chat-v0.89"},
                "/api/version": {"version": "0.35.1"},
                "/v1/models": {"data": [{"id": MODEL}]},
                "/api/tags": {"models": [{"name": MODEL}]},
                "/info": {"version": "3.3.7", "model_id": MODEL},
                "/get_server_info": {"version": "0.5.20"},
            }
            self.response(
                json.dumps(values.get(route, {})).encode(), status=200 if route in values else 404
            )

        def do_POST(self) -> None:
            route = "/" + self.path.split("/", 2)[-1] if self.path.startswith("/m") else self.path
            contact: dict[str, Any] = {"method": "POST", "route": route}
            contact["member"] = self.path.split("/", 2)[1] if self.path.startswith("/m") else None
            calls.append(contact)
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if route == "/api/show":
                self.response(b"{}")
                return
            backend = state["backend"]
            assert route == ("/api/chat" if backend == "ollama" else "/v1/chat/completions")
            assert value["model"] == MODEL and value["stream"] is True
            assert value["messages"] and all(
                set(m) == {"role", "content"} for m in value["messages"]
            )
            assert not {"prompt", "echo", "return_token_ids", "return_prompt_token_ids"} & set(
                value
            )
            if backend == "ollama":
                assert all(value[name] is False for name in ("think", "truncate", "shift"))
                cap = value["options"]["num_predict"]
                temperature = value["options"]["temperature"]
            else:
                assert value["n"] == 1 and value["stream_options"] == {"include_usage": True}
                cap = value["max_tokens"]
                temperature = value["temperature"]
            contact.update(
                {
                    "backend": backend,
                    "message_roles": [m["role"] for m in value["messages"]],
                    "message_hash": hashlib.sha256(
                        json.dumps(value["messages"], sort_keys=True).encode()
                    ).hexdigest(),
                    "cap": cap,
                    "temperature": temperature,
                }
            )
            self.response(
                frames(backend, cap - int(state["short"]), usage=state["usage"]),
                "application/x-ndjson" if backend == "ollama" else "text/event-stream",
            )

    listener = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    listener.daemon_threads = False
    thread = threading.Thread(target=listener.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{listener.server_port}", state, calls
    finally:
        listener.shutdown()
        listener.server_close()
        thread.join(JOIN_SECONDS)
        assert not thread.is_alive()


def accept(cwd: Path, env: dict) -> dict:
    from chimeraforge import api
    from chimeraforge.bench.trace_gate_inputs import load_trace
    from ci_installed_acceptance import run_cli

    directory = cwd / "chat-trace"
    directory.mkdir()
    source = directory / "messages.json"
    rows = workload()
    raw = (json.dumps(rows, ensure_ascii=False) + "\n").encode()
    source.write_bytes(raw)
    profiles = []
    rendered_chat = False
    with server() as (url, state, calls):
        for backend in ("vllm", "sglang", "tgi", "ollama"):
            state["backend"] = backend
            state["usage"] = True
            for usage in (True, False):
                state["usage"] = usage
                start = len(calls)
                out = directory / f"{backend}-{usage}.trace.json"
                report = json.loads(
                    run_cli(
                        [
                            "trace",
                            str(source),
                            "--model",
                            MODEL,
                            "--backend",
                            backend,
                            "--base-url",
                            url,
                            "--concurrency",
                            "2",
                            "--request-timeout",
                            "5",
                            "--trace-timeout",
                            "10",
                            "--out",
                            str(out),
                            "--json",
                        ],
                        cwd,
                        env,
                    )
                )
                assert report == json.loads(out.read_bytes()) == load_trace(out)["data"]
                assert report["execution"]["completed"] == len(rows)
                assert report["resource_cleanup"]["state"] == "completed"
                for item in report["requests"]:
                    assert item["descriptor"]["mode"] == "chat"
                    assert item["native"]["tokens_generated"] == (8 if usage else None)
                    assert item["native"]["prompt_tokens"] == (512 if usage else None)
                assert "PrivateChat89" not in json.dumps(report)
                if backend == "vllm" and usage:
                    rendered = api.render_trace_report(out, format="svg").content
                    text = run_cli(
                        [
                            "report",
                            "--kind",
                            "trace",
                            "--input",
                            str(out),
                            "--format",
                            "svg",
                            "--title",
                            "Trace diagnostics",
                        ],
                        cwd,
                        env,
                    )
                    assert text == rendered and "PrivateChat89" not in text
                    rendered_chat = True
                expected = {
                    hashlib.sha256(
                        json.dumps(r["messages"], sort_keys=True).encode()
                    ).hexdigest(): r
                    for r in rows
                }
                wire = [r for r in calls[start:] if "message_hash" in r]
                assert Counter(r["message_hash"] for r in wire) == Counter(expected.keys())
                assert all(
                    r["temperature"] == expected[r["message_hash"]]["temperature"] for r in wire
                )
                profiles.append(
                    {"backend": backend, "usage_present": usage, "completed": len(rows)}
                )
        state["backend"] = "vllm"
        state["usage"] = True
        saved = api.plan(
            api.PlanRequest(
                models=[MODEL],
                overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                hardware="RTX 4090 24GB",
                platform="linux",
                tensor_parallel=2,
                request_rate=128,
                prompt_tokens=512,
                latency_slo=10000,
                tpot_slo=None,
                quality_target=0,
                budget=1e8,
                allow_network=False,
            )
        )
        index = next(
            i
            for i, c in enumerate(saved.to_dict()["result"]["candidates"])
            if c["backend"] == "vllm" and c["quant"] == "FP16" and c["n_agents"] == REPLICAS
        )
        cap = saved.candidate(index).decode_tokens_per_req
        assert isinstance(cap, int) and cap > 0
        plan_path = directory / "native-plan.json"
        saved.save(plan_path)
        assert api.load_plan(plan_path).to_dict() == saved.to_dict()
        saved_rows = typed(workload(cap, 2))
        saved_receipt = asyncio.run(
            api.replay_plan_trace(
                plan_path,
                saved_rows,
                candidate_index=index,
                base_url=url,
                request_timeout=5,
                trace_timeout=10,
            )
        )
        saved_data = saved_receipt.to_dict()
        assert saved_data["native_trace"]["execution"]["completed"] == 2
        assert saved_data["binding"]["token_lengths"]["prompt_tokens"]["state"] == "matched"
        assert saved_data["binding"]["token_lengths"]["prompt_tokens"]["expected"] == 512
        fleet_rows = typed(workload(cap, 6))
        endpoints = tuple(api.FleetEndpoint(f"m{i}", f"{url}/m{i}") for i in range(REPLICAS))
        routes = [
            api.TraceRoute(r.request_id, f"m{i % REPLICAS}") for i, r in enumerate(fleet_rows)
        ]
        original = saved.to_dict()
        fleet_start = len(calls)
        receipt = asyncio.run(
            api.replay_fleet_trace(
                saved,
                fleet_rows,
                endpoints,
                routes,
                candidate_index=index,
                concurrency=2,
                request_timeout=5,
                trace_timeout=10,
            )
        )
        data = receipt.to_dict()
        assert data["native_trace"]["execution"]["completed"] == 6
        assert len(data["slots"]) == REPLICAS and api.load_fleet_trace(receipt).to_dict() == data
        assert saved.to_dict() == original
        routed = {
            hashlib.sha256(
                json.dumps([asdict(m) for m in row.messages], sort_keys=True).encode()
            ).hexdigest(): f"m{i % REPLICAS}"
            for i, row in enumerate(fleet_rows)
        }
        wire = [r for r in calls[fleet_start:] if "message_hash" in r]
        assert Counter(r["message_hash"] for r in wire) == Counter(routed.keys())
        assert all(r["member"] == routed[r["message_hash"]] for r in wire)
        before = len(calls)
        stopped = asyncio.Event()
        stopped.set()
        expanded = [
            api.ChatTraceRequest(str(i), (api.ChatMessage("user", "x"),) * 128, 1, 0, 0.0)
            for i in range(1024)
        ]
        try:
            asyncio.run(
                api.replay_trace(
                    expanded, model=MODEL, backend="vllm", base_url=url, stop_event=stopped
                )
            )
        except api.PlanError as exc:
            assert "byte" in str(exc)
        else:
            raise AssertionError("unreceivable descriptor expansion was not refused")
        assert len(calls) == before
        before = len(calls)
        bad = directory / "late-invalid.json"
        bad.write_text(
            json.dumps(
                [rows[0], {**rows[1], "messages": [{"role": "tool", "content": "PrivateChat89"}]}]
            ),
            encoding="utf-8",
        )
        run_cli(
            ["trace", str(bad), "--model", MODEL, "--backend", "vllm", "--base-url", url, "--json"],
            cwd,
            env,
            2,
        )
        assert len(calls) == before and source.read_bytes() == raw
        native_posts = sum("backend" in contact for contact in calls)
        assert native_posts == len(profiles) * len(rows) + len(saved_rows) + len(fleet_rows)
    return {
        "scope": "Actual native adapters/OSCLI against controlled HTTP; no engine inference.",
        "profiles": profiles,
        "native_chat_POSTs": native_posts,
        "native_plan_save_load_chat_completed": 2,
        "server_templated_prompt_count_matched": 512,
        "native_diagnostic_API_CLI_text_equal": rendered_chat,
        "oversized_stopped_receipt_refused_without_HTTP": True,
        "fleet": {"members": REPLICAS, "rows": 6, "native_completed": 6},
        "late_invalid_precontact": True,
        "wire_row_association": True,
        "per_member_routes_held": True,
        "source_bytes_held": True,
        "owned_HTTP_server_thread_joined": True,
        "owned_CLI_children_joined": True,
        "private_messages_and_outputs_absent": True,
    }


def accept_cpu(cwd: Path, env: dict, model: str, base_url: str, version: str) -> dict:
    from chimeraforge.bench.trace_gate_inputs import load_trace
    from ci_installed_acceptance import run_cli

    source = cwd / "native-cpu-chat.json"
    rows = workload(16, 1)
    rows[0]["messages"] = [
        {"role": "system", "content": "You answer concisely."},
        {"role": "user", "content": "Say hello."},
    ]
    raw = (json.dumps(rows) + "\n").encode()
    source.write_bytes(raw)
    report = json.loads(
        run_cli(
            [
                "trace",
                str(source),
                "--model",
                model,
                "--backend",
                "ollama",
                "--base-url",
                base_url,
                "--request-timeout",
                "60",
                "--trace-timeout",
                "90",
                "--json",
            ],
            cwd,
            env,
        )
    )
    assert load_trace(report)["data"] == report
    assert (
        report["execution"]["completed"] == 1 and report["resource_cleanup"]["state"] == "completed"
    )
    assert report["serving_after"]["version"] == version
    native = report["requests"][0]["native"]
    assert 0 < native["tokens_generated"] <= 16 and native["prompt_tokens"] > 0
    assert source.read_bytes() == raw
    return {
        "scope": "Actual pinned CPU Ollama native chat, not GPU/capacity/science qualification.",
        "completed": 1,
        "server_output_count": native["tokens_generated"],
        "server_templated_prompt_count": native["prompt_tokens"],
        "version": version,
        "source_bytes_held": True,
        "backend_closed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    if args.record.exists():
        parser.error("record target must be new; preserve dated historical runs")
    root = Path(__file__).resolve().parents[1]
    paths = {
        *root.glob("src/chimeraforge/bench/*.py"),
        *root.glob("src/chimeraforge/bench/backends/*.py"),
        *root.glob("src/chimeraforge/commands/trace*.py"),
        *root.glob("tests/test_chat*.py"),
        *[
            root / name
            for name in (
                "src/chimeraforge/api.py",
                "scripts/ci_chat_trace.py",
                "scripts/ci_installed_acceptance.py",
                "scripts/ci_cpu_serving.py",
                "scripts/ci_secure_active.py",
                "tests/test_ci_chat_trace.py",
                ".github/workflows/ci.yml",
                "pyproject.toml",
                "uv.lock",
                "server.json",
            )
        ],
    }

    def hashes() -> dict[str, str]:
        return {
            str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(paths)
        }

    before = hashes()
    from chimeraforge import __version__

    with tempfile.TemporaryDirectory(prefix="cf-chat-trace-") as folder:
        actual = accept(Path(folder), dict(os.environ))
    assert hashes() == before, "recording inputs changed during execution"
    actual.update(
        tool_version=__version__,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        source_hash_basis="Actual current RAW source files held before and after execution.",
        current_source_sha256=before,
        actual_inference_engine_executed=False,
        source_only=True,
    )
    with args.record.open("x", encoding="utf-8") as output:
        output.write(json.dumps(actual, indent=2) + "\n")
    print(
        json.dumps(
            {
                "profiles": len(actual["profiles"]),
                "native_chat_POSTs": actual["native_chat_POSTs"],
                "source_bytes_held": True,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
