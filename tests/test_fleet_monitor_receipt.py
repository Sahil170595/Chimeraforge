"""Complete native fleet projections have explicit bounded export semantics."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json

import pytest
from typer.testing import CliRunner

from chimeraforge import __version__, api
from chimeraforge.bench import serving
from chimeraforge.cli import app
from chimeraforge.fleet_monitor_types import FleetMonitorError, FleetMonitorReport, FleetSlot
from chimeraforge.monitor import MonitorRequest, evaluate_window
from chimeraforge.monitor_binding import assemble_binding
from test_fleet_monitor import MODEL, make_native_fleet
from test_monitor_slo import pair

JSON_LIMIT = 8 * 1024 * 1024
VERSION_CHARS = 128 * 1024
REQUESTED_WINDOWS = 4


@pytest.fixture(scope="module")
def monitor_source():
    return make_native_fleet()


@pytest.fixture(scope="module")
def monitor_source_one():
    saved = api.plan(
        api.PlanRequest(
            models=[MODEL],
            overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=10,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    indices = {
        row["backend"]: i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] in ("vllm", "sglang")
        and row["quant"] == "FP16"
        and row["n_agents"] == 1
        and row["gpus_total"] == 2
    }
    assert set(indices) == {"vllm", "sglang"}
    return saved, indices


@pytest.fixture(scope="module")
def monitor_source_sixteen():
    saved = api.plan(
        api.PlanRequest(
            models=[MODEL],
            overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=768,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    indices = {
        row["backend"]: i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] in ("vllm", "sglang")
        and row["quant"] == "FP16"
        and row["n_agents"] == 16
        and row["gpus_total"] == 32
    }
    assert set(indices) == {"vllm", "sglang"}
    return saved, indices


def assembled_report(
    monitor_source,
    *,
    version_chars=VERSION_CHARS,
    seconds=1,
    ttft=0.05,
    backend="vllm",
    tpot_slo=None,
    window_count=REQUESTED_WINDOWS,
):
    """Pure native assembly fixture; no HTTP, engine or resource-closure claim."""
    saved, indices = monitor_source
    data = saved.to_dict()
    index = indices[backend]
    candidate = data["result"]["candidates"][index]
    targets = {
        "ttft": "explicit_override",
        "tpot": "explicit_override" if tpot_slo is not None else "not_set",
    }
    first, second = (text.replace("org/model", MODEL) for text in pair(backend, ttft=ttft))
    window = evaluate_window(
        first,
        second,
        backend=backend,
        model=MODEL,
        seconds=seconds,
        ttft_slo=500,
        tpot_slo=tpot_slo,
    )
    snapshot = serving.safe_observation(
        {
            **serving.observation(),
            "backend": backend,
            "model": MODEL,
            "version": "v" * version_chars,
            "quant": "FP16",
            "tensor_parallel": 2,
            "pipeline_parallel": 1,
        }
    )
    slots = []
    for number in range(candidate["n_agents"]):
        url = f"http://fixture.invalid/r{number}/metrics"
        effective = MonitorRequest(
            backend,
            url,
            MODEL,
            ttft_slo=500,
            tpot_slo=tpot_slo,
            interval=1,
            windows=window_count,
        )
        origin = datetime(2026, 10, 30, tzinfo=timezone.utc)
        observations = [
            {**snapshot, "captured_at": (origin + timedelta(seconds=2 * i)).isoformat()}
            for i in range(window_count + 1)
        ]
        windows = [
            replace(window, observed_at=(origin + timedelta(seconds=2 * i + 1)).isoformat())
            for i in range(window_count)
        ]
        binding = assemble_binding(
            data, candidate, index, effective, targets, observations, retain_prefix=True
        )
        slots.append(
            FleetSlot(
                f"r{number}",
                url,
                "complete",
                window.outcome,
                None,
                windows,
                observations,
                binding,
            )
        )
    report = FleetMonitorReport(
        backend,
        MODEL,
        tuple(slots),
        slots[0].binding["plan"],
        targets,
        {
            "requests": 60,
            "max_requests": 256,
            "accepted_body_bytes": 1000000,
            "max_body_bytes": 8 * 1024 * 1024,
            "termination": None,
            "byte_scope": "accepted identity-encoded body chunks; not wire/transport buffers",
        },
        {
            "state": "completed",
            "budget_seconds": 2,
            "allowance_exceeded": False,
            "resources_closed": True,
            "close_errors": 0,
            "owned_pools": 2 * len(slots),
            "closed_pools": 2 * len(slots),
            "joined_endpoint_tasks": len(slots),
        },
        False,
        __version__,
        effective_controls={
            "schema_version": 1,
            "endpoints": [{"id": slot.id, "url": slot.url} for slot in slots],
            "interval": 1,
            "windows": window_count,
            "timeout": 10,
            "observation_seconds": 60,
            "cleanup_seconds": 2,
            "concurrency": 4,
            "max_requests": 256,
            "max_body_bytes": 8 * 1024 * 1024,
            "targets": {"ttft_ms": 500, "tpot_ms": tpot_slo},
            "target_sources": targets,
        },
    )
    assert report.exit_code == {"pass": 0, "breach": 3, "unknown": 4}[window.outcome]
    return report


def test_native_amplified_json_refuses_instead_of_unbounded_projection(monitor_source):
    report = assembled_report(monitor_source)
    # Independent trusted-fixture measurement; the tested export must refuse first.
    assert len(json.dumps(asdict(report)).encode("utf-8")) > JSON_LIMIT
    with pytest.raises(FleetMonitorError, match="export.*limit|JSON.*limit"):
        report.to_dict()


def test_json_export_refusal_precedes_prometheus_publication(monitor_source, tmp_path, monkeypatch):
    report = assembled_report(monitor_source)
    saved, indices = monitor_source
    source = tmp_path / "plan.json"
    saved.save(source)
    original = source.read_bytes()
    sink = tmp_path / "metrics.prom"
    sink.write_bytes(b"existing-sink\n")

    async def observe(*args, **kwargs):
        return report

    monkeypatch.setattr(api, "monitor_fleet", observe)
    args = [
        "monitor-fleet",
        "--from-plan",
        str(source),
        "--candidate-index",
        str(indices["vllm"]),
        "--ttft-slo",
        "500",
        "--json",
        "--prometheus",
        str(sink),
    ]
    for slot in report.slots:
        args += ["--endpoint", f"{slot.id}={slot.url}"]
    result = CliRunner().invoke(app, args)
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert result.exit_code == 4
    assert json.loads(result.stdout).get("error")
    assert "slots" not in json.loads(result.stdout)
    assert sink.read_bytes() == b"existing-sink\n"
    assert source.read_bytes() == original


def test_full_native_save_receive_preserves_projection_and_private_guards(monitor_source, tmp_path):
    report = assembled_report(monitor_source, version_chars=32)
    saved, indices = monitor_source
    source, receipt = tmp_path / "plan.json", tmp_path / "receipt.json"
    saved.save(source)
    report.save(receipt)
    loaded = api.load_fleet_monitor(receipt, source, candidate_index=indices["vllm"])
    assert loaded.exit_code == 0
    assert loaded.to_dict() == report.to_dict()
    assert type(loaded.to_dict()["slots"]) is tuple
    assert loaded.effective_controls["windows"] == REQUESTED_WINDOWS
    original = source.read_bytes()
    with pytest.raises(FleetMonitorError):
        loaded.save(source)
    assert source.read_bytes() == original
    assert "_protected_paths" not in loaded.to_dict()


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "bool_count", "bound", "binding", "extra"]
)
def test_receiving_rejects_actual_population_and_derived_tampering(monitor_source, change):
    report = assembled_report(monitor_source, version_chars=32)
    data = json.loads(report.json_bytes())
    saved, indices = monitor_source
    if change == "missing":
        data["slots"].pop()
    elif change == "duplicate":
        data["slots"][1] = data["slots"][0]
    elif change == "bool_count":
        data["cleanup"]["budget_seconds"] = True
    elif change == "bound":
        data["slots"][0]["windows"][0]["metrics"]["ttft"]["p95_upper_ms"] = 1000
    elif change == "binding":
        data["slots"][0]["binding"]["configuration"]["state"] = "matched"
    else:
        data["unexpected"] = "not admitted"
    with pytest.raises(api.PlanError):
        api.load_fleet_monitor(data, saved, candidate_index=indices["vllm"])


def test_receiving_native_v1_preserves_declared_producer_and_missing_controls(monitor_source):
    report = assembled_report(monitor_source, version_chars=32)
    saved, indices = monitor_source
    data = json.loads(report.json_bytes())
    data["schema_version"] = 1
    data.pop("effective_controls")
    data["monitor_tool_version"] = "0.76.0"
    for slot in data["slots"]:
        slot["binding"]["monitor_tool_version"] = "0.76.0"
    loaded = api.load_fleet_monitor(data, saved, candidate_index=indices["vllm"])
    assert loaded.schema_version == 1 and loaded.effective_controls is None
    assert loaded.monitor_tool_version == "0.76.0"
    assert all(slot.binding["monitor_tool_version"] == "0.76.0" for slot in loaded.slots)
    assert "effective_controls" not in loaded.to_dict()


def test_exact_encoded_limit_unicode_escaping_and_lf(monkeypatch):
    from chimeraforge import fleet_monitor_json as formatter

    value = {"text": "snowman:\u2603\\\n$"}
    expected = (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()
    monkeypatch.setattr(formatter, "MAX_FLEET_JSON_BYTES", len(expected))
    assert formatter.encode_public(value) == expected
    monkeypatch.setattr(formatter, "MAX_FLEET_JSON_BYTES", len(expected) - 1)
    with pytest.raises(FleetMonitorError):
        formatter.encode_public(value)


def test_rich_native_python_projection_preserves_old_asdict_container_types(monitor_source):
    from chimeraforge.fleet_monitor_json import public_projection
    from chimeraforge.planner.hardware import GPUSpec
    from chimeraforge.planner.resolver import ModelSpec

    report = assembled_report(monitor_source, version_chars=32)
    rich = serving.safe_observation(
        {
            "hardware": asdict(GPUSpec("fixture", 24, 1000, 0, memory_options_gb=(24, 48))),
            "model_spec": asdict(ModelSpec(MODEL, 3, 28, 8, 128)),
        }
    )
    report.slots[0].observations[0].update(rich)
    expected = asdict(report)
    expected.pop("_protected_paths")
    expected.pop("_received_raw")
    public = public_projection(report)
    expected.update(
        {name: public[name] for name in ("declared_coverage", "exit_code", "outcome", "limits")}
    )
    actual = report.to_dict()

    def shape(value):
        if isinstance(value, dict):
            return (dict, {key: shape(item) for key, item in value.items()})
        if isinstance(value, (list, tuple)):
            return (type(value), [shape(item) for item in value])
        return type(value)

    assert actual == expected and shape(actual) == shape(expected)
    assert type(actual["slots"][0]["observations"][0]["hardware"]["memory_options_gb"]) is list


def test_in_limit_compact_legacy_loads_whole_typed_report_even_if_pretty_export_refuses(
    monitor_source, tmp_path
):
    from chimeraforge.fleet_monitor_json import LIMITS

    def compact(chars):
        report = assembled_report(monitor_source, version_chars=chars)
        data = asdict(replace(report, schema_version=1, effective_controls=None))
        data.pop("_protected_paths")
        data.pop("_received_raw")
        data.pop("effective_controls")
        data.update(
            {
                "declared_coverage": {"expected": 3, "complete": 3, "state": "complete"},
                "exit_code": 0,
                "outcome": "pass",
                "limits": LIMITS,
            }
        )
        return json.dumps(data, separators=(",", ":")).encode()

    small = compact(32)
    copies = small.count(('"' + "v" * 32 + '"').encode())
    chars = 32 + (JSON_LIMIT - len(small)) // copies
    raw = compact(chars)
    assert len(raw) <= JSON_LIMIT
    path = tmp_path / "compact-legacy.json"
    path.write_bytes(raw)
    saved, indices = monitor_source
    loaded = api.load_fleet_monitor(path, saved, candidate_index=indices["vllm"])
    assert loaded.exit_code == 0 and len(loaded.slots) == 3
    assert all(len(slot.windows) == REQUESTED_WINDOWS for slot in loaded.slots)
    with pytest.raises(FleetMonitorError):
        loaded.to_dict()
    from test_fleet_monitor_gate import policy_for

    baseline = assembled_report(monitor_source, version_chars=32, seconds=2)
    policy = policy_for(baseline, baseline)
    verdict = api.gate_fleet_monitors(
        baseline, path, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    assert verdict.exit_code == 3
    junit = tmp_path / "legacy.xml"
    api.write_fleet_monitor_gate(verdict, junit=junit)
    from xml.etree import ElementTree as ET

    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["tests"] == suite.attrib["errors"] == "25"
    out, paired = tmp_path / "unavailable.json", tmp_path / "paired.xml"
    api.write_fleet_monitor_gate(verdict, out=out, junit=paired)
    assert json.loads(out.read_bytes())["exit_code"] == 3 and paired.exists()
    typed = api.gate_fleet_monitors(
        baseline, loaded, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    assert typed.exit_code == 3
    assert len(typed.to_dict()["inputs"]["candidate"]["slots"]) == 3
    loaded.slots[0].observations[0]["version"] = "changed-after-held-snapshot"
    with pytest.raises(api.PlanError, match="changed"):
        api.gate_fleet_monitors(
            baseline, loaded, baseline_plan=saved, candidate_plan=saved, policy=policy
        )


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), True),
        (("monitor_tool_version",), "unrecognized"),
        (("cancelled",), 0),
        (("budget", "requests"), 0),
        (("budget", "termination"), "invented"),
        (("budget", "accepted_body_bytes"), JSON_LIMIT + 1),
        (("cleanup", "owned_pools"), 0),
        (("cleanup", "closed_pools"), 7),
        (("cleanup", "joined_endpoint_tasks"), 1),
        (("cleanup", "allowance_exceeded"), True),
        (("effective_controls", "windows"), True),
        (("effective_controls", "timeout"), float("inf")),
        (("effective_controls", "target_sources", "ttft"), "saved_request"),
        (("slots", 0, "windows", 0, "seconds"), 0),
        (("slots", 0, "windows", 0, "observed_at"), "2026-10-30T00:00:00"),
        (("slots", 0, "windows", 0, "metrics", "ttft", "samples"), True),
        (("slots", 0, "windows", 0, "metrics", "ttft", "confidence"), "confidence-interval"),
        (("slots", 0, "windows", 0, "metrics", "ttft", "p95_lower_ms"), -1),
    ],
)
def test_native_closed_finite_types_and_outcomes_cannot_be_forged(monitor_source, path, value):
    report = assembled_report(monitor_source, version_chars=32)
    data = json.loads(report.json_bytes())
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    saved, indices = monitor_source
    with pytest.raises(api.PlanError):
        api.load_fleet_monitor(data, saved, candidate_index=indices["vllm"])


@pytest.mark.asyncio
async def test_native_precancelled_producer_loads_all_unstarted_slots(monitor_source, tmp_path):
    import asyncio
    from test_fleet_monitor_gate import policy_for

    saved, indices = monitor_source
    baseline = assembled_report(monitor_source, version_chars=32)
    stop = asyncio.Event()
    stop.set()
    request = api.FleetMonitorRequest(
        tuple(api.FleetEndpoint(slot.id, slot.url) for slot in baseline.slots),
        interval=1,
        windows=REQUESTED_WINDOWS,
        ttft_slo=500,
    )
    report = await api.monitor_fleet(
        saved, request, candidate_index=indices["vllm"], stop_event=stop
    )
    loaded = api.load_fleet_monitor(report, saved, candidate_index=indices["vllm"])
    assert loaded.exit_code == 4 and loaded.budget["requests"] == 0
    assert loaded.cleanup["resources_closed"] and loaded.cleanup["closed_pools"] == 6
    assert [slot.state for slot in loaded.slots] == ["unstarted"] * 3
    policy = policy_for(baseline, baseline)
    gate = api.gate_fleet_monitors(
        baseline, loaded, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    assert gate.exit_code == 3 and len(gate.to_dict()["cases"]) == 24
    api.write_fleet_monitor_gate(gate, junit=tmp_path / "partial.xml")


@pytest.mark.parametrize("entrypoint", ["load", "gate"])
@pytest.mark.parametrize(
    "path",
    [
        ("budget", "requests"),
        ("budget", "max_requests"),
        ("cleanup", "closed_pools"),
        ("cleanup", "joined_endpoint_tasks"),
    ],
)
@pytest.mark.parametrize("mutator", [float, bool])
def test_current_typed_count_mutation_cannot_reuse_old_validated_bytes(
    monitor_source, entrypoint, path, mutator
):
    from test_fleet_monitor_gate import policy_for

    saved, indices = monitor_source
    original = assembled_report(monitor_source, version_chars=32)
    loaded = api.load_fleet_monitor(original, saved, candidate_index=indices["vllm"])
    baseline = assembled_report(monitor_source, version_chars=32, seconds=2)
    policy = policy_for(baseline, original)
    target = getattr(loaded, path[0])
    assert type(target[path[1]]) is int
    target[path[1]] = mutator(target[path[1]])
    with pytest.raises(api.PlanError, match="changed"):
        if entrypoint == "load":
            api.load_fleet_monitor(loaded, saved, candidate_index=indices["vllm"])
        else:
            api.gate_fleet_monitors(
                loaded, baseline, baseline_plan=saved, candidate_plan=saved, policy=policy
            )


def test_untouched_admitted_integer_real_spelling_keeps_typed_interoperability(monitor_source):
    from test_fleet_monitor_gate import policy_for

    saved, indices = monitor_source
    baseline = assembled_report(monitor_source, version_chars=32, seconds=2)
    data = json.loads(assembled_report(monitor_source, version_chars=32).json_bytes())
    metric = data["slots"][0]["windows"][0]["metrics"]["ttft"]
    metric["p95_lower_ms"] = int(metric["p95_lower_ms"])
    loaded = api.load_fleet_monitor(data, saved, candidate_index=indices["vllm"])
    assert type(loaded.slots[0].windows[0].metrics["ttft"].p95_lower_ms) is int
    untouched = api.load_fleet_monitor(loaded, saved, candidate_index=indices["vllm"])
    assert untouched.exit_code == 0
    gate = api.gate_fleet_monitors(
        baseline,
        loaded,
        baseline_plan=saved,
        candidate_plan=saved,
        policy=policy_for(baseline, loaded),
    )
    assert gate.exit_code == 0
