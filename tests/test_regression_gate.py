"""Conditional gates consume complete native receipts, not persisted qualification claims."""

import copy
from dataclasses import asdict
import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.bench.metrics import RunMetrics, aggregate_runs
from chimeraforge.planner.replay import digest


def seal(data):
    data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    return data


def receipt(*, elapsed=1.0, rate=40.0, ttft=2.0, token_count=4, backend="ollama", serial=0):
    """Synthetic protocol receipt; these values are not independent serving executions."""
    rows = [
        RunMetrics(
            token_count,
            rate,
            ttft,
            102.0,
            max(ttft, 0),
            100.0,
            prompt_tokens=8,
            cached_prompt_tokens=0,
            ttft_basis="server-prefill-duration",
        )
        for _ in range(3)
    ]
    serving = {
        "backend": backend,
        "version": "0.35.1",
        "model": "synthetic",
        "model_digest": "a" * 64,
        "quant": "Q4_K_M",
        "context_length": 2048,
        "device": "cpu",
        "prefix_cache": False,
    }
    measurement = {
        "model": "synthetic",
        "backend": backend,
        "quant": None,
        "workload": "single",
        "runs": 3,
        "context_length": 2048,
        "individual_runs": [asdict(r) for r in rows],
        "aggregate": asdict(aggregate_runs(rows)),
        "environment": {},
        "timestamp": str(serial),
        "warnings": [],
    }
    return seal(
        {
            "schema_version": 1,
            "kind": "chimeraforge.plan-benchmark",
            "created_at": str(serial),
            "plan": {},
            "measurement": measurement,
            "execution": {
                "request": {
                    "prompt_sha256": "b" * 64,
                    "prompt_characters": 5,
                    "options": {"num_predict": 4, "num_ctx": 2048},
                    "workload": "single",
                    "concurrency": 1,
                    "arrival_rate": None,
                    "requested_count": 3,
                },
                "serving_before": copy.deepcopy(serving),
                "serving_after": copy.deepcopy(serving),
                "requested_count": 3,
                "successful_count": 3,
                "failed_count": 0,
                "elapsed_seconds": elapsed,
                "elapsed_seconds_basis": "client-workload-wall; preflight and metadata excluded",
                "individual_runs": measurement["individual_runs"],
            },
            "binding": {},
            "audit": {},
            "status": "completed",
            "configuration_status": "unverified",
            "exit_code": 0,
            "limits": "",
        }
    )


def policy(**kwargs):
    return api.RegressionPolicy(
        rules={"completed_token_rate_tps": 0.05}, expected_replicates=1, **kwargs
    )


def gate(baseline=None, candidate=None, chosen=None):
    return api.gate_benchmarks(
        [baseline or receipt()], [candidate or receipt(elapsed=0.9)], policy=chosen or policy()
    ).to_dict()


def test_gate_recomputes_wall_metric_and_returns_defensive_receipt():
    left, right = receipt(), receipt(elapsed=0.9)
    original = copy.deepcopy((left, right))
    result = api.gate_benchmarks([left], [right], policy=policy(fixed_controls={"device": "cpu"}))
    report = result.to_dict()
    assert report["exit_code"] == 0 and report["outcome"] == "conditional_pass"
    metric = report["pairs"][0]["metrics"]["completed_token_rate_tps"]
    assert metric["baseline"] == 12 and metric["candidate"] == pytest.approx(12 / 0.9)
    assert metric["unit"] == "tokens/second" and metric["state"] == "pass"
    report["pairs"].clear()
    assert result.to_dict()["pairs"] and (left, right) == original
    assert result.to_dict()["assurance"]["independent_executions_verified"] is False


def test_joint_rules_do_not_hide_latency_regression_behind_throughput_gain():
    result = gate(
        candidate=receipt(elapsed=0.8, ttft=3),
        chosen=api.RegressionPolicy(rules={"completed_token_rate_tps": 0.05, "ttft_ms": 0.1}),
    )
    assert result["exit_code"] == 1
    assert result["pairs"][0]["metrics"]["ttft_ms"]["state"] == "regression"


def test_every_ordered_pair_is_retained_and_a_bad_pair_cannot_be_averaged_away():
    chosen = api.RegressionPolicy(rules={"completed_token_rate_tps": 0.05}, expected_replicates=2)
    result = api.gate_benchmarks(
        [receipt(), receipt(elapsed=2)], [receipt(elapsed=0.4), receipt(elapsed=3)], policy=chosen
    ).to_dict()
    assert result["exit_code"] == 1 and len(result["pairs"]) == 2
    assert result["pairs"][1]["metrics"]["completed_token_rate_tps"]["state"] == "regression"


