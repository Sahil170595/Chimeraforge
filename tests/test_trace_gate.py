"""Synthetic protocol decisions; no independent execution or native serving claim."""

import copy
import json
from pathlib import Path

import pytest

from chimeraforge import api
from chimeraforge.bench.trace import NATIVE_FIELDS, _qualify, _timing
from chimeraforge.planner.replay import digest


def test_trace_cli_json_prose_and_all_consumed_output_aliases(tmp_path):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    left, right, policy, out = [
        tmp_path / name for name in ("left.json", "right.json", "policy.json", "out.json")
    ]
    left.write_text(json.dumps(receipt()))
    right.write_text(json.dumps(receipt(duration=0.10)))
    policy.write_text(json.dumps({"rules": {"latency_p95_ms": 0.1}}))
    argv = [
        "gate",
        "--kind",
        "trace",
        "--baseline",
        str(left),
        "--candidate",
        str(right),
        "--policy",
        str(policy),
    ]
    runner = CliRunner()
    result = runner.invoke(app, argv)
    assert result.exit_code == 0 and result.output.startswith("conditional_pass:")
    result = runner.invoke(app, [*argv, "--json", "--out", str(out)])
    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(out.read_bytes())
    for source in (left, right, policy):
        original = source.read_bytes()
        refused = runner.invoke(app, [*argv, "--json", "--out", str(source)])
        assert refused.exit_code == 2 and json.loads(refused.output)["error"]
        assert source.read_bytes() == original
    policy.write_text('{"private-sentinel":1,"private-sentinel":2}')
    refused = runner.invoke(app, [*argv, "--json"])
    assert refused.exit_code == 2 and "private-sentinel" not in refused.output
    parsed = runner.invoke(app, ["gate", "--kind", "trace"])
    assert parsed.exit_code == 2
    unsupported = runner.invoke(app, [*argv, "--kind", "unknown", "--json"])
    assert unsupported.exit_code == 2


def test_trace_result_atomic_failure_and_hardlink_alias(tmp_path, monkeypatch):
    import os

    left, right = tmp_path / "left.json", tmp_path / "right.json"
    left.write_text(json.dumps(receipt()))
    right.write_text(json.dumps(receipt(duration=0.10)))
    result = api.gate_traces([left], [right])
    alias = tmp_path / "alias.json"
    os.link(left, alias)
    with pytest.raises(api.PlanError):
        result.save(alias)
    original = left.read_bytes()
    out = tmp_path / "out.json"
    out.write_bytes(b"prior decision")

    def unavailable_replace(*args):
        raise OSError("synthetic output refusal")

    monkeypatch.setattr(Path, "replace", unavailable_replace)
    with pytest.raises(api.PlanError):
        result.save(out)
    assert left.read_bytes() == original and out.read_bytes() == b"prior decision"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("payload", [b"NaN", b'{"x":1e999}', b'{"x":1,"x":2}', b"[]"])
def test_trace_strict_bounded_json_boundary(tmp_path, payload):
    source = tmp_path / "invalid.json"
    source.write_bytes(payload)
    with pytest.raises(api.PlanError):
        api.gate_traces([source], [receipt()])


def seal(data):
    data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    return data


