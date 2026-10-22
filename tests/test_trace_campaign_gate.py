"""Synthetic campaign protocol oracles; no native-serving or performance claim."""

import copy
import json
import math

import pytest

from chimeraforge import api
from chimeraforge.bench.trace_campaign import TraceCampaign, _prepare
from chimeraforge.bench.trace_workload import TraceRequest, TraceSLO
from test_trace_gate import finish, receipt, seal


def campaign(*, durations=(0.12, 0.14, 0.16), final_stop=None, count=2):
    rows = [TraceRequest(str(i), "PRIVATE INPUT", 8, 0.0) for i in range(count)]
    _, manifest, _ = _prepare(
        rows,
        model="synthetic",
        backend="ollama",
        base_url=None,
        replicates=len(durations),
        concurrency=2,
        request_timeout=300,
        trace_timeout=600,
        campaign_timeout=1800,
        slos=TraceSLO(latency_ms=2000.0),
        stop_event=None,
    )
    replicas = []
    cursor = 0.0
    for i, duration in enumerate(durations):
        native = receipt(duration=duration, origin=100.0 + cursor + 0.1, count=count)
        native["workload"] = {**manifest["workload"], "raw_sha256": None}
        for row, descriptor in zip(native["requests"], manifest["ordered_descriptors"]):
            row["descriptor"] = copy.deepcopy(descriptor)
        finish(native)
        end = cursor + max(0.8, native["execution"]["elapsed_seconds"] + 0.2)
        replicas.append(
            {
                "index": i,
                "manifest_fingerprint": manifest["fingerprint"],
                "workload_ref": manifest["workload"]["canonical_sha256"],
                "start_s": cursor,
                "end_s": end,
                "state": "completed",
                "receipt": native,
                "error": None,
                "reason": None,
            }
        )
        cursor = max(cursor + 1.0, end + 0.1)
    return seal(
        {
            "schema_version": 1,
            "kind": "chimeraforge.trace-campaign",
            "created_at": "synthetic",
            "manifest": manifest,
            "replicas": replicas,
            "execution": {
                "planned": len(replicas),
                "completed": len(replicas),
                "incomplete": 0,
                "failed": 0,
                "not_started": 0,
            },
            "clock": {
                "basis": "client time.perf_counter monotonic offsets in seconds",
                "origin": 100.0,
                "elapsed_seconds": cursor,
            },
            "stop_reason": final_stop,
            "state": "completed",
            "exit_code": 0,
            "assurance": dict.fromkeys(
                (
                    "external_preregistration",
                    "time_authentication",
                    "independent_cold_executions",
                    "cache_independence",
                    "gpu_geometry",
                    "served_weights",
                    "provider_termination",
                ),
                "unverified",
            ),
            "limits": "Synthetic protocol oracle only",
        }
    )


def reseal(data):
    seal(data["manifest"])
    for slot in data["replicas"]:
        slot["manifest_fingerprint"] = data["manifest"]["fingerprint"]
        if slot["receipt"] is not None:
            seal(slot["receipt"])
    return seal(data)


def incomplete(data, index=1, *, failed=False):
    for i, slot in enumerate(data["replicas"]):
        if i < index:
            continue
        slot.update(receipt=None, error=None)
        if i == index:
            slot.update(
                state="failed",
                error={"stage": "campaign_replay", "type": "ValueError"},
                reason="replay_failed",
            )
            if not failed:
                native = receipt(
                    duration=0.13, origin=data["clock"]["origin"] + slot["start_s"] + 0.1
                )
                native["workload"] = {**data["manifest"]["workload"], "raw_sha256": None}
                for row, descriptor in zip(
                    native["requests"], data["manifest"]["ordered_descriptors"]
                ):
                    row["descriptor"] = copy.deepcopy(descriptor)
                native["error"] = {"stage": "metadata_after", "type": "RuntimeError"}
                native["serving_after"] = None
                finish(native)
                slot.update(
                    state="incomplete", receipt=native, error=None, reason="native_incomplete"
                )
        else:
            slot.update(
                start_s=None, end_s=None, state="not_started", reason="first_incomplete_replicate"
            )
    data["execution"] = {
        "planned": len(data["replicas"]),
        **{
            state: sum(row["state"] == state for row in data["replicas"])
            for state in ("completed", "incomplete", "failed", "not_started")
        },
    }
    data.update(state="incomplete", exit_code=1, stop_reason="first_incomplete_replicate")
    return reseal(data)