def test_declared_replicates_cannot_be_truncated():
    chosen = api.RegressionPolicy(rules={"decode_tps": 0.05}, expected_replicates=3)
    result = api.gate_benchmarks(
        [receipt(), receipt(elapsed=2)], [receipt(elapsed=0.9), receipt(elapsed=1.9)], policy=chosen
    ).to_dict()
    assert result["exit_code"] == 3 and "replicate_population" in result["blockers"]


@pytest.mark.parametrize("field,value", [("device", None), ("device", "gpu"), ("version", "other")])
def test_required_controls_are_observed_before_and_after(field, value):
    row = receipt(elapsed=0.9)
    row["execution"]["serving_before"][field] = value
    result = gate(
        candidate=seal(row), chosen=policy(fixed_controls={"device": "cpu", "version": "0.35.1"})
    )
    assert result["exit_code"] == 3


def test_backend_change_is_intentional_only_when_both_arm_treatments_are_declared():
    row = receipt(elapsed=0.9, backend="vllm")
    assert gate(candidate=row)["exit_code"] == 3
    chosen = policy(
        baseline_treatment={"backend": "ollama"}, candidate_treatment={"backend": "vllm"}
    )
    assert gate(candidate=row, chosen=chosen)["exit_code"] == 0
    row["execution"]["serving_before"]["backend"] = "ollama"
    assert gate(candidate=seal(row), chosen=chosen)["exit_code"] == 3


@pytest.mark.parametrize(
    "mutator",
    [
        lambda r: r["execution"]["request"].update(prompt_sha256="c" * 64),
        lambda r: (
            r["execution"]["request"].update(workload="batch", concurrency=2),
            r["measurement"].update(workload="batch"),
        ),
        lambda r: r["execution"]["request"]["options"].update(num_predict=5),
        lambda r: r["execution"]["individual_runs"][0].update(prompt_tokens=None),
        lambda r: (
            r["execution"]["serving_before"].update(prefix_cache=None),
            r["execution"]["serving_after"].update(prefix_cache=None),
            [
                sample.update(cached_prompt_tokens=None)
                for sample in r["execution"]["individual_runs"]
            ],
        ),
        lambda r: r["execution"]["serving_after"].update(prefix_cache=True),
    ],
)
def test_missing_or_different_workload_length_and_cache_cannot_pass(mutator):
    row = receipt(elapsed=0.9)
    mutator(row)
    # Both stored raw lists describe the same consumed sample population.
    row["measurement"]["individual_runs"] = row["execution"]["individual_runs"]
    assert gate(candidate=seal(row))["exit_code"] == 3


def test_partial_success_does_not_qualify_survivor_metrics():
    row = receipt(elapsed=0.9)
    row["execution"].update(requested_count=4, failed_count=1)
    row["execution"]["request"]["requested_count"] = row["measurement"]["runs"] = 4
    row["status"] = "partial"
    assert gate(candidate=seal(row))["exit_code"] == 3


@pytest.mark.parametrize("kind", ["decode_tps", "ttft_ms", "request_duration_ms"])
def test_native_bases_are_not_pooled_across_intentional_backend_changes(kind):
    row = receipt(elapsed=0.9, backend="vllm")
    chosen = api.RegressionPolicy(
        rules={kind: 0.05},
        baseline_treatment={"backend": "ollama"},
        candidate_treatment={"backend": "vllm"},
    )
    assert gate(candidate=row, chosen=chosen)["exit_code"] == 3


def test_unknown_ttft_sentinel_never_becomes_negative_improvement():
    assert (
        gate(
            candidate=receipt(elapsed=0.9, ttft=-1),
            chosen=api.RegressionPolicy(rules={"ttft_ms": 0.05}),
        )["exit_code"]
        == 3
    )


def test_duplicates_detected_even_if_created_clock_and_fingerprint_are_changed():
    assert gate(candidate=receipt(serial=19))["exit_code"] == 3


def test_legacy_plain_benchmark_remains_inconclusive():
    result = api.gate_benchmarks(
        [receipt()["measurement"]], [receipt(elapsed=0.9)["measurement"]], policy=policy()
    ).to_dict()
    assert result["exit_code"] == 3 and "legacy_evidence_unavailable" in result["blockers"]


