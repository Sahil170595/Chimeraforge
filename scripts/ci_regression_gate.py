"""Installed gate protocol acceptance; synthetic rates are not serving measurements."""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import statistics

CPU_GATE_RULES = {"completed_token_rate_tps": 0.05, "ttft_ms": 0.1}


def protocol_receipt(elapsed: float, ttft: float = 2.0) -> dict:
    """Produce a clearly synthetic, internally consistent native protocol fixture."""
    from chimeraforge.bench.metrics import BENCHMARK_WALL_BASIS, RunMetrics, aggregate_runs
    from chimeraforge.planner.replay import digest

    samples = [
        RunMetrics(4, 40, ttft, 102, ttft, 100, 8, 0, "server-prefill-duration") for _ in range(3)
    ]
    serving = {
        "backend": "ollama",
        "version": "synthetic-protocol",
        "model": "synthetic-protocol",
        "model_digest": "a" * 64,
        "quant": "Q4_K_M",
        "context_length": 2048,
        "device": "cpu",
        "prefix_cache": False,
    }
    measurement = {
        "model": "synthetic-protocol",
        "backend": "ollama",
        "quant": None,
        "workload": "single",
        "runs": 3,
        "context_length": 2048,
        "individual_runs": [asdict(row) for row in samples],
        "aggregate": asdict(aggregate_runs(samples)),
        "environment": {},
        "timestamp": "synthetic-protocol",
        "warnings": [],
    }
    result = {
        "schema_version": 1,
        "kind": "chimeraforge.plan-benchmark",
        "created_at": "synthetic-protocol",
        "plan": {},
        "measurement": measurement,
        "binding": {},
        "audit": {},
        "status": "completed",
        "configuration_status": "unverified",
        "exit_code": 0,
        "limits": "Synthetic protocol only",
        "execution": {
            "serving_before": copy.deepcopy(serving),
            "serving_after": copy.deepcopy(serving),
            "requested_count": 3,
            "successful_count": 3,
            "failed_count": 0,
            "elapsed_seconds": elapsed,
            "elapsed_seconds_basis": BENCHMARK_WALL_BASIS,
            "individual_runs": measurement["individual_runs"],
            "request": {
                "prompt_sha256": "b" * 64,
                "prompt_characters": 5,
                "options": {"num_predict": 4, "num_ctx": 2048},
                "workload": "single",
                "concurrency": 1,
                "arrival_rate": None,
                "requested_count": 3,
            },
        },
    }
    result["fingerprint"] = digest(result)
    return result


def validate(report: dict, expected: int, counts: tuple[int, int]) -> None:
    """Challenge receipt population, every requested rule and exact decision binding."""
    from chimeraforge.planner.replay import digest

    assert report["kind"] == "chimeraforge.regression-gate"
    assert report["fingerprint"] == digest(
        {key: value for key, value in report.items() if key != "fingerprint"}
    )
    assert report["exit_code"] == expected
    assert tuple(len(report["inputs"][arm]) for arm in ("baseline", "candidate")) == counts
    assert report["assurance"]["source_authentication"] == "unverified"
    assert report["assurance"]["independent_executions_verified"] is False
    if expected in (0, 1):
        assert len(report["pairs"]) == report["policy"]["expected_replicates"]
        assert not report["blockers"]
        assert all(
            set(pair["metrics"]) == set(report["policy"]["rules"]) for pair in report["pairs"]
        )


