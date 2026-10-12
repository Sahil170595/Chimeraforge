"""Installed CLI acceptance against explicit SSE protocol fixtures, not inference."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

MODEL = "synthetic-protocol-model"
PRIVATE_OUTPUT = "private-completion-sentinel"
SERVER_JOIN_SECONDS = 5


def frames(backend: str, mode: str) -> bytes:
    def event(value: dict) -> bytes:
        return ("data: " + json.dumps(value) + "\n\n").encode()

    output = 2 if mode == "overcap" else 1
    if backend == "tgi":
        token = {"id": 10, "text": PRIVATE_OUTPUT, "special": False}
        details = {
            "finish_reason": "length",
            "generated_tokens": output,
            "input_length": 7,
        }
        if mode == "incomplete":
            return event({"token": token, "details": None})
        if mode == "abort":
            return event({"token": token}) + event({"error": PRIVATE_OUTPUT})
        if mode == "overcap":
            return event({"token": token}) + event({"token": token, "details": details})
        return event({"token": token, "details": details})
    choice = {
        "index": 0,
        "text": PRIVATE_OUTPUT,
        "token_ids": list(range(output)),
        "finish_reason": "length",
    }
    first = event({"choices": [choice]})
    if mode == "incomplete":
        return first
    if mode == "abort":
        return first + event({"error": PRIVATE_OUTPUT})
    return (
        first
        + event(
            {
                "choices": [],
                "usage": {
                    "completion_tokens": output,
                    "prompt_tokens": 7,
                    "total_tokens": 7 + output,
                },
            }
        )
        + b"data: [DONE]\n\n"
    )


def accept(cwd: Path, env: dict, checkout: Path) -> dict:
    import chimeraforge
    from ci_installed_acceptance import assert_installed_origin, run_cli
    from chimeraforge.planner.replay import digest

    assert_installed_origin(chimeraforge.__file__, checkout)
    selected = {"backend": "vllm", "mode": "single"}
    calls: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            # Private fixture request bodies are never included in HTTP access logs.
            return

        def do_GET(self) -> None:
            values = {
                "/health": {},
                "/version": {"version": "synthetic-protocol"},
                "/server_info": {"version": "synthetic-protocol"},
                "/get_server_info": {"version": "synthetic-protocol"},
                "/info": {"version": "synthetic-protocol", "model_id": MODEL},
                "/v1/models": {"data": [{"id": MODEL}]},
            }
            raw = json.dumps(values.get(self.path, {})).encode()
            self.send_response(200 if self.path in values else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            backend = selected["backend"]
            expected_path = "/generate_stream" if backend == "tgi" else "/v1/completions"
            assert self.path == expected_path
            assert self.headers["Accept-Encoding"] == "identity"
            if backend == "tgi":
                assert request["parameters"]["max_new_tokens"] == 1
                assert request["parameters"]["details"] is True
            else:
                assert request["max_tokens"] == 1 and request["n"] == 1
                assert request["return_token_ids"] is True and request["echo"] is False
                assert request["stream_options"] == {"include_usage": True}
            calls.append({"backend": backend, "mode": selected["mode"]})
            raw = frames(backend, selected["mode"])
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    backends = ["vllm", "sglang", "tgi"]
    outcomes = ["single", "overcap", "abort", "incomplete"]
    workload = [
        {
            "request_id": "protocol",
            "prompt": "private-prompt-sentinel",
            "max_output_tokens": 1,
            "arrival_offset_s": 0,
        }
    ]
    source = cwd / "native-protocol-workload.json"
    raw = json.dumps(workload).encode()
    source.write_bytes(raw)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        for backend in backends:
            for mode in outcomes:
                selected.update(backend=backend, mode=mode)
                output = cwd / f"native-{backend}-{mode}.json"
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
                            f"http://127.0.0.1:{server.server_port}",
                            "--request-timeout",
                            "5",
                            "--trace-timeout",
                            "10",
                            "--tpot-slo",
                            "1",
                            "--json",
                            "--out",
                            str(output),
                        ],
                        cwd,
                        env,
                        0 if mode == "single" else 1,
                    )
                )
                assert report == json.loads(output.read_bytes())
                assert report["fingerprint"] == digest(
                    {key: value for key, value in report.items() if key != "fingerprint"}
                )
                assert report["workload"]["canonical_sha256"] == digest(workload)
                assert source.read_bytes() == raw
                assert report["execution"]["planned"] == report["execution"]["attempted"] == 1
                assert report["resource_cleanup"]["state"] == "completed"
                assert report["performance"]["gpu_qualification"] == "unverified"
                row = report["requests"][0]
                if mode == "single":
                    assert row["state"] == "completed" and row["native"]["tokens_generated"] == 1
                    assert row["timing"]["first_output_ms"] is not None
                    assert row["mean_tpot_ms"] is None and row["slo"]["joint"] == "unknown"
                else:
                    assert row["state"] in ("partial", "failed")
                    assert row["native"]["tokens_generated"] is None
                    assert row["slo"]["joint"] == "not_completed"
                assert PRIVATE_OUTPUT not in json.dumps(report)
                assert workload[0]["prompt"] not in json.dumps(report)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(SERVER_JOIN_SECONDS)
        assert not worker.is_alive(), "fixture server failed to stop"
    assert len(calls) == len(backends) * len(outcomes)
    return {
        "evidence_class": "synthetic SSE protocol through installed CLI; no inference",
        "backends": backends,
        "outcomes": outcomes,
        "gpu_engine_execution": "unverified",
        "server_cleanup": "completed",
    }