def receipt(
    *, duration=0.12, queued=0.0, count=2, elapsed=None, origin=0.0, first=True, cache=0, mean=True
):
    rows = []
    targets = {"latency_ms": 2000.0, "first_output_ms": None, "tpot_ms": None}
    serving = {
        "backend": "ollama",
        "version": "synthetic",
        "model": "synthetic",
        "model_digest": "a" * 64,
        "quant": "Q4_K_M",
        "context_length": 2048,
        "device": "cpu",
        "prefix_cache": False,
    }
    for i in range(count):
        start = i * queued
        row = {
            "descriptor": {
                "request_id": str(i),
                "prompt_sha256": "b" * 64,
                "prompt_bytes": 5,
                "max_output_tokens": 8,
                "arrival_offset_s": 0.0,
            },
            "state": "completed",
            "times": {
                "scheduled_s": 0.0,
                "arrival_s": 0.0,
                "start_s": start,
                "first_output_s": start + 0.02 if first else None,
                "terminal_s": start + duration,
            },
            "native": {
                **dict.fromkeys(NATIVE_FIELDS),
                "tokens_generated": 4,
                "prompt_tokens": 8,
                "cached_prompt_tokens": cache,
                "throughput_tps": 40.0,
                "ttft_ms": 2.0,
                "total_duration_ms": 102.0,
                "prompt_eval_duration_ms": 2.0,
                "eval_duration_ms": 100.0,
                "ttft_basis": "server-prefill-duration",
            },
            "error": None,
            "mean_tpot_ms": 25.0 if mean else None,
            "mean_tpot_basis": "server-decode-duration/output-token-count"
            if mean
            else "unavailable",
            "output_cap_state": "within_cap",
        }
        row["timing"] = _timing(row)
        row["slo"] = _qualify(row, targets)
        rows.append(row)
    elapsed = max(r["times"]["terminal_s"] for r in rows) + 0.01 if elapsed is None else elapsed
    data = {
        "schema_version": 1,
        "created_at": "synthetic",
        "tool": {"name": "chimeraforge", "version": "synthetic"},
        "model": "synthetic",
        "backend": "ollama",
        "endpoint": None,
        "workload": {"canonical_sha256": "c" * 64, "raw_sha256": None},
        "requests": rows,
        "targets": targets,
        "execution": {
            "planned": count,
            "attempted": count,
            "completed": count,
            "failed": 0,
            "partial": 0,
            "cancelled": 0,
            "not_started": 0,
            "concurrency": 1,
            "request_timeout_seconds": 300,
            "trace_timeout_seconds": 600,
            "elapsed_seconds": elapsed,
        },
        "clock": {
            "basis": "client time.perf_counter monotonic offsets in seconds",
            "origin": origin,
            "resolution_seconds": 1e-7,
        },
        "timing_bases": {
            "latency_ms": "scheduled-arrival-to-client-terminal",
            "first_output_ms": "scheduled-arrival-to-client-first-output",
            "tpot_ms": "per-request explicitly named mean decode basis; not every-token latency",
        },
        "deadline_scope": "scheduled replay only; preflight/metadata separately bounded, cleanup cooperative",
        "goodput": {
            "qualification": "observed_targets",
            "qualified_requests": count,
            "horizon_seconds": elapsed,
            "planned_horizon_seconds": 0.0,
            "horizon_basis": "origin to max(last planned arrival, observed terminal/stop)",
            "joint_outcomes": {
                "pass": count,
                "breach": 0,
                "unknown": 0,
                "not_completed": 0,
                "not_requested": 0,
            },
            "requests_per_second": count / elapsed,
        },
        "serving_before": copy.deepcopy(serving),
        "serving_after": copy.deepcopy(serving),
        "serving_stability": {},
        "resource_cleanup": {"state": "completed"},
        "stop_reason": None,
        "error": None,
        "exit_code": 0,
        "performance": {
            "state": "observed_client_workload",
            "gpu_qualification": "unverified",
            "served_file_authentication": "unverified",
        },
        "limits": "Synthetic protocol only",
    }
    from chimeraforge.bench.serving_binding import serving_stability

    data["serving_stability"] = serving_stability(serving, serving)
    return seal(data)


def policy(**kw):
    return api.TraceGatePolicy(
        rules={"goodput_rps": 0.05, "latency_p95_ms": 0.1}, fixed_controls={"device": "cpu"}, **kw
    )


def test_trace_gate_retains_all_pairs_and_defensive_snapshot():
    left, right = receipt(), receipt(duration=0.10)
    original = copy.deepcopy((left, right))
    gate = api.gate_traces([left], [right], policy=policy())
    result = gate.to_dict()
    assert result["outcome"] == "conditional_pass" and result["exit_code"] == 0
    assert result["pairs"][0]["metrics"]["latency_p95_ms"]["baseline"] == pytest.approx(120)
    result["pairs"].clear()
    assert gate.to_dict()["pairs"] and (left, right) == original