def accept(cwd: Path, env: dict, checkout: Path) -> dict:
    """Use actual installed CLI/schema/atomic writer for four protocol outcomes."""
    import chimeraforge
    from ci_installed_acceptance import assert_installed_origin, run_cli

    assert_installed_origin(chimeraforge.__file__, checkout)
    config = cwd / "regression-policy.json"
    config.write_text(
        json.dumps(
            {
                "rules": {"completed_token_rate_tps": 0.05, "ttft_ms": 0.1},
                "expected_replicates": 2,
                "fixed_controls": {"device": "cpu"},
            }
        )
    )
    paths = [
        cwd / name for name in ("gate-b0.json", "gate-b1.json", "gate-c0.json", "gate-c1.json")
    ]
    for path, elapsed in zip(paths, (1.0, 2.0, 0.9, 1.8)):
        path.write_text(json.dumps(protocol_receipt(elapsed)))
    original = [path.read_bytes() for path in paths]
    args = [
        "gate",
        "--policy",
        str(config),
        "--baseline",
        str(paths[0]),
        "--baseline",
        str(paths[1]),
        "--candidate",
        str(paths[2]),
        "--candidate",
        str(paths[3]),
        "--json",
    ]
    output = cwd / "regression-gate.json"
    passed = json.loads(run_cli([*args, "--out", str(output)], cwd, env))
    validate(passed, 0, (2, 2))
    assert json.loads(output.read_text()) == passed
    paths[3].write_text(json.dumps(protocol_receipt(1.8, ttft=3)))
    regressed = json.loads(run_cli(args, cwd, env, 1))
    validate(regressed, 1, (2, 2))
    assert regressed["pairs"][1]["metrics"]["ttft_ms"]["state"] == "regression"
    paths[3].write_bytes(original[3])
    short_args = args[: args.index("--candidate") + 2] + ["--json"]
    refused = json.loads(run_cli(short_args, cwd, env, 3))
    validate(refused, 3, (2, 1))
    malformed = json.loads(paths[3].read_text())
    malformed["measurement"]["aggregate"]["count"] = 99
    from chimeraforge.planner.replay import digest

    malformed["fingerprint"] = digest(
        {key: value for key, value in malformed.items() if key != "fingerprint"}
    )
    paths[3].write_text(json.dumps(malformed))
    error = json.loads(run_cli(args, cwd, env, 2))
    assert error.get("error")
    paths[3].write_bytes(original[3])
    for path in [*paths, config]:
        before = path.read_bytes()
        assert json.loads(run_cli([*args, "--out", str(path)], cwd, env, 2))["error"]
        assert path.read_bytes() == before
    assert [path.read_bytes() for path in paths] == original
    return {
        "evidence_class": "synthetic protocol; no independent execution or performance claim",
        "installed_cli_outcomes": [0, 1, 2, 3],
        "rules": sorted(passed["policy"]["rules"]),
        "expected_replicates": 2,
        "all_input_alias_guards": "passed",
        "passed_fingerprint": passed["fingerprint"],
        "regressed_fingerprint": regressed["fingerprint"],
    }


def _cpu_cache(samples: list[dict], before: dict, after: dict) -> dict:
    """Derive cache evidence from native counters, never an assumed cold state."""
    from chimeraforge.planner.replay import digest

    counts = [row["cached_prompt_tokens"] for row in samples]
    complete = all(value is not None for value in counts)
    disabled = before.get("prefix_cache") is False and after.get("prefix_cache") is False
    contradiction = disabled and any(value is not None and value > 0 for value in counts)
    return {
        "state": "mismatch" if contradiction else "known" if complete or disabled else "unknown",
        "counts_sha256": digest(sorted(counts)) if complete else None,
        "disabled_observed": disabled,
        "known_counts": sorted(value for value in counts if value is not None),
        "unknown_count": counts.count(None),
        "unknown_prompt_capacities": [
            row["prompt_tokens"] for row in samples if row["cached_prompt_tokens"] is None
        ],
        "basis": "observed per-request cached tokens"
        if complete
        else "observed disabled prefix cache"
        if disabled
        else "unavailable; not assumed cold",
    }


