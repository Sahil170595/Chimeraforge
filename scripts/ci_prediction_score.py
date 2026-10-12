"""Installed frozen-score outcomes from explicitly synthetic native protocol facts."""

from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import statistics


def seal(data: dict) -> dict:
    from chimeraforge.planner.replay import digest

    data["fingerprint"] = digest(
        {key: value for key, value in data.items() if key != "fingerprint"}
    )
    return data


def synthetic_plan(source: Path) -> tuple[dict, int]:
    """Declare synthetic complete geometry/prediction; do not label it fitted ground truth."""
    from chimeraforge import api

    data = api.load_plan(source).to_dict()
    index = next(
        i for i, row in enumerate(data["result"]["candidates"]) if row["backend"] == "ollama"
    )
    data["result"]["candidates"][index]["throughput_tps"] = 40.0
    for mapping in (data["result"]["specs"], data["result"]["replay_context"]["model_specs"]):
        for spec in mapping.values():
            spec["hidden_size"] = spec["hidden_size"] or 3072
            spec["vocab_size"] = spec["vocab_size"] or 128256
    return api.artifact_from_dict(seal(data)).to_dict(), index


def protocol_receipt(saved: dict, index: int, duration: float = 125.0) -> dict:
    """Synthetic capability-shaped metadata; no serving process or physical attestation."""
    from chimeraforge.bench.metrics import RunMetrics, aggregate_runs
    from chimeraforge.plan_check import identity

    candidate = saved["result"]["candidates"][index]
    context = saved["result"]["replay_context"]
    prompt, output = saved["inputs"]["prompt_tokens"], candidate["decode_tokens_per_req"]
    # Scale duration to retain the independent 32/20 tps oracle at any saved output length.
    duration = duration * output / 4
    samples = [
        RunMetrics(
            output,
            1000 * output / duration,
            2,
            duration + 2,
            2,
            duration,
            prompt,
            0,
            "server-prefill-duration",
        )
        for _ in range(3)
    ]
    observation = {
        "backend": "ollama",
        "version": "synthetic-protocol",
        "model": candidate["model"],
        "model_digest": "a" * 64,
        "quant": candidate["quant"],
        "context_length": saved["inputs"]["context_length"],
        "tensor_parallel": 1,
        "pipeline_parallel": 1,
        "replicas": candidate["n_agents"],
        "device": "gpu",
        "hardware": context["hardware"]["effective"],
        "model_spec": context["model_specs"][candidate["model"]],
        "prefix_cache": False,
        "source": "synthetic protocol only",
    }
    measurement = {
        "model": candidate["model"],
        "backend": "ollama",
        "quant": None,
        "workload": "single",
        "runs": 3,
        "context_length": saved["inputs"]["context_length"],
        "individual_runs": [asdict(row) for row in samples],
        "aggregate": asdict(aggregate_runs(samples)),
        "environment": {},
        "warnings": ["synthetic-private-sentinel"],
        "timestamp": "synthetic",
    }
    return seal(
        {
            "schema_version": 1,
            "kind": "chimeraforge.plan-benchmark",
            "created_at": "synthetic",
            "plan": {
                "fingerprint": saved["fingerprint"],
                "candidate_index": index,
                "identity": identity(candidate),
                "served_model": candidate["model"],
            },
            "measurement": measurement,
            "binding": {},
            "audit": {},
            "status": "completed",
            "configuration_status": "unverified",
            "exit_code": 0,
            "limits": "synthetic protocol only",
            "execution": {
                "request": {
                    "prompt_sha256": "b" * 64,
                    "prompt_characters": 5,
                    "options": {
                        "num_predict": output,
                        "num_ctx": saved["inputs"]["context_length"],
                        "private": "synthetic-private-sentinel",
                    },
                    "workload": "single",
                    "concurrency": 1,
                    "arrival_rate": None,
                    "requested_count": 3,
                },
                "serving_before": copy.deepcopy(observation),
                "serving_after": copy.deepcopy(observation),
                "requested_count": 3,
                "successful_count": 3,
                "failed_count": 0,
                "elapsed_seconds": 1.0,
                "individual_runs": measurement["individual_runs"],
            },
        }
    )


def validate(report: dict, expected: int, saved: dict, source: dict | None) -> None:
    """Independent count/duration oracle checks score, population and assurance boundaries."""
    from chimeraforge.planner.replay import digest

    assert report["kind"] == "chimeraforge.prediction-scorecard" and report["exit_code"] == expected
    assert report["fingerprint"] == digest(
        {key: value for key, value in report.items() if key != "fingerprint"}
    )
    assert report["plan"]["fingerprint"] == saved["fingerprint"]
    assert report["assurance"]["source_authentication"] == "unverified"
    assert report["assurance"]["physical_hardware"] == "unverified"
    assert report["assurance"]["actual_serving_modifiers"] == "unverified"
    assert "synthetic-private-sentinel" not in json.dumps(report)
    coverage = report["coverage"][0]
    if source is None:
        assert coverage["received"] == 0 and coverage["missing"] == 1
        assert report["rows"][0]["state"] == "missing"
        return
    assert coverage["received"] == 1 and coverage["missing"] == 0
    row = report["rows"][0]
    if expected in (0, 1):
        observed = statistics.mean(
            1000 * sample["tokens_generated"] / sample["eval_duration_ms"]
            for sample in source["measurement"]["individual_runs"]
        )
        prediction = saved["result"]["candidates"][source["plan"]["candidate_index"]][
            "throughput_tps"
        ]
        assert row["measured"] == observed and row["predicted"] == prediction
        assert row["relative_error"] == (prediction - observed) / observed
        assert row["within_band"] is (expected == 0) and coverage["comparable"] == 1
        assert report["worst_rows"] == [0]
    else:
        assert row["relative_error"] is None and coverage["comparable"] == 0