def test_real_ollama_missing_cache_shape_has_explicit_conditional_opt_out():
    left, right = receipt(), receipt(elapsed=0.9)
    for row in (left, right):
        for phase in ("serving_before", "serving_after"):
            row["execution"][phase]["prefix_cache"] = None
        for sample in row["execution"]["individual_runs"]:
            sample["cached_prompt_tokens"] = None
        seal(row)
    assert gate(left, right)["exit_code"] == 3
    report = gate(left, right, policy(require_cache_evidence=False))
    assert report["exit_code"] == 0
    assert report["pairs"][0]["cache"]["baseline"]["state"] == "unknown"
    assert report["assurance"]["cache_evidence_required"] is False
    assert (
        gate(
            left,
            right,
            policy(require_cache_evidence=False, fixed_controls={"prefix_cache": False}),
        )["exit_code"]
        == 3
    )
    right["execution"]["serving_before"]["prefix_cache"] = False
    right["execution"]["serving_after"]["prefix_cache"] = True
    assert gate(left, seal(right), policy(require_cache_evidence=False))["exit_code"] == 3


@pytest.mark.parametrize(
    "mutator",
    [
        lambda r: r["measurement"]["aggregate"]["throughput_tps"].update(mean=999),
        lambda r: r["execution"].update(successful_count=True),
        lambda r: r["measurement"]["individual_runs"][0].update(tokens_generated=True),
        lambda r: r["execution"].update(failed_count=7),
    ],
)
def test_resigned_inconsistent_native_receipts_are_malformed(mutator):
    row = receipt(elapsed=0.9)
    mutator(row)
    with pytest.raises(api.PlanError):
        gate(candidate=seal(row))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rules": {}},
        {"rules": {"unknown": 0.1}},
        {"rules": {"decode_tps": True}},
        {"rules": {"decode_tps": -1}},
        {"rules": {"decode_tps": float("nan")}},
        {"rules": {"decode_tps": 0.1}, "expected_replicates": True},
        {"rules": {"decode_tps": 0.1}, "pairing": "first"},
        {"rules": {"decode_tps": 0.1}, "fixed_controls": {"secret": "token"}},
        {"rules": {"decode_tps": 0.1}, "baseline_treatment": {"backend": "ollama"}},
    ],
)
def test_invalid_policy_refused(kwargs):
    with pytest.raises(api.PlanError):
        gate(chosen=api.RegressionPolicy(**kwargs))


def test_privacy_ignores_audit_warnings_and_private_option_payloads():
    left, right = receipt(), receipt(elapsed=0.9)
    for row in (left, right):
        row["audit"] = {"private": "prompt completion token"}
        row["measurement"]["warnings"] = ["prompt completion token"]
        row["execution"]["request"]["options"]["private"] = "prompt completion token"
        seal(row)
    assert "prompt completion token" not in json.dumps(gate(left, right))


def test_cli_atomic_output_protects_all_inputs_and_policy(tmp_path):
    from chimeraforge.cli import app

    baseline, candidate, config = [
        tmp_path / name for name in ("base.json", "candidate.json", "policy.json")
    ]
    baseline.write_text(json.dumps(receipt()))
    candidate.write_text(json.dumps(receipt(elapsed=0.9)))
    config.write_text(json.dumps({"rules": {"completed_token_rate_tps": 0.05}}))
    args = [
        "gate",
        "--baseline",
        str(baseline),
        "--candidate",
        str(candidate),
        "--policy",
        str(config),
        "--json",
    ]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    for path in (baseline, candidate, config):
        before = path.read_bytes()
        refused = CliRunner().invoke(app, [*args, "--out", str(path)])
        assert refused.exit_code == 2 and path.read_bytes() == before
    out = tmp_path / "gate.json"
    result = CliRunner().invoke(app, [*args, "--out", str(out)])
    assert result.exit_code == 0 and json.loads(out.read_text()) == json.loads(result.output)


def test_known_cache_counts_change_is_not_waived_by_unknown_opt_out():
    left, right = receipt(), receipt(elapsed=0.9)
    for row in (left, right):
        for phase in ("serving_before", "serving_after"):
            row["execution"][phase]["prefix_cache"] = True
    for sample in right["execution"]["individual_runs"]:
        sample["cached_prompt_tokens"] = 1
    assert gate(seal(left), seal(right), policy(require_cache_evidence=False))["exit_code"] == 3