def validate_cpu(report: dict, originals: tuple[bytes, bytes], version: str, runs: int) -> dict:
    """Check this CPU policy's native facts and decision without a machine-speed gate."""
    from chimeraforge.bench.gate import FACTS, RegressionPolicy, _evidence_id, _fact
    from chimeraforge.bench.gate_inputs import SERIALIZATION_ROUNDOFF, load_receipt
    from chimeraforge.bench.metrics import BENCHMARK_WALL_BASIS
    from chimeraforge.bench.serving import safe_observation
    from chimeraforge.planner.replay import digest

    code = report["exit_code"]
    assert type(code) is int and code in (0, 1, 3)
    validate(report, code, (1, 1))
    controls = {"device": "cpu", "backend": "ollama", "version": version}
    rules = dict(CPU_GATE_RULES)
    assert report["policy"] == asdict(RegressionPolicy(rules=rules, fixed_controls=controls))
    assert len(report["pairs"]) == 1
    pair = report["pairs"][0]
    assert pair["index"] == 0 and set(pair["metrics"]) == set(rules)
    rows = [json.loads(raw) for raw in originals]
    phases, caches, native, values, workloads, identities = {}, {}, {}, {}, {}, []
    blockers = set()
    for arm, raw, row in zip(("baseline", "candidate"), originals, rows):
        assert row["fingerprint"] == digest({k: v for k, v in row.items() if k != "fingerprint"})
        execution, samples = row["execution"], row["measurement"]["individual_runs"]
        assert len(samples) == execution["requested_count"] == execution["successful_count"] == runs
        assert execution["failed_count"] == 0 and execution["individual_runs"] == samples
        assert all(
            type(sample["prompt_tokens"]) is int and sample["prompt_tokens"] > 0
            for sample in samples
        )
        assert all(
            type(sample["tokens_generated"]) is int and sample["tokens_generated"] > 0
            for sample in samples
        )
        held = load_receipt(row)
        identity = _evidence_id(held)
        identities.append(identity)
        assert report["inputs"][arm] == [
            {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "fingerprint": row["fingerprint"],
                "size_bytes": len(raw),
                "evidence_sha256": identity,
                "legacy": False,
            }
        ]
        before, after = (
            safe_observation(execution[key]) for key in ("serving_before", "serving_after")
        )
        phases[arm] = (before, after)
        caches[arm] = _cpu_cache(samples, before, after)
        assert pair["cache"][arm] == caches[arm]
        if caches[arm]["state"] == "unknown":
            blockers.add("cache_evidence_unavailable")
        if caches[arm]["state"] == "mismatch":
            blockers.add("cache_contradiction")
        native[arm] = {
            name: [sample[name] for sample in samples]
            for name in (
                "prompt_tokens",
                "cached_prompt_tokens",
                "tokens_generated",
            )
        }
        request = execution["request"]
        options = copy.deepcopy(request["options"])
        cap = options.pop("num_predict")
        assert type(cap) is int and cap > 0
        assert all(sample["tokens_generated"] <= cap for sample in samples)
        workloads[arm] = {
            "prompt_sha256": request["prompt_sha256"],
            "profile": request["workload"],
            "concurrency": request["concurrency"],
            "arrival_rate": request["arrival_rate"],
            "output_cap": cap,
            "options_sha256": digest(options),
            "requested_count": runs,
            "actual_lengths_sha256": digest(
                sorted(
                    zip(native[arm]["prompt_tokens"], native[arm]["tokens_generated"]),
                    key=lambda value: (str(value[0]), value[1]),
                )
            ),
        }
        assert pair["workload"][arm] == workloads[arm]
        elapsed = execution["elapsed_seconds"]
        assert (
            math.isfinite(elapsed)
            and elapsed > 0
            and execution["elapsed_seconds_basis"] == BENCHMARK_WALL_BASIS
        )
        rate = sum(native[arm]["tokens_generated"]) / elapsed
        ttft = statistics.mean(sample["ttft_ms"] for sample in samples)
        native_prefill = before.get("backend") == after.get("backend") == "ollama" and all(
            sample["ttft_basis"] == "server-prefill-duration" and sample["ttft_ms"] > 0
            for sample in samples
        )
        values[arm] = {
            "completed_token_rate_tps": rate,
            "ttft_ms": ttft if native_prefill else None,
        }
    assert pair["cache"] == caches
    assert set(pair["conditions"]) == FACTS
    unavailable = []
    for name, condition in pair["conditions"].items():
        observed = {arm: [_fact(phase, name) for phase in phases[arm]] for arm in phases}
        known = [value for phases in observed.values() for value in phases if value is not None]
        mismatch = (
            any(value != known[0] for value in known[1:])
            or name in controls
            and any(value != controls[name] for value in known)
        )
        missing = any(value is None for phases in observed.values() for value in phases)
        state = "mismatch" if mismatch else "unavailable" if missing else "matched"
        assert condition["observed"] == observed and condition["state"] == state
        assert condition["required"] is (name in controls) and condition["treatment"] is False
        assert condition["expected"] == (
            {arm: controls[name] for arm in phases} if name in controls else None
        )
        if mismatch or name in controls and missing:
            blockers.add("condition:" + name)
        if state == "unavailable":
            unavailable.append(name)
    assert pair["uncontrolled_or_unavailable_facts"] == sorted(unavailable)
    if workloads["baseline"] != workloads["candidate"]:
        blockers.add("workload_or_actual_lengths_changed")
    for left, right in (
        (caches["baseline"], caches["candidate"]),
        (caches["candidate"], caches["baseline"]),
    ):
        residual = sorted(
            (Counter(left["known_counts"]) - Counter(right["known_counts"])).elements()
        )
        capacity = sorted(
            0 if right["disabled_observed"] else value
            for value in right["unknown_prompt_capacities"]
        )
        if len(residual) > len(capacity) or any(
            value > cap for value, cap in zip(residual, capacity[len(capacity) - len(residual) :])
        ):
            blockers.add("observed_cache_hits_changed")
    regression = False
    for name, threshold in rules.items():
        metric = pair["metrics"][name]
        left, right = values["baseline"][name], values["candidate"][name]
        assert metric["baseline"] == left and metric["candidate"] == right
        basis = (
            BENCHMARK_WALL_BASIS
            if name == "completed_token_rate_tps"
            else "server-prefill-duration"
        )
        assert metric["baseline_basis"] == (basis if left is not None else None)
        assert metric["candidate_basis"] == (basis if right is not None else None)
        assert metric["max_regression_fraction"] == threshold
        if left is None or right is None:
            blockers.add("metric_basis_or_value_unavailable:" + name)
            assert metric["regression_fraction"] is None
        else:
            fraction = (
                (left - right) / left
                if name == "completed_token_rate_tps"
                else (right - left) / left
            )
            assert math.isclose(
                metric["regression_fraction"],
                fraction,
                rel_tol=SERIALIZATION_ROUNDOFF,
                abs_tol=SERIALIZATION_ROUNDOFF,
            )
            regression |= fraction > threshold
    assert pair["blockers"] == sorted(blockers)
    if identities[0] == identities[1]:
        blockers.add("duplicate_execution_payload")
    assert report["blockers"] == sorted(blockers)
    expected = 3 if blockers else 1 if regression else 0
    assert (
        code == expected
        and report["outcome"]
        == {0: "conditional_pass", 1: "regression", 3: "inconclusive"}[expected]
    )
    for name, metric in pair["metrics"].items():
        assert metric["state"] == (
            "inconclusive"
            if pair["blockers"]
            else "regression"
            if metric["regression_fraction"] > rules[name]
            else "pass"
        )
    return {
        "exit_code": code,
        "outcome": report["outcome"],
        "native_counts": native,
        "cache": caches,
        "blockers": report["blockers"],
        "native_metrics": pair["metrics"],
        "performance_threshold_qualification": "not asserted",
        "gpu_accuracy": "unverified",
    }