def test_decode_only_improvement_cannot_hide_queued_latency_regression():
    right = receipt(duration=0.10, queued=0.4)
    result = api.gate_traces([receipt()], [right], policy=policy()).to_dict()
    assert (
        result["exit_code"] == 1
        and result["pairs"][0]["metrics"]["latency_p95_ms"]["state"] == "regression"
    )


def test_origin_and_label_changes_cannot_qualify_copied_execution():
    left = receipt()
    right = copy.deepcopy(left)
    right.update(created_at="changed", endpoint="http://private.invalid/label")
    right["clock"]["origin"] = 42.0
    right["tool"]["version"] = "new"
    seal(right)
    result = api.gate_traces([left], [right], policy=policy()).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]


@pytest.mark.parametrize("field", ["timing", "counts", "goodput", "slo"])
def test_resealed_favorable_inconsistent_receipt_is_malformed(field):
    value = receipt(duration=0.10)
    if field == "timing":
        value["requests"][0]["timing"]["latency_ms"] = 1.0
    elif field == "counts":
        value["execution"]["completed"] = 1
    elif field == "goodput":
        value["goodput"]["requests_per_second"] = 999
    else:
        value["requests"][0]["slo"]["joint"] = "breach"
    seal(value)
    with pytest.raises(api.PlanError):
        api.gate_traces([receipt()], [value], policy=policy())


def test_valid_full_1024_rows_and_typed_dict_path_parity(tmp_path):
    left, right = receipt(count=1024), receipt(count=1024, duration=0.1)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(left))
    b.write_text(json.dumps(right))
    for baseline, candidate in (
        (left, right),
        (api.TraceReplay(left), api.TraceReplay(right)),
        (a, b),
    ):
        result = api.gate_traces([baseline], [candidate], policy=policy()).to_dict()
        assert (
            result["exit_code"] == 0
            and result["inputs"]["baseline"][0]["execution"]["planned"] == 1024
        )


def test_unknown_required_first_output_is_not_filtered_from_p95():
    chosen = api.TraceGatePolicy(rules={"first_output_p95_ms": 0.1})
    result = api.gate_traces(
        [receipt(first=False)], [receipt(duration=0.1)], policy=chosen
    ).to_dict()
    assert (
        result["exit_code"] == 3
        and result["pairs"][0]["metrics"]["first_output_p95_ms"]["baseline"] is None
    )


@pytest.mark.parametrize("field", ["mean_tpot_basis", "ttft_basis", "error-stage", "error-type"])
@pytest.mark.parametrize("bad", [[], {}, 1, True])
def test_wrong_structured_enums_are_public_malformed_errors(field, bad):
    value = receipt(duration=0.1)
    if field == "mean_tpot_basis":
        value["requests"][0][field] = bad
    elif field == "ttft_basis":
        value["requests"][0]["native"][field] = bad
    else:
        value["error"] = {
            "stage": bad if field == "error-stage" else "metadata_after",
            "type": bad if field == "error-type" else "RuntimeError",
        }
        value["exit_code"] = 1
    seal(value)
    with pytest.raises(api.PlanError):
        api.gate_traces([receipt()], [value], policy=policy())


def test_completed_generation_error_cannot_be_resealed_into_a_pass():
    value = receipt(duration=0.1)
    value["requests"][0]["error"] = {"stage": "generation", "type": "RuntimeError"}
    seal(value)
    with pytest.raises(api.PlanError):
        api.gate_traces([receipt()], [value], policy=policy())


@pytest.mark.parametrize("stage", ["metadata_after", "cleanup"])
def test_valid_global_probe_or_cleanup_failure_retains_complete_rows_as_inconclusive(stage):
    value = receipt(duration=0.1)
    value["error"] = {"stage": stage, "type": "RuntimeError"}
    value["exit_code"] = 1
    if stage == "cleanup":
        value["resource_cleanup"]["state"] = "incomplete"
    else:
        value["serving_after"] = None
    finish(value)
    result = api.gate_traces([receipt()], [value], policy=policy()).to_dict()
    assert (
        result["exit_code"] == 3 and result["inputs"]["candidate"][0]["execution"]["completed"] == 2
    )