def test_same_supported_stream_basis_can_compare_intentional_backend_treatments():
    left, right = receipt(backend="vllm"), receipt(elapsed=0.9, backend="sglang")
    for row in (left, right):
        for sample in row["execution"]["individual_runs"]:
            sample.update(ttft_basis="client-stream-first-content", throughput_tps=30.0)
        row["measurement"]["aggregate"] = asdict(
            aggregate_runs([RunMetrics(**sample) for sample in row["execution"]["individual_runs"]])
        )
        seal(row)
    chosen = api.RegressionPolicy(
        rules={"decode_tps": 0.05, "ttft_ms": 0.05, "request_duration_ms": 0.05},
        baseline_treatment={"backend": "vllm"},
        candidate_treatment={"backend": "sglang"},
    )
    assert gate(left, right, chosen)["exit_code"] == 0


def test_negative_unused_ttft_does_not_block_independent_wall_rule():
    assert gate(candidate=receipt(elapsed=0.9, ttft=-1))["exit_code"] == 0


def test_unlabeled_legacy_wall_duration_is_unavailable_not_zero_or_inferred():
    row = receipt(elapsed=0.9)
    row["execution"].pop("elapsed_seconds_basis")
    assert gate(candidate=seal(row))["exit_code"] == 3


def test_public_planbenchmark_objects_are_revalidated():
    from chimeraforge.bench.plan import PlanBenchmark

    row = receipt(elapsed=0.9)
    row["execution"]["requested_count"] = False
    with pytest.raises(api.PlanError):
        api.gate_benchmarks([PlanBenchmark(receipt())], [PlanBenchmark(seal(row))], policy=policy())


@pytest.mark.parametrize(
    "raw", [b"[]", b'{"rules":{},"rules":{}}', b'{"rules":{"decode_tps":NaN}}']
)
def test_strict_bounded_policy_json(raw, tmp_path):
    path = tmp_path / "policy.json"
    path.write_bytes(raw)
    with pytest.raises(api.PlanError):
        api.gate_benchmarks([receipt()], [receipt(elapsed=0.9)], policy=path)


def test_unmatched_receipt_is_read_validated_and_retained_not_skipped():
    row = receipt(elapsed=2)
    row["measurement"]["aggregate"]["count"] = 999
    with pytest.raises(api.PlanError):
        api.gate_benchmarks([receipt()], [receipt(elapsed=0.9), seal(row)], policy=policy())
    result = api.gate_benchmarks(
        [receipt()], [receipt(elapsed=0.9), receipt(elapsed=2)], policy=policy()
    ).to_dict()
    assert result["exit_code"] == 3 and len(result["inputs"]["candidate"]) == 2


def test_output_failure_is_domain_error_and_preserves_existing_file(tmp_path, monkeypatch):
    result = api.gate_benchmarks([receipt()], [receipt(elapsed=0.9)], policy=policy())
    target = tmp_path / "output.json"
    target.write_bytes(b"original output")
    original_replace = type(target).replace

    def fail_replace(source, destination):
        if destination == target:
            raise OSError("synthetic replacement failure")
        return original_replace(source, destination)

    monkeypatch.setattr(type(target), "replace", fail_replace)
    with pytest.raises(api.PlanError):
        result.save(target)
    assert target.read_bytes() == b"original output" and list(tmp_path.iterdir()) == [target]


def test_hardlink_output_alias_is_refused(tmp_path):
    import os

    baseline, candidate = tmp_path / "baseline.json", tmp_path / "candidate.json"
    baseline.write_text(json.dumps(receipt()))
    candidate.write_text(json.dumps(receipt(elapsed=0.9)))
    alias = tmp_path / "alias.json"
    result = api.gate_benchmarks([baseline], [candidate], policy=policy())
    os.link(baseline, alias)
    with pytest.raises(api.PlanError):
        result.save(alias)