def gate(left=None, right=None, **policy):
    from chimeraforge.bench.trace_campaign_gate import gate_trace_campaigns

    return gate_trace_campaigns(
        campaign() if left is None else left,
        campaign(durations=(0.10, 0.11, 0.09)) if right is None else right,
        policy={"rules": {"latency_p95_ms": 0.1}, "expected_replicates": 3, **policy},
    )


def test_full_campaign_population_positive_and_breach_oracles():
    assert gate().to_dict()["exit_code"] == 0
    result = gate(right=campaign(durations=(0.10, 0.30, 0.09))).to_dict()
    assert result["exit_code"] == 1 and len(result["pairs"]) == 3
    assert result["known_breaches"] == [{"index": 1, "metric": "latency_p95_ms"}]
    assert result["inputs"]["baseline"]["execution"]["planned"] == 3


@pytest.mark.parametrize(
    "mutation",
    [
        "drop",
        "index",
        "counts",
        "manifest_count",
        "binding",
        "child_descriptor",
        "child_workload",
        "child_model",
        "child_backend",
        "child_concurrency",
        "child_timeout",
        "child_target",
        "raw_hash",
        "swap",
        "overlap",
        "outer_elapsed",
        "after_boundary",
    ],
)
def test_resealed_population_binding_control_and_chronology_forgery_refuses(mutation):
    data = campaign(durations=(0.10, 0.11, 0.09))
    child = data["replicas"][0]["receipt"]
    if mutation == "drop":
        data["replicas"].pop()
    elif mutation == "index":
        data["replicas"][1]["index"] = 0
    elif mutation == "counts":
        data["execution"]["completed"] = True
    elif mutation == "manifest_count":
        data["manifest"]["population"]["total_requests"] = 5
    elif mutation == "binding":
        data["replicas"][0]["workload_ref"] = "0" * 64
    elif mutation == "child_descriptor":
        child["requests"][0]["descriptor"]["prompt_sha256"] = "0" * 64
    elif mutation == "child_workload":
        child["workload"]["canonical_sha256"] = "0" * 64
    elif mutation == "child_model":
        child["model"] = "other-model"
    elif mutation == "child_backend":
        child["backend"] = "other-backend"
    elif mutation == "child_concurrency":
        child["execution"]["concurrency"] = 3
    elif mutation == "child_timeout":
        child["execution"]["request_timeout_seconds"] = 200
    elif mutation == "child_target":
        child["targets"]["latency_ms"] = 1999
    elif mutation == "raw_hash":
        child["workload"]["raw_sha256"] = "0" * 64
    elif mutation == "swap":
        child = data["replicas"][1]["receipt"]
        data["replicas"][0]["receipt"] = child
        child["requests"][0]["descriptor"]["prompt_sha256"] = "0" * 64
    elif mutation == "overlap":
        data["replicas"][1]["start_s"] = 0.2
    elif mutation == "outer_elapsed":
        data["clock"]["elapsed_seconds"] = 0.2
    elif mutation == "after_boundary":
        incomplete(data)
        data["replicas"][2].update(
            state="completed",
            start_s=2.0,
            end_s=2.8,
            receipt=campaign()["replicas"][2]["receipt"],
            reason=None,
        )
        data["execution"].update(completed=2, not_started=0)
    reseal(data)
    with pytest.raises(api.PlanError):
        gate(right=data)