def finish(value):
    """Rebuild only producer-defined derived fields after a declared fixture mutation."""
    from chimeraforge.bench.serving_binding import serving_stability

    for row in value["requests"]:
        row["timing"] = _timing(row)
        row["slo"] = _qualify(row, value["targets"])
        count = row["native"]["tokens_generated"]
        row["output_cap_state"] = (
            "unknown"
            if count is None
            else "within_cap"
            if count <= row["descriptor"]["max_output_tokens"]
            else "exceeded"
        )
    ex = value["execution"]
    rows = value["requests"]
    for state in ("completed", "failed", "partial", "cancelled", "not_started"):
        ex[state] = sum(row["state"] == state for row in rows)
    ex["attempted"] = sum(row["times"]["start_s"] is not None for row in rows)
    origin = value["clock"]["origin"]
    elapsed = ex["elapsed_seconds"]
    horizon = (
        max(elapsed, max(r["descriptor"]["arrival_offset_s"] for r in rows))
        if origin is not None
        else None
    )
    g = value["goodput"]
    requested = any(v is not None for v in value["targets"].values())
    g.update(
        qualification="not_requested"
        if not requested
        else "observed_targets"
        if origin is not None
        else "unavailable",
        horizon_seconds=horizon,
        qualified_requests=sum(r["slo"]["joint"] == "pass" for r in rows),
    )
    for state in g["joint_outcomes"]:
        g["joint_outcomes"][state] = sum(r["slo"]["joint"] == state for r in rows)
    g["requests_per_second"] = (
        g["qualified_requests"] / horizon
        if requested and horizon is not None and horizon > 0
        else None
    )
    value["exit_code"] = (
        0
        if ex["completed"] == len(rows) and value["error"] is None and value["stop_reason"] is None
        else 1
    )
    value["performance"]["state"] = (
        "observed_client_workload" if origin is not None else "unavailable"
    )
    value["serving_stability"] = serving_stability(
        value["serving_before"] or {}, value["serving_after"] or {}
    )
    return seal(value)


@pytest.mark.parametrize("state", ["failed", "partial", "cancelled", "not_started"])
def test_valid_incomplete_native_and_no_origin_receipts_are_retained(state):
    value = receipt(duration=0.1)
    for row in value["requests"]:
        row.update(
            state=state,
            native=dict.fromkeys(NATIVE_FIELDS),
            mean_tpot_ms=None,
            mean_tpot_basis="unavailable",
            error={"stage": "generation", "type": "TimeoutError"}
            if state in {"failed", "partial"}
            else None,
        )
        if state == "failed":
            row["times"]["first_output_s"] = None
        if state == "not_started":
            row["times"].update(arrival_s=None, start_s=None, first_output_s=None, terminal_s=None)
    if state == "not_started":
        value["clock"]["origin"] = None
        value["execution"]["elapsed_seconds"] = None
    else:
        value["stop_reason"] = "trace_deadline"
    finish(value)
    result = api.gate_traces([receipt()], [value], policy=policy()).to_dict()
    assert result["exit_code"] == 3 and result["inputs"]["candidate"][0]["execution"][state] == 2


def test_zero_goodput_baseline_is_inconclusive_and_positive_to_zero_is_regression():
    left, right = receipt(), receipt(duration=3)
    left["targets"]["latency_ms"] = 1000
    right["targets"]["latency_ms"] = 1000
    finish(left)
    finish(right)
    chosen = api.TraceGatePolicy(rules={"goodput_rps": 0.05})
    assert api.gate_traces([left], [right], policy=chosen).to_dict()["exit_code"] == 1
    assert api.gate_traces([right], [left], policy=chosen).to_dict()["exit_code"] == 3