@pytest.mark.parametrize(
    "metric", ["completed_token_rate_tps", "decode_tps", "ttft_ms", "request_duration_ms"]
)
def test_zero_required_metric_never_passes(metric):
    row = receipt(elapsed=0.9)
    if metric == "completed_token_rate_tps":
        row["execution"]["elapsed_seconds"] = 0
    else:
        field = {
            "decode_tps": "eval_duration_ms",
            "ttft_ms": "ttft_ms",
            "request_duration_ms": "total_duration_ms",
        }[metric]
        for sample in row["execution"]["individual_runs"]:
            sample[field] = 0
        row["measurement"]["aggregate"] = asdict(
            aggregate_runs([RunMetrics(**sample) for sample in row["execution"]["individual_runs"]])
        )
    assert (
        gate(candidate=seal(row), chosen=api.RegressionPolicy(rules={metric: 0.05}))["exit_code"]
        == 3
    )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda r: r["execution"]["request"].update(prompt_sha256="wrong"),
        lambda r: r["execution"].update(elapsed_seconds=float("inf")),
        lambda r: r["measurement"]["individual_runs"][0].update(cached_prompt_tokens=99),
        lambda r: r["measurement"]["individual_runs"][0].update(throughput_tps=-4),
        lambda r: r["measurement"]["individual_runs"][0].update(ttft_basis=False),
        lambda r: r["execution"]["request"].update(workload="server", arrival_rate=None),
        lambda r: r["execution"].update(serving_before=[]),
        lambda r: r.update(schema_version=True),
        lambda r: r.update(kind="other"),
        lambda r: r.update(fingerprint="a" * 64),
    ],
)
def test_malformed_shapes_and_nonfinite_data_refused_without_tracebacks(mutator):
    row = receipt(elapsed=0.9)
    mutator(row)
    if row["fingerprint"] != "a" * 64:
        seal(row)
    with pytest.raises(api.PlanError):
        gate(candidate=row)


def test_known_native_rate_must_agree_with_server_counts_and_duration():
    row = receipt(elapsed=0.9)
    for sample in row["execution"]["individual_runs"]:
        sample["throughput_tps"] = 999
    row["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**sample) for sample in row["execution"]["individual_runs"]])
    )
    with pytest.raises(api.PlanError):
        gate(candidate=seal(row), chosen=api.RegressionPolicy(rules={"decode_tps": 0.05}))


def test_after_known_difference_is_not_waived_by_missing_before_metadata():
    row = receipt(elapsed=0.9)
    row["execution"]["serving_before"]["version"] = None
    row["execution"]["serving_after"]["version"] = "new"
    assert gate(candidate=seal(row))["exit_code"] == 3


def test_missing_unrequired_facts_are_explicit_but_not_an_automatic_failure():
    report = gate()
    assert report["exit_code"] == 0
    pair = report["pairs"][0]
    assert pair["conditions"]["replicas"]["state"] == "unavailable"
    assert "replicas" in pair["uncontrolled_or_unavailable_facts"]


def test_held_paths_are_consumed_once_and_not_reread_on_save(tmp_path, monkeypatch):
    from chimeraforge import plan_bundle

    baseline, candidate = tmp_path / "baseline.json", tmp_path / "candidate.json"
    baseline.write_text(json.dumps(receipt()))
    candidate.write_text(json.dumps(receipt(elapsed=0.9)))
    original_read = plan_bundle._read
    reads = []

    def record(path, limit, **kwargs):
        reads.append(path)
        return original_read(path, limit, **kwargs)

    monkeypatch.setattr(plan_bundle, "_read", record)
    result = api.gate_benchmarks([baseline], [candidate], policy=policy())
    candidate.write_bytes(b"replaced after consumption")
    assert result.to_dict()["exit_code"] == 0
    result.save(tmp_path / "output.json")
    assert reads == [baseline, candidate]


def test_actual_public_saved_benchmark_runner_supplies_gate_clock_and_coverage(monkeypatch):
    import asyncio
    from chimeraforge.bench import runner
    from chimeraforge.bench.backends.base import Backend

    saved = api.plan(api.PlanRequest(allow_network=False, budget=100000, avg_tokens=4))
    clock = [0.0]

    class NativeFixture(Backend):
        name = "ollama"
        closed = False

        async def health_check(self):
            return True, ""

        async def check_model(self, model):
            return True, ""

        async def get_version(self):
            return "synthetic-protocol"

        async def observe_serving(self, model):
            return {
                "backend": "ollama",
                "version": "synthetic-protocol",
                "model": model,
                "device": "cpu",
                "prefix_cache": False,
            }

        async def generate(self, model, prompt, options=None):
            clock[0] += 0.125
            return RunMetrics(4, 40, 2, 102, 2, 100, 8, 0, "server-prefill-duration")

        async def close(self):
            self.closed = True

    engines = []

    def backend(*args, **kwargs):
        instance = NativeFixture()
        engines.append(instance)
        return instance

    monkeypatch.setattr(runner, "get_backend", backend)
    monkeypatch.setattr(runner.time, "perf_counter", lambda: clock[0])
    first = asyncio.run(api.benchmark_plan(saved, backend="ollama", runs=3))
    clock[0] += 1
    second = asyncio.run(api.benchmark_plan(saved, backend="ollama", runs=3))
    assert all(engine.closed for engine in engines)
    assert first.to_dict()["execution"]["elapsed_seconds_basis"].startswith("client-workload-wall")
    # Identical synthetic sample/duration evidence is not two independent executions.
    report = api.gate_benchmarks([first], [second], policy=policy()).to_dict()
    assert report["exit_code"] == 3 and "duplicate_execution_payload" in report["blockers"]


