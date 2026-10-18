"""Saved plans bind explicit native trace controls without becoming deployment proof."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict
import hashlib
import json
import os

import pytest

from chimeraforge import api
from chimeraforge.bench.backends.base import Backend, GenerationObservation
from chimeraforge.bench.metrics import RunMetrics
from chimeraforge.bench.trace_workload import TraceRequest
from chimeraforge.planner.replay import digest


@pytest.fixture
def saved():
    return api.plan(
        api.PlanRequest(
            allow_network=False,
            budget=100000,
            avg_tokens=4,
            prompt_tokens=8,
            latency_slo=100000,
            ttft_slo=20000,
            tpot_slo=20000,
        )
    )


def rows(cap=4):
    return [
        TraceRequest("first", "PRIVATE prompt alpha", cap, 0),
        TraceRequest("second", "PRIVATE prompt beta", cap, 0.001),
    ]


class ObservedBackend(Backend):
    name = "ollama"

    def __init__(self, saved):
        data = saved.to_dict()
        selected = data["result"]["candidates"][0]
        self.calls = []
        self.contacts = []
        self.closed = False
        self.entered = asyncio.Event()
        self.hold = None
        self.active = 0
        self.prompt_count = 8
        self.output_count = 4
        self.decode_ms = 100
        self.fail = False
        self.before = {
            "backend": selected["backend"],
            "execution_engine": selected["backend"],
            "model": selected["model"].removeprefix("ollama:"),
            "quant": selected["quant"],
            "context_length": data["inputs"]["context_length"],
            "tensor_parallel": selected["tensor_parallel"],
            "pipeline_parallel": selected["pipeline_parallel"],
            "replicas": selected["n_agents"],
            "model_spec": data["result"]["replay_context"]["model_specs"][selected["model"]],
            "hardware": data["result"]["replay_context"]["hardware"]["effective"],
            "version": "fixture",
            "model_digest": "a" * 64,
            "device": "gpu",
            "prefix_cache": False,
            "source": "offline fixture",
            "private_field": "PRIVATE metadata",
        }
        self.after = copy.deepcopy(self.before)
        self.observations = 0

    async def health_check(self):
        self.contacts.append("health")
        return True, ""

    async def check_model(self, model):
        self.contacts.append(model)
        return True, ""

    async def get_version(self):
        return "fixture"

    async def observe_serving(self, model):
        self.observations += 1
        return copy.deepcopy(self.before if self.observations == 1 else self.after)

    async def generate(self, model, prompt, options=None):
        return RunMetrics(4, 40, 2, 102, 2, 100, prompt_tokens=8)

    async def generate_observed(self, model, prompt, options, on_first_output):
        self.active += 1
        self.calls.append((model, prompt, copy.deepcopy(options)))
        self.entered.set()
        try:
            on_first_output()
            if self.hold is not None:
                await self.hold.wait()
            if self.fail:
                raise RuntimeError("PRIVATE generation failure")
            return GenerationObservation(
                {
                    "tokens_generated": self.output_count,
                    "prompt_tokens": self.prompt_count,
                    "eval_duration_ms": self.decode_ms,
                    "ttft_basis": "server-prefill-duration",
                },
                self.decode_ms / self.output_count,
                "server-decode-duration/output-token-count",
            )
        finally:
            self.active -= 1

    async def close(self):
        assert self.active == 0
        self.closed = True


@pytest.fixture
def backend(saved, monkeypatch):
    from chimeraforge.bench import trace

    instance = ObservedBackend(saved)
    monkeypatch.setattr(trace, "get_backend", lambda *args, **kwargs: instance)
    return instance


def module():
    from chimeraforge.bench import plan_trace

    return plan_trace


@pytest.mark.asyncio
async def test_exact_selection_controls_and_native_receipt_are_preserved(saved, backend):
    source = saved.to_dict()
    receipt = await module().replay_plan_trace(saved, rows(), concurrency=2)
    report = receipt.to_dict()
    candidate = source["result"]["candidates"][0]
    assert saved.to_dict() == source and backend.closed
    assert report["kind"] == "chimeraforge.plan-trace"
    assert report["plan"]["fingerprint"] == source["fingerprint"]
    assert report["plan"]["candidate"] == candidate
    assert report["plan"]["candidate_sha256"] == digest(candidate)
    assert report["plan"]["candidate_index"] == 0
    assert report["controls"]["applied"]["concurrency"] == 2
    assert all(call[2] == {"num_predict": 4} for call in backend.calls)
    assert (
        report["controls"]["modeled_unapplied"]["context_length"]
        == source["inputs"]["context_length"]
    )
    assert [row["arrival_offset_s"] for row in report["ordered_descriptors"]] == [0, 0.001]
    native = receipt.native_trace
    assert type(native).__name__ == "TraceReplay" and native.to_dict() == report["native_trace"]
    assert native.to_dict()["workload"]["raw_sha256"] is None
    assert report["exit_code"] == report["native_trace"]["exit_code"] == 0
    assert report["configuration_status"] == "unverified"
    assert "PRIVATE" not in json.dumps(report)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["fingerprint", "candidate", "cap", "mixed_caps", "model", "event"])
async def test_invalid_inputs_are_rejected_before_contact(saved, backend, bad):
    source, workload, options = saved, rows(), {}
    if bad == "fingerprint":
        source = api.PlanArtifact({**saved.to_dict(), "fingerprint": "0" * 64})
    elif bad == "candidate":
        options["candidate_index"] = True
    elif bad == "cap":
        workload = rows(3)
    elif bad == "mixed_caps":
        workload[1] = TraceRequest("second", "PRIVATE prompt", 5, 0)
    elif bad == "model":
        options["model"] = " "
    else:
        options["stop_event"] = object()
    with pytest.raises(api.PlanError):
        await module().replay_plan_trace(source, workload, **options)
    assert not backend.contacts and not backend.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value", [("model", "wrong-model"), ("quant", "FP16"), ("context_length", 8192)]
)
async def test_before_mismatch_survives_matching_after(saved, backend, field, value):
    backend.before[field] = value
    report = (await module().replay_plan_trace(saved, rows())).to_dict()
    assert report["binding"]["after"][field]["state"] == "matched"
    assert report["binding"]["summary"][field]["state"] == "mismatch"
    assert report["exit_code"] == 1 and report["native_trace"]["exit_code"] == 0


@pytest.mark.asyncio
async def test_unknown_before_phase_cannot_become_matched(saved, backend):
    backend.before = {}
    report = (await module().replay_plan_trace(saved, rows())).to_dict()
    assert report["binding"]["after"]["model"]["state"] == "matched"
    assert report["binding"]["summary"]["model"]["state"] == "unavailable"
    assert report["exit_code"] == 0


@pytest.mark.asyncio
async def test_actual_token_lengths_are_separate_from_requested_caps(saved, backend):
    backend.output_count = 2
    report = (await module().replay_plan_trace(saved, rows())).to_dict()
    assert all(call[2] == {"num_predict": 4} for call in backend.calls)
    assert report["binding"]["token_lengths"]["output_tokens"]["state"] == "mismatch"
    assert report["native_trace"]["exit_code"] == 0 and report["exit_code"] == 1
    assert report["slo"]["state"] == "observed_pass"


@pytest.mark.asyncio
async def test_missing_token_count_is_unavailable(saved, backend):
    backend.prompt_count = None
    report = (await module().replay_plan_trace(saved, rows())).to_dict()
    assert report["binding"]["token_lengths"]["prompt_tokens"]["state"] == "unavailable"


@pytest.mark.asyncio
async def test_explicit_alias_is_recorded_without_rewriting_selected_model(saved, backend):
    backend.before["model"] = backend.after["model"] = "served-alias"
    report = (
        await module().replay_plan_trace(saved, rows(), model="ollama:served-alias")
    ).to_dict()
    assert all(call[0] == "served-alias" for call in backend.calls)
    assert report["plan"]["model_override"] == "ollama:served-alias"
    assert report["plan"]["served_model"] == "served-alias"
    assert report["plan"]["candidate"]["model"] == saved.candidate().model
    assert report["binding"]["summary"]["model"]["state"] == "mismatch"


@pytest.mark.asyncio
async def test_raw_input_is_held_once_and_not_forged_into_native_receipt(saved, backend, tmp_path):
    path = tmp_path / "workload.json"
    raw = (json.dumps([asdict(row) for row in rows()], indent=3) + "\n\n").encode()
    path.write_bytes(raw)
    prepared = module()._prepare(saved, path)
    path.write_text("not the original workload")
    report = (await module()._replay_prepared(prepared)).to_dict()
    assert report["workload"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["native_trace"]["workload"]["raw_sha256"] is None
    assert [call[1] for call in backend.calls] == [row.prompt for row in rows()]
    assert path in prepared.protected_paths


@pytest.mark.asyncio
async def test_saved_nonnull_slos_only_and_native_basis_are_retained(saved, backend):
    report = (await module().replay_plan_trace(saved, rows())).to_dict()
    assert report["native_trace"]["targets"] == {
        "latency_ms": 100000,
        "first_output_ms": 20000,
        "tpot_ms": 20000,
    }
    assert report["slo"]["sources"]["tpot_ms"]["unit"] == "ms/token"
    assert report["slo"]["sources"]["first_output_ms"]["unit"] == "ms"
    without = api.plan(
        api.PlanRequest(allow_network=False, budget=100000, avg_tokens=4, prompt_tokens=8)
    )
    report = (await module().replay_plan_trace(without, rows())).to_dict()
    assert all(value is None for value in report["native_trace"]["targets"].values())
    assert report["slo"]["state"] == "not_requested"


@pytest.mark.asyncio
async def test_wrapper_and_native_are_defensive_and_legacy_receiver_rejects_wrapper(
    saved, backend, tmp_path
):
    from chimeraforge.bench.trace_gate_inputs import load_trace
    from chimeraforge.bench.trace_campaign_inputs import load_campaign
    from chimeraforge.bench.gate_inputs import load_receipt

    receipt = await module().replay_plan_trace(saved, rows())
    original = receipt.to_dict()
    native = receipt.native_trace
    native._data["model"] = "changed"
    copy_out = receipt.to_dict()
    copy_out["native_trace"].clear()
    assert receipt.to_dict() == original
    assert (
        load_trace(receipt.native_trace)["fingerprint"] == original["native_trace"]["fingerprint"]
    )
    for receiver in (load_trace, load_campaign, load_receipt):
        with pytest.raises(api.PlanError):
            receiver(original)
    path = tmp_path / "report.json"
    receipt.save(path)
    assert json.loads(path.read_text()) == original


@pytest.mark.asyncio
async def test_held_plan_bundle_members_and_hardlink_output_are_protected(saved, backend, tmp_path):
    from chimeraforge.plan_study import protect_output

    path = tmp_path / "plan.json"
    saved.save(path)
    directory = tmp_path / "bundle"
    bundle = api.create_plan_bundle(path, directory)
    prepared = module()._prepare(bundle, rows())
    assert directory in prepared.protected_paths
    assert {p.name for p in prepared.protected_paths} >= {
        "plan.json",
        "corpus.json",
        "manifest.json",
    }
    alias = tmp_path / "outside-alias.json"
    os.link(directory / "plan.json", alias)
    with pytest.raises(api.PlanError):
        protect_output(alias, prepared.protected_paths)
    assert not backend.contacts
    # Held bytes remain consumable after inventory paths are changed.
    (directory / "manifest.json").write_text("changed")
    receipt = await module()._replay_prepared(prepared)
    assert receipt.to_dict()["plan"]["fingerprint"] == saved.to_dict()["fingerprint"]
    with pytest.raises(api.PlanError):
        receipt.save(alias)


@pytest.mark.asyncio
async def test_stop_event_drains_native_work_and_preserves_incomplete_receipt(saved, backend):
    stop = asyncio.Event()
    backend.hold = asyncio.Event()
    task = asyncio.create_task(module().replay_plan_trace(saved, rows(), stop_event=stop))
    await backend.entered.wait()
    stop.set()
    report = (await task).to_dict()
    assert backend.closed and backend.active == 0
    assert report["status"] == "incomplete" and report["exit_code"] == 1
    assert report["native_trace"]["stop_reason"] == "cancelled"
    assert report["native_trace"]["serving_after"] is None
    assert report["binding"]["summary"]["model"]["state"] == "unavailable"


@pytest.mark.asyncio
async def test_external_cancellation_propagates_after_native_cleanup(saved, backend):
    backend.hold = asyncio.Event()
    task = asyncio.create_task(module().replay_plan_trace(saved, rows()))
    await backend.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert backend.closed and backend.active == 0


@pytest.mark.asyncio
async def test_slo_breach_is_distinct_from_execution_and_binding_exit(saved, backend):
    backend.decode_ms = 100000
    report = (await module().replay_plan_trace(saved, rows())).to_dict()
    assert report["slo"]["state"] == "breach"
    assert report["exit_code"] == report["native_trace"]["exit_code"] == 0
    assert report["configuration_status"] == "unverified"


@pytest.mark.asyncio
async def test_native_generation_failure_remains_full_population(saved, backend):
    backend.fail = True
    report = (await module().replay_plan_trace(saved, rows())).to_dict()
    assert report["exit_code"] == 1 and report["status"] == "incomplete"
    assert len(report["native_trace"]["requests"]) == 2
    assert report["native_trace"]["execution"]["partial"] == 2
    assert report["slo"]["state"] == "incomplete"
    assert "PRIVATE" not in json.dumps(report)


@pytest.mark.asyncio
async def test_prepare_freezes_source_selection_and_typed_population(saved, backend):
    source = saved.to_dict()
    workload = rows()
    prepared = module()._prepare(saved, workload)
    saved._data["inputs"]["prompt_tokens"] = 999
    workload.clear()
    report = (await module()._replay_prepared(prepared)).to_dict()
    assert report["plan"]["fingerprint"] == source["fingerprint"]
    assert report["binding"]["token_lengths"]["prompt_tokens"]["expected"] == 8
    assert len(report["native_trace"]["requests"]) == 2


@pytest.mark.asyncio
async def test_mapped_wrapper_is_observed_without_claiming_engine_match(saved, backend):
    data = saved.to_dict()
    data["result"]["candidates"][0]["backend"] = "llama.cpp"
    data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    mapped = api.artifact_from_dict(data)
    backend.before["backend"] = backend.after["backend"] = "ollama"
    backend.before["execution_engine"] = backend.after["execution_engine"] = None
    report = (await module().replay_plan_trace(mapped, rows())).to_dict()
    assert report["controls"]["applied"]["backend"] == "ollama"
    assert report["plan"]["identity"]["backend"] == "llama.cpp"
    assert report["binding"]["summary"]["backend"]["state"] == "unavailable"
    assert report["binding"]["summary"]["execution_engine"]["state"] == "unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["missing_candidate", "negative_index", "invalid_cap", "corrupt_candidate"]
)
async def test_bad_saved_candidate_cannot_contact_endpoint(saved, backend, change):
    data = saved.to_dict()
    options = {}
    if change == "missing_candidate":
        data["result"]["candidates"] = []
    elif change == "negative_index":
        options["candidate_index"] = -1
    elif change == "invalid_cap":
        data["result"]["candidates"][0]["decode_tokens_per_req"] = 0
    else:
        data["result"]["candidates"][0]["tensor_parallel"] = "private-invalid"
    data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    with pytest.raises(api.PlanError):
        await module().replay_plan_trace(api.PlanArtifact(data), rows(), **options)
    assert not backend.contacts and not backend.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("option", ["model", "base_url"])
async def test_native_receiver_identity_limits_are_checked_before_contact(saved, backend, option):
    value = "x" * 513 if option == "model" else "https://example.test/" + "x" * 4096
    with pytest.raises(api.PlanError):
        await module().replay_plan_trace(saved, rows(), **{option: value})
    assert not backend.contacts


@pytest.mark.asyncio
@pytest.mark.parametrize("first_bad", [True, False], ids=["first-invalid", "first-valid"])
async def test_native_receipt_is_snapshotted_exactly_once(saved, backend, monkeypatch, first_bad):
    from chimeraforge.bench import trace
    from chimeraforge.bench.trace import TraceReplay

    prepared = module()._prepare(saved, rows())
    result = await trace.replay(
        list(prepared.requests),
        model=prepared.served_model,
        backend_name=prepared.backend,
        slos=prepared.slos,
    )
    clean = result.to_dict()
    bad = {**copy.deepcopy(clean), "provider_response": "PRIVATE response"}
    bad["fingerprint"] = digest({k: v for k, v in bad.items() if k != "fingerprint"})
    calls = []

    def changing_snapshot(self):
        calls.append(1)
        corrupt = first_bad if len(calls) == 1 else not first_bad
        return copy.deepcopy(bad if corrupt else clean)

    async def returned_receipt(*args, **kwargs):
        return result

    monkeypatch.setattr(TraceReplay, "to_dict", changing_snapshot)
    monkeypatch.setattr(trace, "replay", returned_receipt)
    if first_bad:
        with pytest.raises(api.PlanError):
            await module()._replay_prepared(prepared)
    else:
        report = (await module()._replay_prepared(prepared)).to_dict()
        assert report["native_trace"] == clean
    assert calls == [1]