@pytest.mark.parametrize(
    "field",
    [
        "model",
        "descriptor",
        "population",
        "controls",
        "policy",
        "assurance",
        "clock",
        "replica_error",
        "replica_state",
        "execution",
    ],
)
def test_nested_shapes_refuse_without_reflecting_private_diagnostics(field):
    data = incomplete(campaign(), index=0, failed=True)
    if field == "model":
        data["manifest"]["controls"]["model"] = None
    elif field == "descriptor":
        data["manifest"]["ordered_descriptors"][0]["prompt_bytes"] = False
    elif field in ("population", "controls", "policy"):
        data["manifest"][field] = []
    elif field in ("assurance", "clock", "execution"):
        data[field] = []
    elif field == "replica_error":
        data["replicas"][0]["error"] = {"stage": "PRIVATE SENTINEL", "type": "PRIVATE SENTINEL"}
    else:
        data["replicas"][0]["state"] = {"PRIVATE SENTINEL": 1}
    reseal(data)
    with pytest.raises(api.PlanError) as exc:
        gate(right=data)
    assert "PRIVATE SENTINEL" not in str(exc.value)


@pytest.mark.parametrize("failed", [False, True])
def test_incomplete_and_failed_boundary_preserves_missing_slots_and_known_breach(failed):
    data = incomplete(campaign(durations=(0.3, 0.11, 0.09)), failed=failed)
    result = gate(right=data).to_dict()
    assert result["exit_code"] == 3 and len(result["pairs"]) == 3
    assert result["known_breaches"] == [{"index": 0, "metric": "latency_p95_ms"}]
    assert result["inputs"]["candidate"]["replicas"][2]["receipt"] is None
    assert result["inputs"]["candidate"]["replicas"][2]["state"] == "not_started"


@pytest.mark.parametrize("stop", ["caller_stop", "campaign_deadline"])
def test_final_completed_population_can_coexist_with_stop(stop):
    assert (
        gate(right=campaign(durations=(0.10, 0.11, 0.09), final_stop=stop)).to_dict()["exit_code"]
        == 0
    )


def test_all_slo_breaches_are_completed_execution_not_fabricated_incomplete():
    result = gate(right=campaign(durations=(3.0, 3.1, 3.2))).to_dict()
    assert result["exit_code"] == 1
    assert result["inputs"]["candidate"]["execution"]["completed"] == 3


def test_policy_population_and_semantic_copies_cannot_pass():
    assert gate(expected_replicates=2).to_dict()["exit_code"] == 3
    data = campaign(durations=(0.10, 0.11, 0.09))
    data["replicas"][1]["receipt"] = copy.deepcopy(data["replicas"][0]["receipt"])
    data["replicas"][1]["receipt"]["created_at"] = "renamed time"
    data["replicas"][1]["receipt"]["clock"]["origin"] = (
        data["clock"]["origin"] + data["replicas"][1]["start_s"] + 0.1
    )
    data["replicas"][1]["receipt"]["execution"]["request_timeout_seconds"] = 300.0
    reseal(data)
    result = gate(right=data).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]
    result = gate(right=campaign()).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]


def test_native_endpoint_default_allowed_but_foreign_endpoint_rejected():
    data = campaign(durations=(0.10, 0.11, 0.09))
    for slot in data["replicas"]:
        slot["receipt"]["endpoint"] = "http://localhost:11434"
    reseal(data)
    assert gate(right=data).to_dict()["exit_code"] == 0
    data["replicas"][0]["receipt"]["endpoint"] = "http://foreign.example"
    reseal(data)
    with pytest.raises(api.PlanError):
        gate(right=data)


def test_read_once_cached_path_and_total_budget_before_clone(tmp_path, monkeypatch):
    import chimeraforge.bench.trace_campaign_gate as core
    import chimeraforge.plan_bundle as bundle

    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(campaign()))
    read, calls = bundle._read, []

    def mutate(p, limit, **kwargs):
        raw = read(p, limit, **kwargs)
        calls.append(p)
        p.write_text("invalid after held read")
        return raw

    monkeypatch.setattr(bundle, "_read", mutate)
    assert gate(path, path).to_dict()["exit_code"] == 3 and len(calls) == 1
    path.write_text(json.dumps(campaign()))
    monkeypatch.setattr(core, "MAX_TOTAL_BYTES", path.stat().st_size)
    monkeypatch.setattr(
        core.copy, "deepcopy", lambda *args: pytest.fail("clone after exhausted budget")
    )
    with pytest.raises(api.PlanError):
        gate(path, path)