def test_finite_inputs_cannot_emit_nonfinite_derived_wall_or_regression():
    row = receipt(elapsed=1e-320)
    result = gate(candidate=row)
    assert result["exit_code"] == 3
    json.dumps(result, allow_nan=False)
    result = gate(receipt(elapsed=1e308), receipt(elapsed=1e-300))
    assert result["exit_code"] == 3
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "condition",
    [
        {"prefix_cache": 1},
        {"context_length": True},
        {"hardware.fp8_supported": 1},
    ],
)
def test_boolean_condition_aliases_are_not_accepted(condition):
    with pytest.raises(api.PlanError):
        gate(chosen=policy(fixed_controls=condition))


@pytest.mark.parametrize(
    "condition",
    [
        {"model_spec.n_layers": True},
        {"model_spec.params_b": True},
        {"model_spec.parallel_hybrid": 1},
        {"model_spec.n_kv_heads": "8"},
    ],
)
def test_geometry_condition_scalar_types_are_strict(condition):
    with pytest.raises(api.PlanError):
        gate(chosen=policy(fixed_controls=condition))


def test_partial_known_cache_change_is_not_waived_by_missing_counts():
    left, right = receipt(), receipt(elapsed=0.9)
    for row in (left, right):
        for phase in ("serving_before", "serving_after"):
            row["execution"][phase]["prefix_cache"] = True
    for sample, known in zip(right["execution"]["individual_runs"], (None, None, 1)):
        sample["cached_prompt_tokens"] = known
    result = gate(seal(left), seal(right), policy(require_cache_evidence=False))
    assert result["exit_code"] == 3
    assert "observed_cache_hits_changed" in result["blockers"]


def test_two_partial_cache_populations_retain_proven_incompatibility():
    left, right = receipt(), receipt(elapsed=0.9)
    for row, counts in ((left, (None, 0, 0)), (right, (None, 1, 1))):
        for phase in ("serving_before", "serving_after"):
            row["execution"][phase]["prefix_cache"] = True
        for sample, known in zip(row["execution"]["individual_runs"], counts):
            sample["cached_prompt_tokens"] = known
        seal(row)
    assert gate(left, right, policy(require_cache_evidence=False))["exit_code"] == 3


@pytest.mark.parametrize("location", ["options", "ignored_metadata"])
def test_overflow_json_number_is_rejected_before_digest_normalization(location, monkeypatch):
    from pathlib import Path
    from chimeraforge import plan_bundle

    left, right = receipt(), receipt(elapsed=0.9)
    if location == "options":
        left["execution"]["request"]["options"]["temperature"] = None
        right["execution"]["request"]["options"]["temperature"] = float("inf")
    else:
        right["measurement"]["environment"]["untrusted_ignored"] = float("inf")
    raw = {
        "baseline.json": json.dumps(seal(left)).encode(),
        "candidate.json": json.dumps(seal(right)).replace("Infinity", "1e309").encode(),
    }
    monkeypatch.setattr(plan_bundle, "_read", lambda path, limit: raw[path.name])
    with pytest.raises(api.PlanError):
        api.gate_benchmarks([Path("baseline.json")], [Path("candidate.json")], policy=policy())


def test_strict_policy_held_parser_refuses_overflow_nested_numbers(monkeypatch):
    from pathlib import Path
    from chimeraforge import plan_bundle
    from chimeraforge.bench.gate_inputs import held_json, MAX_POLICY_BYTES

    monkeypatch.setattr(
        plan_bundle, "_read", lambda *args: b'{"rules":{"decode_tps":0.1},"nested":[1e309]}'
    )
    with pytest.raises(api.PlanError):
        held_json(Path("policy.json"), MAX_POLICY_BYTES)


