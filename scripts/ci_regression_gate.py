"""Installed gate protocol acceptance; synthetic rates are not serving measurements."""

from __future__ import annotations

import copy
from dataclasses import asdict
import json
from pathlib import Path


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
                "rules": {"completed_token_rate_tps": 0.05, "ttft_ms": 0.1},
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
    actual = json.loads(run_cli(args, cwd, env, 3))
    validate(actual, 3, (1, 1))
    pair = actual["pairs"][0]
    assert pair["cache"]["baseline"]["state"] == pair["cache"]["candidate"]["state"] == "unknown"
    assert "cache_evidence_unavailable" in actual["blockers"]
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
        "exit_code": 3,
        "cause": "required cache evidence unavailable; additional native limitations retained",
        "metrics": sorted(pair["metrics"]),
        "copied_receipt_refused": True,
        "performance_threshold_qualification": "not asserted",
        "gpu_accuracy": "unverified",
    }