def test_campaign_child_and_outer_byte_limits(tmp_path, monkeypatch):
    import chimeraforge.bench.trace_campaign_inputs as inputs

    monkeypatch.setattr(inputs, "MAX_RECEIPT_BYTES", 32)
    with pytest.raises(api.PlanError):
        gate()
    monkeypatch.undo()
    monkeypatch.setattr(inputs, "MAX_CAMPAIGN_BYTES", 32)
    with pytest.raises(api.PlanError):
        gate()


def test_typed_and_path_sources_protect_source_policy_and_private_workload(tmp_path):
    private = tmp_path / "private.json"
    private.write_bytes(b"PRIVATE PROMPT bytes")
    left = TraceCampaign(campaign(), (private,))
    right = tmp_path / "candidate.json"
    right.write_text(json.dumps(campaign(durations=(0.10, 0.11, 0.09))))
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"rules": {"latency_p95_ms": 0.1}, "expected_replicates": 3}))
    from chimeraforge.bench.trace_campaign_gate import gate_trace_campaigns

    result = gate_trace_campaigns(left, right, policy=policy)
    assert result.to_dict()["exit_code"] == 0
    for path in (private, right, policy):
        before = path.read_bytes()
        with pytest.raises(api.PlanError):
            result.save(path)
        assert path.read_bytes() == before
    result.save(tmp_path / "decision.json")
    assert "PRIVATE PROMPT" not in (tmp_path / "decision.json").read_text()


def test_loader_exposes_held_native_views_and_defensive_snapshot():
    from chimeraforge.bench.trace_campaign_inputs import load_campaign

    source = campaign()
    loaded = load_campaign(source)
    source["replicas"].clear()
    assert len(loaded["replicas"]) == 3 and loaded["replicas"][0]["execution"]["planned"] == 2


@pytest.mark.parametrize("level", ["outer", "manifest", "native", "replica_binding"])
def test_every_hierarchical_fingerprint_is_checked(level):
    data = campaign()
    if level == "outer":
        data["fingerprint"] = "0" * 64
    elif level == "manifest":
        data["manifest"]["fingerprint"] = "0" * 64
        seal(data)
    elif level == "native":
        data["replicas"][0]["receipt"]["fingerprint"] = "0" * 64
        seal(data)
    else:
        data["replicas"][0]["manifest_fingerprint"] = "0" * 64
        seal(data)
    with pytest.raises(api.PlanError):
        gate(right=data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", "../escape"),
        ("prompt_sha256", "bad"),
        ("prompt_bytes", 0),
        ("max_output_tokens", True),
        ("arrival_offset_s", -1),
    ],
)
def test_descriptor_validation_does_not_depend_on_any_native_receipt(field, value):
    data = incomplete(campaign(), index=0, failed=True)
    data["manifest"]["ordered_descriptors"][0][field] = value
    reseal(data)
    with pytest.raises(api.PlanError):
        gate(right=data)


@pytest.mark.parametrize("stop", ["caller_stop", "campaign_deadline"])
def test_valid_stop_before_any_execution_retains_every_declared_slot(stop):
    data = campaign()
    for slot in data["replicas"]:
        slot.update(
            state="not_started", receipt=None, error=None, start_s=None, end_s=None, reason=stop
        )
    data["execution"].update(completed=0, not_started=3)
    data.update(state="incomplete", exit_code=1, stop_reason=stop)
    reseal(data)
    result = gate(right=data).to_dict()
    assert result["exit_code"] == 3 and len(result["pairs"]) == 3
    assert all(slot["receipt"] is None for slot in result["inputs"]["candidate"]["replicas"])


def test_full_sixteen_replica_4096_request_population_is_admitted():
    left = campaign(durations=tuple(0.12 + i / 1000 for i in range(16)), count=256)
    right = campaign(durations=tuple(0.09 + i / 1000 for i in range(16)), count=256)
    result = gate(left, right, expected_replicates=16).to_dict()
    assert result["exit_code"] == 0 and len(result["pairs"]) == 16
    assert result["inputs"]["baseline"]["population"]["total_requests"] == 4096