def test_unknown_means_and_cache_default_are_not_favorable_values():
    left, right = receipt(cache=None, mean=False), receipt(duration=0.1, cache=None, mean=False)
    for r in (left, right):
        r["serving_before"]["prefix_cache"] = r["serving_after"]["prefix_cache"] = None
        finish(r)
    assert api.gate_traces([left], [right], policy=policy()).to_dict()["exit_code"] == 3
    assert (
        api.gate_traces([left], [right], policy=policy(require_cache_evidence=False)).to_dict()[
            "exit_code"
        ]
        == 0
    )
    assert (
        api.gate_traces(
            [left],
            [right],
            policy=api.TraceGatePolicy(rules={"tpot_p95_ms": 0.1}, require_cache_evidence=False),
        ).to_dict()["exit_code"]
        == 3
    )


def test_known_cache_drift_and_contradiction_are_not_waived_by_opt_out():
    value = receipt(duration=0.1, cache=1)
    finish(value)
    assert (
        api.gate_traces(
            [receipt()], [value], policy=policy(require_cache_evidence=False)
        ).to_dict()["exit_code"]
        == 3
    )
    for v in (value,):
        v["serving_before"]["prefix_cache"] = v["serving_after"]["prefix_cache"] = True
        finish(v)
    left = receipt()
    left["serving_before"]["prefix_cache"] = left["serving_after"]["prefix_cache"] = True
    finish(left)
    result = api.gate_traces([left], [value], policy=policy(require_cache_evidence=False)).to_dict()
    assert result["exit_code"] == 3 and "observed_cache_hits_changed" in result["blockers"]


def test_consistently_exceeded_caps_are_valid_but_ineligible():
    value = receipt(duration=0.1)
    for row in value["requests"]:
        row["descriptor"]["max_output_tokens"] = 3
    finish(value)
    result = api.gate_traces([receipt()], [value], policy=policy()).to_dict()
    assert result["exit_code"] == 3 and "output_cap_exceeded" in result["blockers"]


def test_unpaired_declared_receipts_are_retained_and_never_pass():
    result = api.gate_traces(
        [receipt(), receipt(duration=0.15)],
        [receipt(duration=0.1)],
        policy=policy(expected_replicates=2),
    ).to_dict()
    assert result["exit_code"] == 3 and len(result["inputs"]["baseline"]) == 2


@pytest.mark.parametrize("role", ["receipt", "policy"])
def test_private_duplicate_field_names_never_escape_json_boundary(tmp_path, role):
    path = tmp_path / "private.json"
    path.write_bytes(b'{"private-response-sentinel":1,"private-response-sentinel":2}')
    with pytest.raises(api.PlanError) as error:
        api.gate_traces(
            [path if role == "receipt" else receipt()],
            [receipt(duration=0.1)],
            policy=path if role == "policy" else policy(),
        )
    assert "private-response-sentinel" not in str(error.value) and error.value.__suppress_context__


def test_swapped_known_request_cache_hits_are_drift_even_if_multiset_matches():
    left, right = receipt(), receipt(duration=0.1)
    for data, counts in ((left, [0, 4]), (right, [4, 0])):
        data["serving_before"]["prefix_cache"] = data["serving_after"]["prefix_cache"] = True
        for row, count in zip(data["requests"], counts):
            row["native"]["cached_prompt_tokens"] = count
        finish(data)
    result = api.gate_traces([left], [right], policy=policy(require_cache_evidence=False)).to_dict()
    assert result["exit_code"] == 3 and "ordered_cache_hits_changed" in result["blockers"]


def test_relabelled_request_ids_and_workload_commitment_do_not_create_replicates():
    left, right = receipt(), receipt(duration=0.1)
    labelled = []
    for value in (left, right):
        copied = copy.deepcopy(value)
        for row in copied["requests"]:
            row["descriptor"]["request_id"] = "renamed-" + row["descriptor"]["request_id"]
        copied["workload"]["canonical_sha256"] = "d" * 64
        labelled.append(seal(copied))
    result = api.gate_traces(
        [left, labelled[0]], [right, labelled[1]], policy=policy(expected_replicates=2)
    ).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]