def accept_cpu(
    cwd: Path,
    env: dict,
    source: Path,
    candidate_index: int,
    baseline_path: Path,
    model: str,
    base_url: str,
    version: str,
    runs: int,
) -> dict:
    """Gate two actual installed executions without a shared-CPU performance threshold."""
    from ci_installed_acceptance import run_cli

    directory = cwd / "gate-real-candidate"
    candidate = json.loads(
        run_cli(
            [
                "bench",
                "--plan",
                str(source),
                "--candidate-index",
                str(candidate_index),
                "--runs",
                str(runs),
                "--base-url",
                base_url,
                "--output-dir",
                str(directory),
                "--json",
            ],
            cwd,
            env,
            1,
        )
    )
    (candidate_path,) = directory.glob("plan-bench_*.json")
    assert json.loads(candidate_path.read_text()) == candidate
    baseline = json.loads(baseline_path.read_text())
    assert baseline["plan"]["served_model"] == candidate["plan"]["served_model"] == model
    assert baseline["fingerprint"] != candidate["fingerprint"]
    for row in (baseline, candidate):
        execution = row["execution"]
        assert execution["requested_count"] == execution["successful_count"] == runs
        assert execution["failed_count"] == 0 and execution["elapsed_seconds"] > 0
        assert execution["serving_after"]["backend"] == "ollama"
        assert execution["serving_after"]["version"] == version
        assert execution["serving_after"]["device"] == "cpu"
        assert all(
            sample["prompt_tokens"] > 0 and sample["tokens_generated"] > 0
            for sample in row["measurement"]["individual_runs"]
        )
    policy = cwd / "gate-real-policy.json"
    policy.write_text(
        json.dumps(
            {
                "rules": CPU_GATE_RULES,
                "fixed_controls": {"device": "cpu", "backend": "ollama", "version": version},
            }
        )
    )
    args = [
        "gate",
        "--baseline",
        str(baseline_path),
        "--candidate",
        str(candidate_path),
        "--policy",
        str(policy),
        "--json",
    ]
    actual = json.loads(run_cli(args, cwd, env, (0, 1, 3)))
    originals = (baseline_path.read_bytes(), candidate_path.read_bytes())
    print(
        json.dumps(
            {
                "cpu_gate_native_evidence": {
                    "validation": "pending following native-derived oracle",
                    "reported_cache": actual["pairs"][0]["cache"],
                    "reported_blockers": actual["blockers"],
                    "reported_exit_code": actual["exit_code"],
                    "native_counts": {
                        arm: {
                            name: [sample[name] for sample in row["measurement"]["individual_runs"]]
                            for name in (
                                "prompt_tokens",
                                "cached_prompt_tokens",
                                "tokens_generated",
                            )
                        }
                        for arm, row in (("baseline", baseline), ("candidate", candidate))
                    },
                }
            },
            sort_keys=True,
        )
    )
    observed = validate_cpu(actual, originals, version, runs)
    pair = actual["pairs"][0]
    for arm, row in (("baseline", baseline), ("candidate", candidate)):
        native_tokens = sum(
            sample["tokens_generated"] for sample in row["measurement"]["individual_runs"]
        )
        assert (
            pair["metrics"]["completed_token_rate_tps"][arm]
            == native_tokens / row["execution"]["elapsed_seconds"]
        )
    original = [baseline_path.read_bytes(), candidate_path.read_bytes()]
    # Same-byte duplicate is a demonstrated receipt-integrity refusal, never a second execution.
    copied = json.loads(
        run_cli(
            [
                "gate",
                "--baseline",
                str(baseline_path),
                "--candidate",
                str(baseline_path),
                "--policy",
                str(policy),
                "--json",
            ],
            cwd,
            env,
            3,
        )
    )
    assert "duplicate_execution_payload" in copied["blockers"]
    assert original == [baseline_path.read_bytes(), candidate_path.read_bytes()]
    return {
        "evidence_class": "two actual installed CPU/Ollama benchmark executions",
        "successful_requests_per_execution": runs,
        "receipts": [baseline["fingerprint"], candidate["fingerprint"]],
        "gate_fingerprint": actual["fingerprint"],
        **observed,
        "metrics": sorted(pair["metrics"]),
        "copied_receipt_refused": True,
        "performance_threshold_qualification": "not asserted",
        "gpu_accuracy": "unverified",
    }
