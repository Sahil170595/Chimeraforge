"""Installed CLI acceptance against explicit SSE protocol fixtures, not inference."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import threading

MODEL = "synthetic-protocol-model"
PRIVATE_OUTPUT = "private-completion-sentinel"
SERVER_JOIN_SECONDS = 5


def frames(
    backend: str, mode: str, *, output_tokens: int | None = None, prompt_tokens: int = 7
) -> bytes:
    def event(value: dict) -> bytes:
        return ("data: " + json.dumps(value) + "\n\n").encode()

    output = output_tokens if output_tokens is not None else 2 if mode == "overcap" else 1
    if backend == "tgi":
        token = {"id": 10, "text": PRIVATE_OUTPUT, "special": False}
        details = {
            "finish_reason": "length",
            "generated_tokens": output,
            "input_length": prompt_tokens,
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
                    "prompt_tokens": prompt_tokens,
                    "total_tokens": prompt_tokens + output,
                },
            }
        )
        + b"data: [DONE]\n\n"
    )


def validate_plan_trace(
    report: dict,
    saved: dict,
    index: int,
    workload: list[dict],
    raw: bytes,
    *,
    expected_code: int,
    served_model: str | None = None,
    plan_raw: bytes | None = None,
) -> None:
    """Validate the wrapper and its strict unchanged native child against frozen inputs."""
    from chimeraforge.bench.trace_gate_inputs import load_trace
    from chimeraforge.bench.trace_workload import TraceRequest, descriptor
    from chimeraforge.bench.serving_binding import BACKEND_WRAPPERS
    from chimeraforge.plan_check import identity
    from chimeraforge.planner.replay import digest

    assert report["kind"] == "chimeraforge.plan-trace"
    assert report["fingerprint"] == digest({k: v for k, v in report.items() if k != "fingerprint"})
    candidate = saved["result"]["candidates"][index]
    selected = report["plan"]
    assert selected["fingerprint"] == saved["fingerprint"] and selected["candidate_index"] == index
    assert selected["candidate"] == candidate and selected["candidate_sha256"] == digest(candidate)
    assert selected["identity"] == identity(candidate)
    if plan_raw is not None:
        assert selected["raw_sha256"] == hashlib.sha256(plan_raw).hexdigest()
    wanted_model = served_model or candidate["model"].removeprefix("ollama:")
    assert selected["served_model"] == wanted_model and selected["model_override"] == served_model
    assert report["workload"] == {
        "canonical_sha256": digest(workload),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
    native = report["native_trace"]
    assert load_trace(native)["data"] == native
    assert native["workload"] == {"canonical_sha256": digest(workload), "raw_sha256": None}
    descriptors = [descriptor(TraceRequest(**row)) for row in workload]
    assert report["ordered_descriptors"] == descriptors
    assert [row["descriptor"] for row in native["requests"]] == descriptors
    assert native["execution"]["planned"] == native["execution"]["completed"] == len(workload)
    assert native["exit_code"] == 0 and native["resource_cleanup"]["state"] == "completed"
    assert report["status"] == "completed" and report["exit_code"] == expected_code
    assert report["configuration_status"] == ("mismatch" if expected_code else "unverified")
    known_mismatch = any(
        row["state"] == "mismatch"
        for section in ("summary", "token_lengths")
        for row in report["binding"][section].values()
    )
    assert known_mismatch == bool(expected_code)
    assert native["model"] == wanted_model
    assert native["backend"] == BACKEND_WRAPPERS.get(candidate["backend"], candidate["backend"])
    assert report["controls"]["applied"]["backend"] == native["backend"]
    assert report["controls"]["applied"]["output_cap_tokens"] == candidate["decode_tokens_per_req"]
    assert report["controls"]["applied"]["concurrency"] == native["execution"]["concurrency"] == 1
    assert (
        report["controls"]["modeled_unapplied"]["context_length"]
        == saved["inputs"]["context_length"]
    )
    expected_targets = {
        "latency_ms": saved["inputs"]["latency_slo"],
        "first_output_ms": saved["inputs"]["ttft_slo"],
        "tpot_ms": saved["inputs"]["tpot_slo"],
    }
    assert native["targets"] == report["slo"]["targets"] == expected_targets
    joint_states = [row["slo"]["joint"] for row in native["requests"]]
    expected_slo = (
        "not_requested"
        if all(value is None for value in expected_targets.values())
        else "breach"
        if "breach" in joint_states
        else "unavailable"
        if any(state in ("unknown", "not_completed") for state in joint_states)
        else "observed_pass"
    )
    assert report["slo"]["state"] == expected_slo
    assert native["performance"]["gpu_qualification"] == "unverified"
    encoded = json.dumps(report)
    assert PRIVATE_OUTPUT not in encoded
    assert not any(row["prompt"] in encoded for row in workload)


def _accept_plan(
    cwd: Path, env: dict, plan_path: Path, selected: dict, contacts: list, base_url: str
) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge.api import load_plan

    original = plan_path.read_bytes()
    saved = load_plan(plan_path).to_dict()
    index = next(
        i for i, row in enumerate(saved["result"]["candidates"]) if row["backend"] == "vllm"
    )
    candidate = saved["result"]["candidates"][index]
    cap = candidate["decode_tokens_per_req"]
    assert cap > 1
    selected.update(
        backend="vllm",
        model=candidate["model"].removeprefix("ollama:"),
        cap=cap,
        prompt_tokens=saved["inputs"]["prompt_tokens"],
        output_tokens=cap,
    )
    workload = [
        {
            "request_id": "plan-protocol",
            "prompt": "private-prompt-sentinel-plan",
            "max_output_tokens": cap,
            "arrival_offset_s": 0,
        }
    ]
    selected["prompt"] = workload[0]["prompt"]
    raw = (json.dumps(workload, indent=2) + "\n").encode()
    source = cwd / "plan-trace-protocol-workload.json"
    source.write_bytes(raw)

    def arguments(path: Path) -> list[str]:
        return [
            "trace",
            str(path),
            "--from-plan",
            str(plan_path),
            "--candidate-index",
            str(index),
            "--base-url",
            base_url,
            "--request-timeout",
            "5",
            "--trace-timeout",
            "10",
            "--json",
        ]

    reports = []
    for mode, count, code in (("plan-complete", cap, 0), ("plan-short", cap - 1, 1)):
        selected.update(mode=mode, output_tokens=count)
        output = cwd / f"{mode}.json"
        report = json.loads(run_cli([*arguments(source), "--out", str(output)], cwd, env, code))
        assert json.loads(output.read_bytes()) == report
        validate_plan_trace(
            report, saved, index, workload, raw, expected_code=code, plan_raw=original
        )
        observed = report["native_trace"]["requests"][0]["native"]
        assert observed["tokens_generated"] == count
        assert report["binding"]["token_lengths"]["output_tokens"]["state"] == (
            "matched" if code == 0 else "mismatch"
        )
        reports.append(report)
    before = len(contacts)
    invalid = cwd / "plan-trace-invalid-cap.json"
    invalid.write_text(json.dumps([{**workload[0], "max_output_tokens": cap - 1}]))
    assert json.loads(run_cli(arguments(invalid), cwd, env, 2))["error"]
    for alias in (source, plan_path):
        assert json.loads(run_cli([*arguments(source), "--out", str(alias)], cwd, env, 2))["error"]
    assert len(contacts) == before, "invalid cap or output alias reached the fixture endpoint"
    assert source.read_bytes() == raw and plan_path.read_bytes() == original
    return {
        "complete": reports[0],
        "token_length_mismatch": reports[1],
        "invalid_cap_precontact": True,
        "output_alias_precontact": True,
        "source_bytes_unchanged": True,
        "modeled_platform": saved["result"]["platform"],
        "engine_execution": "unverified",
        "scope": (
            "modeled Linux candidate; synthetic protocol on the actual host, no engine inference"
        ),
    }


def accept(cwd: Path, env: dict, checkout: Path, *, plan_path: Path | None = None) -> dict:
    import chimeraforge
    from ci_installed_acceptance import assert_installed_origin, run_cli
    from chimeraforge.planner.replay import digest

    assert_installed_origin(chimeraforge.__file__, checkout)
    selected = {"backend": "vllm", "mode": "single"}
    calls: list[dict] = []
    contacts: list[str] = []
    plan_receipt = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            # Private fixture request bodies are never included in HTTP access logs.
            return

        def do_GET(self) -> None:
            contacts.append("GET " + self.path)
            model = selected.get("model", MODEL)
            values = {
                "/health": {},
                "/version": {"version": "synthetic-protocol"},
                "/server_info": {"version": "synthetic-protocol"},
                "/get_server_info": {"version": "synthetic-protocol"},
                "/info": {"version": "synthetic-protocol", "model_id": model},
                "/v1/models": {"data": [{"id": model}]},
            }
            raw = json.dumps(values.get(self.path, {})).encode()
            self.send_response(200 if self.path in values else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            contacts.append("POST " + self.path)
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            backend = selected["backend"]
            expected_path = "/generate_stream" if backend == "tgi" else "/v1/completions"
            assert self.path == expected_path
            assert self.headers["Accept-Encoding"] == "identity"
            if backend == "tgi":
                assert request["parameters"]["max_new_tokens"] == 1
                assert request["parameters"]["details"] is True
            else:
                assert request["max_tokens"] == selected.get("cap", 1) and request["n"] == 1
                assert request["model"] == selected.get("model", MODEL)
                if "prompt" in selected:
                    assert request["prompt"] == selected["prompt"]
                assert request["return_token_ids"] is True and request["echo"] is False
                assert request["stream_options"] == {"include_usage": True}
            calls.append({"backend": backend, "mode": selected["mode"]})
            raw = frames(
                backend,
                selected["mode"],
                output_tokens=selected.get("output_tokens"),
                prompt_tokens=selected.get("prompt_tokens", 7),
            )
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
        if plan_path is not None:
            plan_receipt = _accept_plan(
                cwd, env, plan_path, selected, contacts, f"http://127.0.0.1:{server.server_port}"
            )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(SERVER_JOIN_SECONDS)
        assert not worker.is_alive(), "fixture server failed to stop"
    assert len(calls) == len(backends) * len(outcomes) + (2 if plan_path is not None else 0)
    return {
        "evidence_class": "synthetic SSE protocol through installed CLI; no inference",
        "backends": backends,
        "outcomes": outcomes,
        "gpu_engine_execution": "unverified",
        "server_cleanup": "completed",
        **({"plan_bound_trace": plan_receipt} if plan_receipt is not None else {}),
    }
