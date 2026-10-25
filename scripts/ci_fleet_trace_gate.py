"""Regenerate synthetic fleet-gate controls; no traffic or inference is executed."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

MEMBERS = 3
REQUESTS = 6
CONCURRENCY = 3
PLAN_FIELDS = (
    "fingerprint",
    "raw_sha256",
    "candidate_index",
    "candidate_sha256",
    "served_model",
    "model_override",
)
CONTROLS = (
    "output_cap_tokens",
    "concurrency",
    "request_timeout_seconds",
    "trace_timeout_seconds",
    "cleanup_timeout_seconds",
    "targets",
    "replica_scope",
    "declared_original_replicas",
    "physical_independence",
)


def declared_policy(left: dict, right: dict, *, fixed: dict | None = None) -> dict:
    """Explicit controlled-fixture declaration, never a production policy inference API."""
    from chimeraforge.planner.replay import digest

    return {
        "trace": {
            "rules": {"latency_p95_ms": 0.1},
            "fixed_controls": fixed or {},
            "require_cache_evidence": True,
        },
        "population": {
            "original_replicas": len(left["endpoints"]),
            "endpoint_ids": [row["id"] for row in left["endpoints"]],
            "workload_sha256": left["workload"]["canonical_sha256"],
            "ordered_descriptors_sha256": digest(
                [row["descriptor"] for row in left["native_trace"]["requests"]]
            ),
            "routes_sha256": left["routes"]["canonical_sha256"],
            "minimum_requests_per_slot": 1,
            "controls": {key: left["controls"][key] for key in CONTROLS},
        },
        **{
            arm: {
                "plan": {key: value["plan"][key] for key in PLAN_FIELDS},
                "backend": value["controls"]["backend"],
                "endpoints": value["endpoints"],
            }
            for arm, value in (("baseline", left), ("candidate", right))
        },
    }


def synthetic(saved: Path, *, duration: float) -> dict:
    """Valid native schema with explicitly synthetic metadata, clocks and ownership counts."""
    from chimeraforge import api
    from chimeraforge.bench import trace
    from chimeraforge.bench.fleet_trace_inputs import prepare
    from chimeraforge.bench.fleet_trace_receipt import make_report
    from chimeraforge.bench.serving import safe_observation
    from chimeraforge.bench.trace_workload import TraceRequest

    data = api.load_plan(saved).to_dict()
    index = next(
        i
        for i, row in enumerate(data["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16" and row["n_agents"] == MEMBERS
    )
    candidate = data["result"]["candidates"][index]
    cap = candidate["decode_tokens_per_req"]
    assert cap > 1
    requests = [
        TraceRequest(f"fixture-{i}", "synthetic private prompt", cap, 0) for i in range(REQUESTS)
    ]
    endpoints = tuple(
        api.FleetEndpoint(f"member-{i}", f"http://member-{i}.invalid") for i in range(MEMBERS)
    )
    routes = [
        api.TraceRoute(row.request_id, endpoints[i % MEMBERS].id) for i, row in enumerate(requests)
    ]
    prepared = prepare(
        saved,
        requests,
        endpoints,
        routes,
        candidate_index=index,
        model=None,
        concurrency=CONCURRENCY,
        request_timeout=300,
        trace_timeout=600,
        cleanup_timeout=2,
        stop_event=None,
    )
    rows = trace._initial_rows(requests)
    for i, row in enumerate(rows):
        start = (i // CONCURRENCY) * duration
        row.update(
            {
                "state": "completed",
                "endpoint_id": routes[i].endpoint_id,
                "mean_tpot_basis": "client-first-to-last-content/(server-output-count-1)",
                "mean_tpot_ms": duration * 0.75 * 1000 / (cap - 1),
            }
        )
        row["times"].update(
            arrival_s=0,
            start_s=start,
            first_output_s=start + duration / 4,
            terminal_s=start + duration,
        )
        row["native"].update(
            tokens_generated=cap,
            prompt_tokens=data["inputs"]["prompt_tokens"],
            cached_prompt_tokens=0,
            eval_duration_ms=duration * 0.75 * 1000,
            throughput_tps=(cap - 1) / (duration * 0.75),
            ttft_basis="client-stream-first-content",
        )
    native = trace._report(
        requests,
        rows,
        workload=prepared.plan.workload,
        targets=prepared.plan.slos,
        model=prepared.plan.served_model,
        backend_name="vllm",
        base_url=None,
        concurrency=CONCURRENCY,
        request_timeout=300,
        trace_timeout=600,
        cleanup={"state": "completed"},
        observation={},
        stop_reason=None,
        error=None,
        elapsed=max(row["times"]["terminal_s"] for row in rows),
        origin=1000,
    )
    observation = {
        "backend": "vllm",
        "execution_engine": "vllm",
        "model": candidate["model"],
        "quant": candidate["quant"],
        "context_length": data["inputs"]["context_length"],
        "tensor_parallel": candidate["tensor_parallel"],
        "pipeline_parallel": candidate["pipeline_parallel"],
        "replicas": 1,
        "serving_data_parallel_size": 1,
        "version": "synthetic-gate-fixture",
        "model_spec": data["result"]["replay_context"]["model_specs"][candidate["model"]],
        "hardware": data["result"]["replay_context"]["hardware"]["effective"],
        "device": "gpu",
        "prefix_cache": False,
        "source": "synthetic fixture; not observed hardware",
    }
    observation = safe_observation(observation)
    resources = [
        {"before": copy.deepcopy(observation), "after": copy.deepcopy(observation), "error": None}
        for _ in endpoints
    ]
    tasks = 2 * MEMBERS + 2 * REQUESTS + 3
    cleanup = {
        "state": "completed",
        "budget_seconds": 2,
        "allowance_exceeded": False,
        "resources_closed": True,
        "close_errors": 0,
        "owned_backends": MEMBERS,
        "closed_backends": MEMBERS,
        "owned_tasks": tasks,
        "joined_tasks": tasks,
    }
    report = make_report(prepared, native, resources, cleanup)
    assert api.load_fleet_trace(report).to_dict() == report
    return report


def _project(
    cwd: Path,
    env: dict,
    left: dict,
    right: dict,
    *,
    label: str,
    wanted: int,
    fixed: dict | None = None,
) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge import api

    declared = declared_policy(left, right, fixed=fixed)
    inputs = [cwd / f"gate-{label}-{name}.json" for name in ("left", "right", "policy")]
    for path, value in zip(inputs, (left, right, declared)):
        path.write_text(json.dumps(value), encoding="utf-8")
    held = [path.read_bytes() for path in inputs]
    decision, junit = cwd / f"gate-{label}.json", cwd / f"gate-{label}.xml"
    direct = api.gate_fleet_traces(inputs[0], inputs[1], policy=inputs[2])
    api.write_fleet_trace_gate(direct, out=decision, junit=junit)
    args = [
        "gate",
        "--kind",
        "fleet-trace",
        "--baseline",
        str(inputs[0]),
        "--candidate",
        str(inputs[1]),
        "--policy",
        str(inputs[2]),
        "--out",
        str(decision),
        "--junit",
        str(junit),
        "--json",
    ]
    cli = json.loads(run_cli(args, cwd, env, wanted))
    # created_at/fingerprint vary per invocation; the finalized outcome/arithmetic do not.
    for key in (
        "exit_code",
        "outcome",
        "blockers",
        "known_breaches",
        "metrics",
        "population",
        "members",
    ):
        assert cli[key] == direct.to_dict()[key]
    assert direct.to_dict()["exit_code"] == wanted
    for arm, original in (("baseline", left), ("candidate", right)):
        assert direct.to_dict()["inputs"][arm]["slots"] == original["slots"]
        assert cli["inputs"][arm]["slots"] == original["slots"]
    assert json.loads(decision.read_bytes()) == cli
    xml = ET.parse(junit).getroot()
    assert int(xml.attrib["tests"]) == 2
    assert int(xml.attrib["failures"]) == int(wanted == 1)
    assert int(xml.attrib["errors"]) == (2 if wanted == 3 else 0)
    assert not xml.findall(".//skipped")
    assert all(path.read_bytes() == raw for path, raw in zip(inputs, held))
    return {
        "case": label,
        "api_exit": wanted,
        "cli_exit": cli["exit_code"],
        "junit_tests": 2,
        "junit_failures": int(xml.attrib["failures"]),
        "junit_errors": int(xml.attrib["errors"]),
        "known_breaches": cli["known_breaches"],
        "original_replicas": len(left["slots"]),
        "rows_per_arm": len(left["native_trace"]["requests"]),
        "blockers": cli["blockers"],
    }


def accept(cwd: Path, env: dict, saved: Path) -> dict:
    from ci_installed_acceptance import run_cli

    original = saved.read_bytes()
    left = synthetic(saved, duration=0.1)
    controls = [
        _project(
            cwd,
            env,
            left,
            synthetic(saved, duration=duration),
            label=label,
            wanted=wanted,
            fixed=fixed,
        )
        for label, duration, wanted, fixed in (
            ("pass", 0.09, 0, None),
            ("regression", 0.125, 1, None),
            ("inconclusive", 0.125, 3, {"version": "required-unavailable"}),
        )
    ]
    args = [
        "gate",
        "--kind",
        "fleet-trace",
        "--baseline",
        str(cwd / "gate-pass-left.json"),
        "--candidate",
        str(cwd / "gate-pass-right.json"),
        "--policy",
        str(cwd / "gate-pass-policy.json"),
        "--json",
    ]
    for options in (
        ("--out", cwd / "gate-pass-left.json"),
        ("--out", cwd / "same-output", "--junit", cwd / "same-output"),
    ):
        run_cli(args + [str(value) for value in options], cwd, env, 2)
    assert saved.read_bytes() == original
    return {
        "synthetic": True,
        "controls": controls,
        "input_bytes_unchanged": True,
        "scope": (
            "offline synthetic metadata/timing/ownership, genuine native original plan; "
            "not independent inference or GPU qualification"
        ),
    }


def accept_native(cwd: Path, env: dict, left: dict, right: dict) -> dict:
    """Consume the two unchanged native .79 invocations; no new inference or forced pass."""
    before = copy.deepcopy((left, right))
    result = _project(cwd, env, left, right, label="native-adverse", wanted=3)
    assert (left, right) == before
    assert any(
        "producer_execution_or_configuration_incomplete" in reason for reason in result["blockers"]
    )
    return result


def main() -> int:
    import argparse
    import os
    import tempfile
    from chimeraforge import __version__, api

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cf-fleet-gate-") as temporary:
        cwd = Path(temporary)
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
        saved = cwd / "saved.json"
        artifact.save(saved)
        result = accept(cwd, dict(os.environ), saved)
    root = Path(__file__).resolve().parents[1]
    files = [
        Path(__file__),
        *sorted((root / "src/chimeraforge/bench").glob("fleet_gate*.py")),
        root / "src/chimeraforge/bench/fleet_trace_gate.py",
        root / "src/chimeraforge/bench/fleet_trace_receipt.py",
        root / "src/chimeraforge/bench/trace_gate.py",
        root / "src/chimeraforge/api.py",
        root / "src/chimeraforge/commands/gate.py",
    ]
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "evidence": (
            "source API/CLI/JUnit synthetic controls; "
            "hosted installed/native acceptance is separate"
        ),
        "result": result,
        "source_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"controls": len(result["controls"]), "traffic": "none"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
