"""Installed request-trace acceptance on the existing pinned CPU Ollama endpoint."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def validate(report: dict, workload: list[dict], raw: bytes, model: str, version: str) -> None:
    """Check actual byte/timing/count associations; require no machine-speed threshold."""
    from chimeraforge.planner.replay import digest

    value = dict(report)
    assert digest({k: v for k, v in value.items() if k != "fingerprint"}) == value["fingerprint"]
    assert report["workload"]["canonical_sha256"] == digest(workload)
    assert report["workload"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    execution = report["execution"]
    assert execution["planned"] == execution["attempted"] == execution["completed"] == len(workload)
    assert all(execution[key] == 0 for key in ("failed", "partial", "cancelled", "not_started"))
    assert report["exit_code"] == 0 and report["resource_cleanup"]["state"] == "completed"
    assert (
        report["serving_after"]["backend"] == "ollama"
        and report["serving_after"]["version"] == version
    )
    assert report["model"] == model and report["performance"]["gpu_qualification"] == "unverified"
    assert type(report["requests"]) is list and len(report["requests"]) == len(workload)
    ids = [row["descriptor"]["request_id"] for row in report["requests"]]
    assert ids == [row["request_id"] for row in workload] and len(set(ids)) == len(ids)
    for row, request in zip(report["requests"], workload):
        assert row["descriptor"]["request_id"] == request["request_id"]
        assert (
            row["descriptor"]["prompt_sha256"]
            == hashlib.sha256(request["prompt"].encode()).hexdigest()
        )
        assert row["descriptor"]["max_output_tokens"] == request["max_output_tokens"]
        times, timing, native = row["times"], row["timing"], row["native"]
        ordered = [
            times[name]
            for name in ("scheduled_s", "arrival_s", "start_s", "first_output_s", "terminal_s")
        ]
        assert all(type(value) in (int, float) and math.isfinite(value) for value in ordered)
        assert ordered == sorted(ordered) and times["scheduled_s"] == request["arrival_offset_s"], (
            ordered
        )
        assert timing["latency_ms"] == (times["terminal_s"] - times["scheduled_s"]) * 1000
        assert timing["first_output_ms"] == (times["first_output_s"] - times["scheduled_s"]) * 1000
        assert timing["client_queue_ms"] == (times["start_s"] - times["arrival_s"]) * 1000
        assert 0 < native["tokens_generated"] <= request["max_output_tokens"]
        assert row["mean_tpot_basis"] == "server-decode-duration/output-token-count"
        assert math.isclose(
            row["mean_tpot_ms"], native["eval_duration_ms"] / native["tokens_generated"]
        )
        assert native["ttft_basis"] == "server-prefill-duration"
        expected = {
            key: "not_requested"
            if target is None
            else "unknown"
            if timing[key] is None
            else "pass"
            if timing[key] <= target
            else "breach"
            for key, target in report["targets"].items()
        }
        active = [state for state in expected.values() if state != "not_requested"]
        joint = "breach" if "breach" in active else "unknown" if "unknown" in active else "pass"
        assert row["slo"] == {**expected, "joint": joint}
    horizon = max(execution["elapsed_seconds"], max(row["arrival_offset_s"] for row in workload))
    assert math.isfinite(execution["elapsed_seconds"]) and execution["elapsed_seconds"] > 0
    assert report["clock"]["origin"] is not None and horizon > 0
    assert report["goodput"]["horizon_seconds"] == horizon
    qualified = sum(row["slo"]["joint"] == "pass" for row in report["requests"])
    assert report["goodput"]["qualified_requests"] == qualified
    assert report["goodput"]["requests_per_second"] == qualified / horizon
    assert not any(request["prompt"] in json.dumps(report) for request in workload)


def accept(cwd: Path, env: dict, model: str, base_url: str, version: str) -> dict:
    from ci_installed_acceptance import run_cli

    workload = [
        {
            "request_id": "colors",
            "prompt": "List three primary colors.",
            "max_output_tokens": 8,
            "arrival_offset_s": 0,
        },
        {
            "request_id": "count",
            "prompt": "Write four counting words.",
            "max_output_tokens": 12,
            "arrival_offset_s": 0.005,
        },
        {
            "request_id": "hello",
            "prompt": "Say hello in a short sentence.",
            "max_output_tokens": 16,
            "arrival_offset_s": 0.01,
        },
    ]
    raw = json.dumps(workload).encode()
    source, output = cwd / "private-trace.json", cwd / "trace-receipt.json"
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
                "--latency-slo",
                "1",
                "--first-output-slo",
                "1",
                "--tpot-slo",
                "1",
                "--json",
                "--out",
                str(output),
            ],
            cwd,
            env,
        )
    )
    validate(report, workload, raw, model, version)
    assert report == json.loads(output.read_bytes()) and source.read_bytes() == raw
    invalid = json.loads(
        run_cli(
            [
                "trace",
                str(source),
                "--model",
                model,
                "--out",
                str(source),
                "--json",
            ],
            cwd,
            env,
            2,
        )
    )
    assert invalid["error"] and source.read_bytes() == raw
    return {
        "scope": "actual installed CPU workload; SLO outcomes retained without a speed gate",
        "trace_replay": report,
        "source_bytes_unchanged": True,
        "output_alias_refused": True,
    }