@pytest.mark.parametrize("label", ["client_environment", "serving_extra", "hardware_price"])
def test_ignored_labels_cannot_manufacture_distinct_execution_evidence(label):
    left, right = receipt(), receipt()
    if label == "client_environment":
        left["execution"][label] = {"python_version": "first-label"}
        right["execution"][label] = {"python_version": "second-label"}
    elif label == "serving_extra":
        for phase in ("serving_before", "serving_after"):
            right["execution"][phase].update(
                private_extra="ignored-label", captured_at="other-date"
            )
    else:
        for row, price in ((left, 1), (right, 2)):
            for phase in ("serving_before", "serving_after"):
                row["execution"][phase]["hardware"] = {"cost_per_hour": price}
    result = gate(seal(left), seal(right))
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]


@pytest.mark.parametrize(
    "backend,basis",
    [("ollama", "server-prefill-duration"), ("vllm", "client-stream-first-content")],
)
def test_supported_positive_ttft_aliases_cannot_contradict_native_prefill(backend, basis):
    left, right = receipt(backend=backend), receipt(elapsed=0.9, backend=backend)
    for row in (left, right):
        for sample in row["execution"]["individual_runs"]:
            sample["ttft_basis"] = basis
    for sample in right["execution"]["individual_runs"]:
        sample["prompt_eval_duration_ms"] = 1000
    with pytest.raises(api.PlanError):
        gate(seal(left), seal(right), api.RegressionPolicy(rules={"ttft_ms": 0.05}))


def test_equal_cache_treatment_labels_cannot_waive_known_changed_hits():
    left, right = receipt(), receipt(elapsed=0.9)
    for row in (left, right):
        for phase in ("serving_before", "serving_after"):
            row["execution"][phase]["prefix_cache"] = True
    for sample in right["execution"]["individual_runs"]:
        sample["cached_prompt_tokens"] = 1
    result = gate(
        seal(left),
        seal(right),
        policy(
            baseline_treatment={"prefix_cache": True}, candidate_treatment={"prefix_cache": True}
        ),
    )
    assert result["exit_code"] == 3


def test_compatible_partial_cache_is_unknown_without_a_fabricated_contradiction():
    left, right = receipt(), receipt(elapsed=0.9)
    for row, counts in ((left, (None, 0, 0)), (right, (None, 0, 1))):
        for phase in ("serving_before", "serving_after"):
            row["execution"][phase]["prefix_cache"] = True
        for sample, known in zip(row["execution"]["individual_runs"], counts):
            sample["cached_prompt_tokens"] = known
        seal(row)
    assert gate(left, right)["exit_code"] == 3
    report = gate(left, right, policy(require_cache_evidence=False))
    assert report["exit_code"] == 0
    assert report["pairs"][0]["cache"]["candidate"]["known_counts"] == [0, 1]
    assert report["pairs"][0]["cache"]["candidate"]["unknown_count"] == 1


def test_actual_distinct_cache_treatment_is_allowed_with_complete_evidence():
    right = receipt(elapsed=0.9)
    for phase in ("serving_before", "serving_after"):
        right["execution"][phase]["prefix_cache"] = True
    for sample in right["execution"]["individual_runs"]:
        sample["cached_prompt_tokens"] = 1
    chosen = policy(
        baseline_treatment={"prefix_cache": False}, candidate_treatment={"prefix_cache": True}
    )
    assert gate(candidate=seal(right), chosen=chosen)["exit_code"] == 0


def test_supported_observed_treatment_changes_remain_distinct_execution_payloads():
    right = receipt()
    for phase in ("serving_before", "serving_after"):
        right["execution"][phase]["version"] = "0.35.2"
    report = gate(
        candidate=seal(right),
        chosen=policy(
            baseline_treatment={"version": "0.35.1"}, candidate_treatment={"version": "0.35.2"}
        ),
    )
    assert report["exit_code"] == 0
    assert (
        report["inputs"]["baseline"][0]["evidence_sha256"]
        != report["inputs"]["candidate"][0]["evidence_sha256"]
    )


def test_finite_large_ignored_numbers_are_allowed_and_do_not_change_execution_identity():
    right = receipt(elapsed=0.9)
    right["measurement"]["environment"]["ignored"] = 1e308
    assert gate(candidate=seal(right))["exit_code"] == 0