def test_declared_byte_budget_is_charged_before_cached_clone(tmp_path, monkeypatch):
    import chimeraforge.bench.trace_gate as gate

    path = tmp_path / "same.json"
    path.write_text(json.dumps(receipt()))
    monkeypatch.setattr(gate, "MAX_TOTAL_BYTES", path.stat().st_size)
    monkeypatch.setattr(
        gate.copy, "deepcopy", lambda *a: pytest.fail("cloned after declared budget exhausted")
    )
    with pytest.raises(api.PlanError):
        api.gate_traces([path], [path], policy={"rules": {"goodput_rps": 0.05}})


def test_same_file_population_is_read_once_and_held_against_later_changes(tmp_path, monkeypatch):
    import chimeraforge.plan_bundle as bundle

    path = tmp_path / "same.json"
    path.write_text(json.dumps(receipt()))
    read = bundle._read
    calls = []

    def mutate(p, limit, **kw):
        data = read(p, limit, **kw)
        calls.append(p)
        p.write_text("invalid bytes after held read")
        return data

    monkeypatch.setattr(bundle, "_read", mutate)
    result = api.gate_traces([path], [path], policy=policy()).to_dict()
    assert result["exit_code"] == 3 and len(calls) == 1


def test_full_p95_includes_queue_outlier_without_average_filtering():
    value = receipt(count=20, duration=0.1)
    value["requests"][-1]["times"].update(start_s=0.4, first_output_s=0.42, terminal_s=0.5)
    value["execution"]["elapsed_seconds"] = 0.51
    finish(value)
    chosen = api.TraceGatePolicy(rules={"latency_p95_ms": 0.1})
    result = api.gate_traces([receipt(count=20)], [value], policy=chosen).to_dict()
    assert result["pairs"][0]["metrics"]["latency_p95_ms"]["candidate"] == pytest.approx(120)


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"latency_p95_ms": 1},
        {"goodput_rps": True},
        {"decode_tps": 0.1},
        {"goodput_rps": float("nan")},
    ],
)
def test_closed_finite_trace_policy_rejects_unsupported_rules(bad):
    with pytest.raises(api.PlanError):
        api.gate_traces([receipt()], [receipt(duration=0.1)], policy={"rules": bad})


def test_goodput_with_tpot_slo_requires_identical_recognized_mean_bases():
    left, right = receipt(), receipt(duration=0.1)
    for data in (left, right):
        data["targets"]["tpot_ms"] = 100.0
        finish(data)
    for phase in ("before", "after"):
        right["serving_" + phase]["backend"] = "vllm"
    right["backend"] = "vllm"
    for row in right["requests"]:
        row["mean_tpot_basis"] = "client-first-to-last-native-output/(server-output-count-1)"
        row["mean_tpot_ms"] = 100 / 3
        row["native"].update(ttft_basis="client-stream-first-content", throughput_tps=30.0)
    finish(right)
    chosen = api.TraceGatePolicy(
        rules={"goodput_rps": 0.05},
        baseline_treatment={"backend": "ollama"},
        candidate_treatment={"backend": "vllm"},
    )
    result = api.gate_traces([left], [right], policy=chosen).to_dict()
    assert (
        result["exit_code"] == 3
        and "mean_timing_basis_unavailable_or_changed" in result["blockers"]
    )


def test_controls_actual_lengths_and_caps_are_required_pair_bindings():
    for change in ("controls", "lengths", "caps"):
        value = receipt(duration=0.1)
        if change == "controls":
            value["serving_after"]["context_length"] = 4096
        elif change == "lengths":
            value["requests"][0]["native"]["prompt_tokens"] = 9
        else:
            value["requests"][0]["descriptor"]["max_output_tokens"] = 10
        finish(value)
        assert api.gate_traces([receipt()], [value], policy=policy()).to_dict()["exit_code"] == 3


def test_cooperative_drained_elapsed_may_exceed_requested_timeout():
    left, right = receipt(elapsed=4000.0), receipt(duration=0.1, elapsed=3900.0)
    result = api.gate_traces([left], [right], policy=policy()).to_dict()
    assert result["exit_code"] == 0 and result["pairs"][0]["metrics"]["goodput_rps"][
        "baseline"
    ] == pytest.approx(2 / 4000)