def accept(cwd: Path, env: dict, checkout: Path, source: Path) -> dict:
    """Exercise installed API/CLI outcomes without inference, network or new jobs."""
    import chimeraforge
    from ci_installed_acceptance import assert_installed_origin, run_cli

    assert_installed_origin(chimeraforge.__file__, checkout)
    saved, index = synthetic_plan(source)
    plan_path, policy_path, receipt_path, out = [
        cwd / name
        for name in (
            "score-synthetic-plan.json",
            "score-policy.json",
            "score-native.json",
            "scorecard.json",
        )
    ]
    plan_path.write_text(json.dumps(saved))
    policy = {
        "plan_fingerprint": saved["fingerprint"],
        "candidate_indices": [index],
        "expected_receipts_per_index": {str(index): 1},
        "relative_error_band": 0.25,
    }
    policy_path.write_text(json.dumps(policy))
    common = [
        "score",
        "--plan",
        str(plan_path),
        "--policy",
        str(policy_path),
        "--out",
        str(out),
        "--json",
    ]
    for code, duration in ((0, 125.0), (1, 200.0)):
        receipt = protocol_receipt(saved, index, duration)
        receipt_path.write_text(json.dumps(receipt))
        report = json.loads(run_cli([*common, "--benchmark", str(receipt_path)], cwd, env, code))
        validate(report, code, saved, receipt)
        assert json.loads(out.read_text()) == report
    unknown = protocol_receipt(saved, index)
    for phase in ("serving_before", "serving_after"):
        unknown["execution"][phase].update(device="cpu", hardware=None)
    unknown["measurement"]["environment"] = {
        "gpu": saved["result"]["replay_context"]["hardware"]["effective"]["name"]
    }
    receipt_path.write_text(json.dumps(seal(unknown)))
    validate(
        json.loads(run_cli([*common, "--benchmark", str(receipt_path)], cwd, env, 3)),
        3,
        saved,
        unknown,
    )
    validate(json.loads(run_cli(common, cwd, env, 3)), 3, saved, None)
    malformed = protocol_receipt(saved, index)
    malformed["measurement"]["aggregate"]["throughput_tps"]["mean"] = 999
    receipt_path.write_text(json.dumps(seal(malformed)))
    assert json.loads(run_cli([*common, "--benchmark", str(receipt_path)], cwd, env, 2))["error"]
    receipt_path.write_text(json.dumps(protocol_receipt(saved, index)))
    for protected in (plan_path, policy_path, receipt_path):
        before = protected.read_bytes()
        args = [
            "score",
            "--plan",
            str(plan_path),
            "--policy",
            str(policy_path),
            "--benchmark",
            str(receipt_path),
            "--out",
            str(protected),
            "--json",
        ]
        assert json.loads(run_cli(args, cwd, env, 2))["error"] and protected.read_bytes() == before
    return {
        "installed_cli_outcomes": [0, 1, 2, 3],
        "input_alias_protection": "passed",
        "evidence_class": "synthetic protocol declarations; not actual serving or GPU accuracy",
    }


def accept_cpu(cwd: Path, env: dict, plan: Path, index: int, receipt: Path) -> dict:
    """Consume the already executed real CPU receipt; never start another benchmark."""
    from ci_installed_acceptance import run_cli

    saved, raw = json.loads(plan.read_bytes()), receipt.read_bytes()
    native = json.loads(raw)
    policy = cwd / "cpu-score-policy.json"
    policy.write_text(
        json.dumps(
            {
                "plan_fingerprint": saved["fingerprint"],
                "candidate_indices": [index],
                "expected_receipts_per_index": {str(index): 1},
                "relative_error_band": 0.25,
            }
        )
    )
    report = json.loads(
        run_cli(
            [
                "score",
                "--plan",
                str(plan),
                "--policy",
                str(policy),
                "--benchmark",
                str(receipt),
                "--json",
            ],
            cwd,
            env,
            3,
        )
    )
    validate(report, 3, saved, native)
    assert native["execution"]["serving_after"]["device"] == "cpu"
    assert native["execution"]["serving_after"]["hardware"] is None
    assert report["inputs"]["receipts"][0]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["rows"][0]["state"] == "binding_mismatch"
    assert "hardware" in report["rows"][0]["reasons"]
    assert receipt.read_bytes() == raw
    return {
        "exit_code": 3,
        "received": 1,
        "comparable": 0,
        "evidence_class": "actual hosted CPU receipt; GPU prediction remains ineligible",
    }
