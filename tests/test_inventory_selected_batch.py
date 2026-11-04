"""Selected memory is a modeled per-device estimate, never deployment readiness."""

import asyncio
from decimal import Inexact, Rounded, ROUND_DOWN, ROUND_UP, localcontext
import hashlib
import json
from pathlib import Path
import sys

import pytest
from typer.testing import CliRunner

from chimeraforge import api, inventory_process
from chimeraforge.cli import app
from chimeraforge.planner.models import VRAMModel


def native_qwen(
    tmp_path,
    context_length=8192,
    *,
    tp=2,
    pp=1,
    rate=16,
    kv_quant="fp16",
    allow_offload=False,
    lora_adapters=0,
):
    fixture = Path(__file__).parent / "fixtures/hybrid_configs/Qwen_Qwen2.5-1.5B-Instruct.json"
    config = json.loads(fixture.read_text(encoding="utf-8"))
    assert config["use_sliding_window"] is False
    saved = api.plan(
        api.PlanRequest(
            models=["ci/archived-qwen-geometry"],
            overrides={
                "params_b": 1.5,
                "n_layers": config["num_hidden_layers"],
                "n_kv_heads": config["num_key_value_heads"],
                "d_head": config["hidden_size"] // config["num_attention_heads"],
                "hidden_size": config["hidden_size"],
            },
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=tp,
            pipeline_parallel=pp,
            kv_quant=kv_quant,
            allow_offload=allow_offload,
            lora_adapters=lora_adapters,
            context_length=context_length,
            request_rate=rate,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    index = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16"
    )
    target = tmp_path / "native-plan.json"
    saved.save(target)
    loaded = api.load_plan(target)
    assert loaded.to_dict() == saved.to_dict()
    row = loaded.candidate(index)
    assert (row.tensor_parallel, row.pipeline_parallel, row.gpus_total) == (
        tp,
        pp,
        row.n_agents * tp * pp,
    )
    return loaded, index, target


def owned_inventory(monkeypatch, free="4100", total="6000"):
    raw = "".join(
        f"{i}, GPU-{i:08x}-1111-2222-3333-444444444444, controlled, {total}, {free}, 595.00, N/A\n"
        for i in (0, 1)
    ).encode()
    monkeypatch.setattr(
        inventory_process,
        "COMMAND",
        (sys.executable, "-B", "-c", f"import sys;sys.stdout.buffer.write({raw!r})"),
    )


def test_archived_qwen_actual_native_save_load_and_literal_784_mib_positive(tmp_path, monkeypatch):
    saved, index, path = native_qwen(tmp_path)
    spec = saved.spec(saved.candidate(index).model)
    assert (spec.n_layers, spec.n_kv_heads, spec.d_head) == (28, 2, 128)
    actual = (
        VRAMModel.kv_cache_gb(spec.arch(), 8192, 8, kv_bytes=2)
        - VRAMModel.kv_cache_gb(spec.arch(), 8192, 1, kv_bytes=2)
    ) / 2
    assert actual * 1024 == 784
    owned_inventory(monkeypatch)
    baseline = asyncio.run(api.check_inventory(path, candidate_index=index, gpu_devices=["0", "1"]))
    assert baseline.exit_code == 0
    assert baseline.baseline.saved_effective_batch == 8
    assert len(baseline.slots) == 2
    assert baseline.observation.cleanup_state == "completed"
    assert baseline.deployment_ready is None


def test_selected_batch_changes_native_b1_pass_to_selected_shortfall(tmp_path, monkeypatch):
    _, index, path = native_qwen(tmp_path)
    owned_inventory(monkeypatch)
    result = asyncio.run(
        api.check_inventory(
            path, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 5
    assert result.baseline.per_sequence_increment_gib == "0.109375"
    assert result.baseline.selected_lower_gib == "4.380625"
    assert result.baseline.selected_upper_gib == "4.390625"
    assert [p.free_comparison for p in result.slots] == ["below_selected_batch_estimate"] * 2
    assert result.deployment_ready is None


def test_cli_selected_basis_reports_shortfall_against_selected_not_original_b1(
    tmp_path, monkeypatch
):
    _, index, path = native_qwen(tmp_path)
    owned_inventory(monkeypatch)
    result = CliRunner().invoke(
        app,
        [
            "inventory-check",
            "--plan",
            str(path),
            "--candidate-index",
            str(index),
            "--gpu-device",
            "0",
            "--gpu-device",
            "1",
            "--memory-basis",
            "selected-batch",
            "--json",
        ],
    )
    assert result.exit_code == 5, result.output
    data = json.loads(result.stdout)
    assert data["baseline"]["saved_effective_batch"] == 8
    assert data["baseline"]["selected_lower_gib"] == "4.380625"
    assert data["slots"][0]["free_comparison"] == "below_selected_batch_estimate"


@pytest.mark.parametrize(
    "free,expected", [("4506.335704", 0), ("4506.335703", 4), ("4496.095703", 5)]
)
def test_context8193_exact_selected_bounds_do_not_reenter_six_digit_source_parser(
    tmp_path, monkeypatch, free, expected
):
    saved, index, path = native_qwen(tmp_path, context_length=8193)
    assert saved.candidate(index).vram_gb == 3.63
    owned_inventory(monkeypatch, free)
    result = asyncio.run(
        api.check_inventory(
            path, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == expected
    assert result.baseline.per_sequence_increment_gib == "0.1093883514404296875"
    assert result.baseline.selected_lower_gib == "4.3907184600830078125"
    assert result.baseline.selected_upper_gib == "4.4007184600830078125"


def test_full_saved_swa_fact_refuses_even_when_native_arch_omits_it(tmp_path, monkeypatch):
    saved, index, _ = native_qwen(tmp_path)
    data = saved.to_dict()
    model = saved.candidate(index).model
    data["result"]["specs"][model]["sliding_window"] = 1024
    spec = data["result"]["specs"][model]
    data["result"]["replay_context"]["model_specs"][model] = dict(spec)
    # Adversarial internally matching declaration is not producer authentication.
    formula = data["result"]["candidates"][index]["provenance"]["vram"].get("memory_formula")
    if formula is not None:
        formula["spec_sha256"] = api._digest(spec)
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    edited = api.artifact_from_dict(data)
    assert "swa_window" not in edited.spec(model).arch()

    async def forbidden(*args, **kwargs):
        pytest.fail("unsupported saved SWA contacted inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            edited, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 4 and len(result.slots) == 2
    assert result.observation.state == "not_started"


@pytest.mark.parametrize("tp,pp", [(1, 2), (3, 1), (4, 1)])
def test_real_native_unsupported_parallel_geometry_keeps_all_slots_without_query(
    tmp_path, monkeypatch, tp, pp
):
    saved, index, _ = native_qwen(tmp_path, tp=tp, pp=pp)

    async def forbidden(*args, **kwargs):
        pytest.fail("unsupported parallel geometry queried inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            saved,
            candidate_index=index,
            gpu_devices=[str(i) for i in range(tp * pp)],
            memory_basis="selected-batch",
        )
    )
    assert result.exit_code == 4 and len(result.slots) == tp * pp
    assert result.observation.state == "not_started"


@pytest.mark.parametrize("tp,expected", [(1, "0.21875"), (2, "0.109375")])
def test_native_whole_head_division_uses_each_original_device(tmp_path, monkeypatch, tp, expected):
    saved, index, _ = native_qwen(tmp_path, tp=tp)
    owned_inventory(monkeypatch, "100000", "100000")
    result = asyncio.run(
        api.check_inventory(
            saved,
            candidate_index=index,
            gpu_devices=[str(i) for i in range(tp)],
            memory_basis="selected-batch",
        )
    )
    assert result.exit_code == 0
    assert result.baseline.per_sequence_increment_gib == expected
    assert len(result.slots) == tp


def test_genuine_native_fleet_retains_all_original_selected_rows(tmp_path, monkeypatch):
    saved, index, _ = native_qwen(tmp_path, rate=128)
    assert saved.candidate(index).n_agents == 3
    groups = [["7", "3"], ["9", "2"], ["8", "4"]]
    raw = "".join(
        f"{i}, GPU-{int(i):08x}-1111-2222-3333-444444444444, "
        "controlled, 100000, 100000, 595.00, N/A\n"
        for group in groups
        for i in group
    ).encode()
    monkeypatch.setattr(
        inventory_process,
        "COMMAND",
        (sys.executable, "-B", "-c", f"import sys;sys.stdout.buffer.write({raw!r})"),
    )
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, replica_gpu_devices=groups, memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 0 and len(result.slots) == 6
    assert [(slot.replica_index, slot.device_index, slot.selector) for slot in result.slots] == [
        (r, p, value) for r, group in enumerate(groups) for p, value in enumerate(group)
    ]
    assert result.observation.cleanup_state == "completed"


@pytest.mark.parametrize("free,expected", [("N/A", 4), ("4485.76", 4), ("5000", 0)])
def test_selected_per_device_unknown_overlap_and_pass(tmp_path, monkeypatch, free, expected):
    saved, index, _ = native_qwen(tmp_path)
    owned_inventory(monkeypatch, free)
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == expected and len(result.slots) == 2
    assert result.slots[0].device.memory_free_mib == (None if free == "N/A" else free)


def test_selected_human_text_explains_b1_pass_but_selected_shortfall(tmp_path, monkeypatch):
    _, index, path = native_qwen(tmp_path)
    owned_inventory(monkeypatch)
    result = CliRunner().invoke(
        app,
        [
            "inventory-check",
            "--plan",
            str(path),
            "--candidate-index",
            str(index),
            "--gpu-device",
            "0",
            "--gpu-device",
            "1",
            "--memory-basis",
            "selected-batch",
        ],
    )
    assert result.exit_code == 5
    assert "Selected batch B=8, context=8192: 4.380625..4.390625" in result.stdout
    assert "Original saved B1: 3.615..3.625" in result.stdout
    assert "below_selected_batch_estimate" in result.stdout


def test_invalid_memory_mode_is_logical_input_error_before_loading_or_query(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("invalid memory basis queried inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    with pytest.raises(api.InventoryCheckError):
        asyncio.run(
            api.check_inventory("does-not-exist.json", gpu_devices=["0"], memory_basis="unknown")
        )
    result = CliRunner().invoke(
        app,
        [
            "inventory-check",
            "--plan",
            "does-not-exist.json",
            "--gpu-device",
            "0",
            "--memory-basis",
            "unknown",
            "--json",
        ],
    )
    assert result.exit_code == 1 and json.loads(result.stdout)["outcome"] == "invalid"
    assert json.loads(result.stdout)["error"] == (
        "Invalid inventory memory basis; choose batch-one or selected-batch."
    )


def legacy_saved():
    path = Path(__file__).parent / "fixtures/inventory/legacy086-qwen-b8.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "33dd39c068be999b66566f336677c489a6af183fc99c3c2d3b0e24035ed57212"
    )
    saved = api.load_plan(path)
    index = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16"
    )
    assert saved.to_dict()["tool"]["version"] == "0.86.0"
    return saved, index


def test_same_actual_legacy_plan_default_and_explicit_batch_one_output_and_query_parity(
    monkeypatch,
):
    saved, index = legacy_saved()
    device = api.InventoryDevice(
        "0",
        "GPU-00000000-1111-2222-3333-444444444444",
        "controlled",
        "6000",
        "4100",
        "595.00",
        "N/A",
    )
    second = api.InventoryDevice(
        "1",
        "GPU-00000001-1111-2222-3333-444444444444",
        "controlled",
        "6000",
        "4100",
        "595.00",
        "N/A",
    )
    observation = api.InventoryObservation(
        "complete",
        ("controlled",),
        returncode=0,
        devices=(device, second),
        cleanup_state="completed",
    )
    calls = []

    async def fixed(timeout):
        calls.append(timeout)
        return observation

    monkeypatch.setattr(inventory_process, "observe", fixed)
    default = asyncio.run(api.check_inventory(saved, candidate_index=index, gpu_devices=["0", "1"]))
    explicit = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="batch-one"
        )
    )
    assert calls == [10.0, 10.0]
    assert default.to_dict() == explicit.to_dict()
    assert default.exit_code == 0
    assert default.to_dict()["schema_version"] == 1
    assert set(default.to_dict()["baseline"]) == {
        "saved_gib",
        "lower_gib",
        "upper_gib",
        "basis",
        "saved_effective_batch",
        "reason",
    }


def test_actual_legacy_selected_refuses_before_spec_registry_models_or_query(monkeypatch):
    saved, index = legacy_saved()
    before = saved.to_dict()

    def forbidden(*args, **kwargs):
        pytest.fail("legacy selected mode resolved or queried a source")

    from chimeraforge.planner import models

    monkeypatch.setattr(api.PlanArtifact, "spec", forbidden)
    monkeypatch.setattr(models, "load_models", forbidden)
    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 4 and result.baseline.reason == "producing_formula_unavailable"
    assert len(result.slots) == 2 and result.observation.state == "not_started"
    assert saved.to_dict() == before


def test_genuine_producer_does_not_declare_foreign_calculator_implementation(tmp_path, monkeypatch):
    original = VRAMModel.predict

    def changed(self, *args, **kwargs):
        return original(self, *args, **kwargs)

    monkeypatch.setattr(VRAMModel, "predict", changed)
    saved, index, _ = native_qwen(tmp_path)
    assert "memory_formula" not in saved.candidate(index).provenance["vram"]

    async def forbidden(*args, **kwargs):
        pytest.fail("unknown producing function queried inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 4 and result.observation.state == "not_started"


def test_native_actual_kv_element_size_must_match_supported_formula_profile(tmp_path, monkeypatch):
    from chimeraforge.planner import engine

    monkeypatch.setitem(engine.KV_QUANT_BYTES, "fp16", 1.0)
    saved, index, _ = native_qwen(tmp_path)

    async def forbidden(*args, **kwargs):
        pytest.fail("unqualified native KV element size queried inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 4 and result.observation.state == "not_started"


def test_genuine_native_offline_approximation_refuses_before_any_inventory_query(
    tmp_path, monkeypatch
):
    from chimeraforge.planner.resolver import SOURCE_REGISTRY_APPROX

    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "empty-native-cache"))
    saved = api.plan(
        api.PlanRequest(
            models=["llama3.2:1b"],
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=16,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    index = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16"
    )
    assert saved.spec(saved.candidate(index).model).source == SOURCE_REGISTRY_APPROX
    assert saved.candidate(index).provenance["vram"] == "estimated"
    path = tmp_path / "actual-native-approximation.json"
    saved.save(path)

    async def forbidden(*args, **kwargs):
        pytest.fail("approximate native geometry reached inventory query")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            path, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 4
    assert result.baseline.reason == "approximate_geometry_unsupported"
    assert result.observation.state == "not_started" and len(result.slots) == 2


def test_claimed_matching_formula_cannot_override_explicit_approximate_geometry(
    tmp_path, monkeypatch
):
    from chimeraforge.planner.resolver import SOURCE_REGISTRY_APPROX

    saved, index, _ = native_qwen(tmp_path)
    data = saved.to_dict()
    row = data["result"]["candidates"][index]
    spec = data["result"]["specs"][row["model"]]
    spec["source"] = SOURCE_REGISTRY_APPROX
    data["result"]["replay_context"]["model_specs"][row["model"]] = dict(spec)
    # An adversarial claimed declaration, NOT output from the approximate producer.
    row["provenance"]["vram"]["memory_formula"]["spec_sha256"] = api._digest(spec)
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    edited = api.artifact_from_dict(data)

    async def forbidden(*args, **kwargs):
        pytest.fail("claimed marker overrode full saved approximate-source exclusion")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            edited, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 4 and result.observation.state == "not_started"


@pytest.mark.parametrize(
    "key,value",
    [
        ("version", True),
        ("calculator", "foreign-formula"),
        ("selected_batch", 1),
        ("context_length", 8193),
        ("kv_bytes", "1"),
        ("tensor_parallel", True),
        ("saved_b1_gib", "3.61"),
        ("spec_sha256", "0" * 64),
        ("architecture_sha256", "0" * 64),
        ("unrecognized", 1),
    ],
)
def test_claimed_formula_must_match_all_held_controls_and_exact_types(
    tmp_path, monkeypatch, key, value
):
    saved, index, _ = native_qwen(tmp_path)
    data = saved.to_dict()
    data["result"]["candidates"][index]["provenance"]["vram"]["memory_formula"][key] = value
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    edited = api.artifact_from_dict(data)

    async def forbidden(*args, **kwargs):
        pytest.fail("inconsistent/foreign producing declaration contacted inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            edited, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 4 and result.baseline.reason == "producing_formula_unavailable"
    assert len(result.slots) == 2 and result.observation.state == "not_started"


@pytest.mark.parametrize("rounding", [ROUND_DOWN, ROUND_UP])
def test_selected_fraction_and_serialization_ignore_hostile_decimal_context(
    tmp_path, monkeypatch, rounding
):
    saved, index, _ = native_qwen(tmp_path, context_length=8193)
    owned_inventory(monkeypatch, free="4506.335704")
    with localcontext() as context:
        context.prec, context.rounding = 2, rounding
        context.Emax, context.Emin = 2, -2
        context.traps[Inexact] = context.traps[Rounded] = True
        before = context.copy()
        result = asyncio.run(
            api.check_inventory(
                saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
            )
        )
        json.dumps(result.to_dict(), allow_nan=False)
        assert context.prec == before.prec and context.traps == before.traps
        assert context.rounding == before.rounding
    assert result.exit_code == 0
    assert result.baseline.selected_upper_gib == "4.4007184600830078125"


def test_selected_effective_batch_one_adds_exactly_zero(tmp_path, monkeypatch):
    saved, index, _ = native_qwen(tmp_path, rate=1)
    assert saved.candidate(index).effective_batch == 1
    owned_inventory(monkeypatch)
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 0
    assert result.baseline.selected_lower_gib == result.baseline.saved_batch1.lower_gib
    assert result.baseline.selected_upper_gib == result.baseline.saved_batch1.upper_gib


def test_native_q8_uses_the_actual_one_byte_kv_increment(tmp_path, monkeypatch):
    saved, index, _ = native_qwen(tmp_path, kv_quant="q8")
    owned_inventory(monkeypatch, "100000", "100000")
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 0
    assert result.baseline.per_sequence_increment_gib == "0.0546875"


@pytest.mark.parametrize("free,expected", [("5000", 0), ("0", 5), ("N/A", 4)])
def test_selected_total_unavailable_never_fills_or_blocks_free_evidence(
    tmp_path, monkeypatch, free, expected
):
    saved, index, _ = native_qwen(tmp_path)
    owned_inventory(monkeypatch, free, "N/A")
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == expected
    assert all(row.total_comparison == "unknown" for row in result.slots)


def test_malformed_selector_has_priority_over_legacy_unsupported_basis(monkeypatch):
    saved, index = legacy_saved()

    async def forbidden(*args, **kwargs):
        pytest.fail("invalid selected selector contacted inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    with pytest.raises(api.InventoryCheckError):
        asyncio.run(
            api.check_inventory(
                saved, candidate_index=index, gpu_devices=["0"], memory_basis="selected-batch"
            )
        )


def test_cli_legacy_selected_explains_unavailable_bounds_and_keeps_original_b1():
    _, index = legacy_saved()
    result = CliRunner().invoke(
        app,
        [
            "inventory-check",
            "--plan",
            str(Path(__file__).parent / "fixtures/inventory/legacy086-qwen-b8.json"),
            "--candidate-index",
            str(index),
            "--gpu-device",
            "0",
            "--gpu-device",
            "1",
            "--memory-basis",
            "selected-batch",
        ],
    )
    assert result.exit_code == 4
    assert "unavailable (producing_formula_unavailable)" in result.stdout
    assert "None..None" not in result.stdout
    assert "Original saved B1: 3.615..3.625" in result.stdout


@pytest.mark.parametrize(
    "field,value",
    [
        ("kv_lora_rank", 512),
        ("sliding_window", 1024),
        ("recurrent_kind", "linear_attention"),
        ("parallel_hybrid", True),
    ],
)
def test_full_saved_attention_and_state_facts_are_unsupported_despite_claimed_marker(
    tmp_path, monkeypatch, field, value
):
    saved, index, _ = native_qwen(tmp_path)
    data = saved.to_dict()
    row = data["result"]["candidates"][index]
    spec = data["result"]["specs"][row["model"]]
    spec[field] = value
    data["result"]["replay_context"]["model_specs"][row["model"]] = dict(spec)
    row["provenance"]["vram"]["memory_formula"]["spec_sha256"] = api._digest(spec)
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})

    async def forbidden(*args, **kwargs):
        pytest.fail("unsupported full saved attention/state fact queried inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            api.artifact_from_dict(data),
            candidate_index=index,
            gpu_devices=["0", "1"],
            memory_basis="selected-batch",
        )
    )
    assert result.exit_code == 4 and result.observation.state == "not_started"


def test_valid_huge_selected_controls_refuse_before_unbounded_output_or_query(
    tmp_path, monkeypatch
):
    saved, index, _ = native_qwen(tmp_path)
    data = saved.to_dict()
    row = data["result"]["candidates"][index]
    row["effective_batch"] = 2**31 - 1
    data["inputs"]["context_length"] = 2**31 - 1
    formula = row["provenance"]["vram"]["memory_formula"]
    formula["selected_batch"] = row["effective_batch"]
    formula["context_length"] = data["inputs"]["context_length"]
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})

    async def forbidden(*args, **kwargs):
        pytest.fail("out-of-profile selected result queried inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            api.artifact_from_dict(data),
            candidate_index=index,
            gpu_devices=["0", "1"],
            memory_basis="selected-batch",
        )
    )
    assert result.exit_code == 4
    assert result.baseline.reason == "selected_memory_range_unsupported"
    assert len(json.dumps(result.to_dict())) < 10000


@pytest.mark.parametrize("controls", [{"allow_offload": True}, {"lora_adapters": 1}])
def test_genuine_saved_offload_or_lora_controls_remain_unavailable_before_query(
    tmp_path, monkeypatch, controls
):
    saved, index, _ = native_qwen(tmp_path, **controls)

    async def forbidden(*args, **kwargs):
        pytest.fail("unsupported native saved residency controls queried inventory")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = asyncio.run(
        api.check_inventory(
            saved, candidate_index=index, gpu_devices=["0", "1"], memory_basis="selected-batch"
        )
    )
    assert result.exit_code == 4 and result.observation.state == "not_started"
    assert len(result.slots) == 2
