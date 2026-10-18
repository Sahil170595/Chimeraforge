"""Installed request-trace acceptance on the existing pinned CPU Ollama endpoint."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def validate(
    report: dict, workload: list[dict], raw: bytes | None, model: str, version: str
) -> None:
    """Check actual byte/timing/count associations; require no machine-speed threshold."""
    from chimeraforge.planner.replay import digest

    value = dict(report)
    assert digest({k: v for k, v in value.items() if k != "fingerprint"}) == value["fingerprint"]
    assert report["workload"]["canonical_sha256"] == digest(workload)
    assert report["workload"]["raw_sha256"] == (
        hashlib.sha256(raw).hexdigest() if raw is not None else None
    )
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


def validate_campaign(
    report: dict, workload: list[dict], raw: bytes, model: str, version: str, *, complete: bool
) -> None:
    """Observe frozen bindings/full populations; never impose shared-host speed thresholds."""
    from chimeraforge.planner.replay import digest

    assert report["kind"] == "chimeraforge.trace-campaign"
    assert report["fingerprint"] == digest({k: v for k, v in report.items() if k != "fingerprint"})
    manifest = report["manifest"]
    assert manifest["fingerprint"] == digest(
        {k: v for k, v in manifest.items() if k != "fingerprint"}
    )
    assert manifest["workload"] == {
        "canonical_sha256": digest(workload),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
    assert manifest["population"] == {
        "replicates": 2,
        "requests_per_replicate": len(workload),
        "total_requests": 2 * len(workload),
    }
    assert manifest["controls"]["model"] == model and manifest["controls"]["backend"] == "ollama"
    assert manifest["policy"] == {
        "execution": "serial",
        "retries": 0,
        "warmup_executions": 0,
        "stop_after_first_incomplete_replicate": True,
    }
    descriptors = [
        {
            "request_id": row["request_id"],
            "prompt_sha256": hashlib.sha256(row["prompt"].encode()).hexdigest(),
            "prompt_bytes": len(row["prompt"].encode()),
            "max_output_tokens": row["max_output_tokens"],
            "arrival_offset_s": row["arrival_offset_s"],
        }
        for row in workload
    ]
    assert manifest["ordered_descriptors"] == descriptors
    assert len(report["replicas"]) == 2
    for index, replica in enumerate(report["replicas"]):
        assert (
            replica["index"] == index and replica["manifest_fingerprint"] == manifest["fingerprint"]
        )
        assert replica["workload_ref"] == manifest["workload"]["canonical_sha256"]
        if complete:
            assert replica["state"] == "completed" and replica["error"] is None
            assert 0 <= replica["start_s"] <= replica["end_s"]
            if index:
                assert report["replicas"][index - 1]["end_s"] <= replica["start_s"]
            validate(replica["receipt"], workload, None, model, version)
            assert [row["descriptor"] for row in replica["receipt"]["requests"]] == descriptors
        elif index == 0:
            assert replica["state"] == "incomplete"
            native = replica["receipt"]
            assert native["fingerprint"] == digest(
                {k: v for k, v in native.items() if k != "fingerprint"}
            )
            assert native["workload"] == {"canonical_sha256": digest(workload), "raw_sha256": None}
            assert native["exit_code"] == 1 and native["error"]["stage"] == "preflight"
            assert native["execution"]["not_started"] == len(workload)
            assert len(native["requests"]) == len(workload)
            assert native["resource_cleanup"]["state"] == "completed"
        else:
            assert replica["state"] == "not_started" and replica["receipt"] is None
            assert replica["start_s"] is replica["end_s"] is None
    assert report["exit_code"] == (0 if complete else 1)
    assert report["execution"]["completed"] == (2 if complete else 0)
    assert report["execution"]["not_started"] == (0 if complete else 1)
    assert report["assurance"]["independent_cold_executions"] == "unverified"
    assert not any(row["prompt"] in json.dumps(report) for row in workload)


def accept_campaign(cwd: Path, env: dict, model: str, base_url: str, version: str) -> dict:
    """Two short replicas on the existing model plus a no-inference missing-model refusal."""
    from ci_installed_acceptance import run_cli

    workload = [
        {
            "request_id": "campaign-colors",
            "prompt": "List three primary colors.",
            "max_output_tokens": 8,
            "arrival_offset_s": 0,
        }
    ]
    raw = json.dumps(workload).encode()
    source, output = cwd / "private-campaign.json", cwd / "campaign-receipt.json"
    source.write_bytes(raw)
    args = [
        "trace-campaign",
        str(source),
        "--backend",
        "ollama",
        "--base-url",
        base_url,
        "--replicates",
        "2",
        "--request-timeout",
        "60",
        "--trace-timeout",
        "90",
        "--campaign-timeout",
        "180",
        "--latency-slo",
        "1",
        "--json",
    ]
    report = json.loads(run_cli([*args, "--model", model, "--out", str(output)], cwd, env))
    validate_campaign(report, workload, raw, model, version, complete=True)
    assert json.loads(output.read_bytes()) == report and source.read_bytes() == raw
    missing_model = "ci-missing-trace-campaign-model"
    missing = json.loads(run_cli([*args, "--model", missing_model], cwd, env, 1))
    validate_campaign(missing, workload, raw, missing_model, version, complete=False)
    from chimeraforge import api

    policy = api.TraceGatePolicy(rules={"latency_p95_ms": 0.1}, expected_replicates=2)
    copied_gate = api.gate_trace_campaigns(report, report, policy=policy).to_dict()
    assert copied_gate["exit_code"] == 3
    assert "duplicate_execution_payload" in copied_gate["blockers"]
    incomplete_gate = api.gate_trace_campaigns(report, missing, policy=policy).to_dict()
    assert incomplete_gate["exit_code"] == 3 and len(incomplete_gate["pairs"]) == 2
    assert [slot["state"] for slot in incomplete_gate["inputs"]["candidate"]["replicas"]] == [
        "incomplete",
        "not_started",
    ]
    return {
        "scope": (
            "actual installed serial CPU campaign; no cold/independence or speed qualification"
        ),
        "trace_campaign": report,
        "missing_model_campaign": missing,
        "campaign_gate_copied_actual_evidence": copied_gate,
        "campaign_gate_incomplete_actual_evidence": incomplete_gate,
        "source_bytes_unchanged": True,
    }


def validate_plan(
    report: dict,
    saved: dict,
    workload: list[dict],
    raw: bytes,
    model: str,
    version: str,
    *,
    plan_raw: bytes | None = None,
) -> None:
    """A completed CPU replay must retain the known modeled-GPU mismatch."""
    from ci_native_stream import validate_plan_trace

    index = next(
        i
        for i, candidate in enumerate(saved["result"]["candidates"])
        if candidate["backend"] == "ollama" and candidate["quant"] == "Q4_K_M"
    )
    validate_plan_trace(
        report,
        saved,
        index,
        workload,
        raw,
        expected_code=1,
        served_model=model,
        plan_raw=plan_raw,
    )
    native = report["native_trace"]
    assert native["backend"] == "ollama"
    assert native["serving_after"]["device"] == "cpu"
    assert native["serving_after"]["version"] == version
    assert report["binding"]["summary"]["hardware"]["state"] == "mismatch"
    assert report["binding"]["summary"]["hardware"]["observed"] == {"device": "cpu"}
    for request in native["requests"]:
        count = request["native"]["tokens_generated"]
        assert type(count) is int and 0 <= count <= request["descriptor"]["max_output_tokens"]
    assert report["slo"]["state"] == "not_requested"


def accept_plan(cwd: Path, env: dict, model: str, base_url: str, version: str) -> dict:
    """One short request on the already-loaded endpoint; no pulls or extra serving job."""
    from ci_installed_acceptance import run_cli

    plan_path = cwd / "plan-trace-cpu-plan.json"
    run_cli(
        [
            "plan",
            "--model",
            f"ollama:{model}",
            "--ollama-url",
            base_url,
            "--hardware",
            "RTX 4080 12GB",
            "--quality-target",
            "0",
            "--budget",
            "100000",
            "--request-rate",
            "0.01",
            "--avg-tokens",
            "4",
            "--prompt-tokens",
            "8",
            "--save",
            str(plan_path),
            "--json",
        ],
        cwd,
        env,
    )
    original = plan_path.read_bytes()
    saved = json.loads(original)
    chosen = next(
        i
        for i, candidate in enumerate(saved["result"]["candidates"])
        if candidate["backend"] == "ollama" and candidate["quant"] == "Q4_K_M"
    )
    cap = saved["result"]["candidates"][chosen]["decode_tokens_per_req"]
    assert cap == 4
    workload = [
        {
            "request_id": "plan-cpu-colors",
            "prompt": "List three primary colors.",
            "max_output_tokens": cap,
            "arrival_offset_s": 0,
        }
    ]
    raw = (json.dumps(workload, indent=2) + "\n").encode()
    source, output = cwd / "plan-trace-cpu-workload.json", cwd / "plan-trace-cpu-receipt.json"
    source.write_bytes(raw)
    report = json.loads(
        run_cli(
            [
                "trace",
                str(source),
                "--from-plan",
                str(plan_path),
                "--candidate-index",
                str(chosen),
                "--model",
                model,
                "--base-url",
                base_url,
                "--request-timeout",
                "60",
                "--trace-timeout",
                "90",
                "--out",
                str(output),
                "--json",
            ],
            cwd,
            env,
            1,
        )
    )
    validate_plan(report, saved, workload, raw, model, version, plan_raw=original)
    assert report == json.loads(output.read_bytes())
    assert plan_path.read_bytes() == original and source.read_bytes() == raw
    return {
        "scope": (
            "actual installed CPU plan-bound replay; modeled GPU remains mismatched/unqualified"
        ),
        "receipt": report,
        "source_bytes_unchanged": True,
        "extra_weight_downloads": 0,
    }


def accept(
    cwd: Path, env: dict, model: str, base_url: str, version: str, *, plan_replay: bool = False
) -> dict:
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
    policy = cwd / "cpu-trace-gate-policy.json"
    policy.write_text(json.dumps({"rules": {"goodput_rps": 0.1}}))
    duplicate = json.loads(
        run_cli(
            [
                "gate",
                "--kind",
                "trace",
                "--baseline",
                str(output),
                "--candidate",
                str(output),
                "--policy",
                str(policy),
                "--json",
            ],
            cwd,
            env,
            3,
        )
    )
    assert "duplicate_execution_payload" in duplicate["blockers"]
    return {
        "scope": "actual installed CPU workload; SLO outcomes retained without a speed gate",
        "trace_replay": report,
        "source_bytes_unchanged": True,
        "output_alias_refused": True,
        "trace_gate_duplicate_execution": duplicate,
        "serial_campaign": accept_campaign(cwd, env, model, base_url, version),
        **(
            {"plan_bound_trace": accept_plan(cwd, env, model, base_url, version)}
            if plan_replay
            else {}
        ),
    }