@pytest.mark.parametrize("role", ["campaign", "policy"])
@pytest.mark.parametrize(
    "raw", [b'{"PRIVATE DIAGNOSTIC":1,"PRIVATE DIAGNOSTIC":2}', b'{"x":1e999}', b"[]", b"NaN"]
)
def test_strict_json_refusals_do_not_reflect_arbitrary_field_names(tmp_path, role, raw):
    from chimeraforge.bench.trace_campaign_gate import gate_trace_campaigns

    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(api.PlanError) as error:
        gate_trace_campaigns(
            path if role == "campaign" else campaign(),
            campaign(),
            policy=path if role == "policy" else {"expected_replicates": 3},
        )
    assert "PRIVATE DIAGNOSTIC" not in str(error.value)


def test_relabelled_ids_do_not_create_semantic_execution_evidence():
    data = campaign()
    data["manifest"]["workload"]["canonical_sha256"] = "e" * 64
    for descriptor in data["manifest"]["ordered_descriptors"]:
        descriptor["request_id"] = "renamed-" + descriptor["request_id"]
    for slot in data["replicas"]:
        native = slot["receipt"]
        native["workload"]["canonical_sha256"] = "e" * 64
        slot["workload_ref"] = "e" * 64
        for row, descriptor in zip(native["requests"], data["manifest"]["ordered_descriptors"]):
            row["descriptor"] = copy.deepcopy(descriptor)
    reseal(data)
    result = gate(right=data).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]


@pytest.mark.parametrize(
    "mutation",
    ["origin_before", "origin_after", "overlapping_native", "end_overshoot", "zero_slot"],
)
def test_native_clock_interval_must_fit_its_enclosing_serial_slot(mutation):
    data = campaign(durations=(0.10, 0.11, 0.09))
    slot = data["replicas"][1 if mutation == "overlapping_native" else 0]
    native = slot["receipt"]
    origin = data["clock"]["origin"]
    if mutation == "origin_before":
        native["clock"]["origin"] = origin + slot["start_s"] - 0.1
        native["clock"]["resolution_seconds"] = 1000000.0
    elif mutation == "origin_after":
        native["clock"]["origin"] = origin + slot["end_s"] + 0.1
    elif mutation == "overlapping_native":
        native["clock"]["origin"] = origin + 0.2
    elif mutation == "end_overshoot":
        native["clock"]["origin"] = origin + slot["end_s"] - 0.05
    else:
        slot["end_s"] = slot["start_s"]
        native["clock"]["origin"] = origin + slot["start_s"]
    reseal(data)
    with pytest.raises(api.PlanError):
        gate(right=data)


def test_native_clock_binding_allows_float_roundoff_at_large_epoch():
    data = campaign(durations=(0.10, 0.11, 0.09))
    data["clock"]["origin"] = float(2**30)
    for slot in data["replicas"]:
        slot["receipt"]["clock"]["origin"] = data["clock"]["origin"] + slot["start_s"] + 0.1
    slot = data["replicas"][0]
    native = slot["receipt"]
    observed_end = (
        native["clock"]["origin"] - data["clock"]["origin"] + native["execution"]["elapsed_seconds"]
    )
    slot["end_s"] = math.nextafter(observed_end, -math.inf)
    reseal(data)
    assert gate(right=data).to_dict()["exit_code"] == 0


def test_absent_native_origin_remains_unavailable_not_invented():
    data = incomplete(campaign())
    native = data["replicas"][1]["receipt"]
    native["clock"]["origin"] = None
    native["execution"]["elapsed_seconds"] = None
    finish(native)
    reseal(data)
    result = gate(right=data).to_dict()
    assert result["exit_code"] == 3
    assert result["inputs"]["candidate"]["replicas"][1]["receipt"]["clock_origin_observed"] is False


def test_campaign_signed_zero_copy_is_duplicate_execution_payload():
    data = campaign(durations=(0.10, 0.11, 0.09))
    copied = copy.deepcopy(data["replicas"][0]["receipt"])
    copied["clock"]["origin"] = data["clock"]["origin"] + data["replicas"][1]["start_s"] + 0.1
    for row in copied["requests"]:
        row["times"]["arrival_s"] = -0.0
    data["replicas"][1]["receipt"] = copied
    reseal(data)
    result = gate(right=data).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]
