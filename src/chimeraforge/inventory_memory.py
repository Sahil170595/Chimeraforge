"""Selected full-context resident components from a compatible saved B1 intercept."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import math
from typing import TYPE_CHECKING

from chimeraforge.inventory_numbers import decimal_text, number
from chimeraforge.inventory_types import InventoryBaseline, MemoryComparison, SelectedBatchBaseline
from chimeraforge.planner.models import VRAMModel
from chimeraforge.planner.replay import digest
from chimeraforge.planner.resolver import SOURCE_REGISTRY_APPROX

if TYPE_CHECKING:
    from chimeraforge.planner.engine import Candidate
    from chimeraforge.planner.resolver import ModelSpec

FORMULA_ID = "native-resident-b1-kv-affine-v1"
FORMULA_VERSION = 1
MAX_GEOMETRY = 10**6
MAX_SAVED_CONTROL = 2**31 - 1
MAX_SELECTED_GIB = 10**9
BYTES_PER_GIB = 1024**3
KV_BYTES = {"fp16": Fraction(2), "q8": Fraction(1), "q4": Fraction(1, 2)}
_PREDICT = VRAMModel.predict
_CACHE = VRAMModel.kv_cache_gb
_STATE = VRAMModel.recurrent_state_gb
_FIELDS = {
    "version",
    "calculator",
    "saved_b1_gib",
    "selected_batch",
    "context_length",
    "kv_quant",
    "kv_bytes",
    "tensor_parallel",
    "pipeline_parallel",
    "spec_sha256",
    "architecture_sha256",
}


def producing_declaration(
    calculator: VRAMModel,
    spec: ModelSpec | None,
    arch: dict | None,
    *,
    baseline: float,
    batch: int,
    context: int,
    kv_quant: str,
    kv_bytes: float,
    tp: int,
    pp: int,
) -> dict | None:
    """Declare actual native formula use; this is not code or producer authentication."""
    if (
        type(calculator) is not VRAMModel
        or getattr(calculator.predict, "__func__", None) is not _PREDICT
        or calculator.kv_cache_gb is not _CACHE
        or calculator.recurrent_state_gb is not _STATE
        or spec is None
        or arch is None
        or not math.isfinite(baseline)
    ):
        return None
    try:
        saved = decimal_text(number(str(round(baseline, 2))))
        actual_kv_bytes = decimal_text(number(str(kv_bytes)))
    except (ValueError, OverflowError):
        return None
    return {
        "version": FORMULA_VERSION,
        "calculator": FORMULA_ID,
        "saved_b1_gib": saved,
        "selected_batch": batch,
        "context_length": context,
        "kv_quant": kv_quant,
        "kv_bytes": actual_kv_bytes,
        "tensor_parallel": tp,
        "pipeline_parallel": pp,
        "spec_sha256": digest(spec.to_dict()),
        "architecture_sha256": digest(arch),
    }


def selected_baseline(
    candidate: Candidate,
    data: dict,
    original: InventoryBaseline,
) -> tuple[SelectedBatchBaseline, tuple[Fraction, Fraction] | None]:
    """Use held facts only, including refusal paths; never resolve or reload a model."""
    inputs = data["inputs"]
    context = inputs.get("context_length")
    kv_quant = inputs.get("kv_quant")
    quant = kv_quant.lower() if isinstance(kv_quant, str) and kv_quant.lower() in KV_BYTES else None
    result = SelectedBatchBaseline(
        original,
        candidate.effective_batch,
        context,
        quant,
        candidate.tensor_parallel,
        candidate.pipeline_parallel,
    )

    def unavailable(reason: str) -> tuple[SelectedBatchBaseline, None]:
        return replace(result, reason=reason), None

    if original.reason is not None or original.lower_gib is None or original.upper_gib is None:
        return unavailable(original.reason or "saved_baseline_unsupported")
    replay = data["result"].get("replay_context")
    spec = data["result"]["specs"].get(candidate.model)
    if replay is None or spec is None or replay["model_specs"].get(candidate.model) != spec:
        return unavailable("saved_geometry_unavailable")
    if spec.get("source") == SOURCE_REGISTRY_APPROX:
        return unavailable("approximate_geometry_unsupported")
    if (
        candidate.pipeline_parallel != 1
        or candidate.offload_fraction != 0
        or inputs.get("allow_offload")
        or candidate.lora_adapters != 0
        or inputs.get("lora_adapters")
    ):
        return unavailable("saved_residency_controls_unsupported")
    layers, heads, width = (spec.get(key) for key in ("n_layers", "n_kv_heads", "d_head"))
    if any(
        type(value) is not int or not 1 <= value <= MAX_GEOMETRY for value in (layers, heads, width)
    ):
        return unavailable("saved_geometry_unsupported")
    if (
        any(
            spec.get(key) is not None
            for key in ("kv_lora_rank", "qk_rope_head_dim", "sliding_window", "recurrent_kind")
        )
        or spec.get("swa_global_every") != 0
        or spec.get("recurrent_state_bytes_per_seq") != 0
        or spec.get("recurrent_state_dtype_declared") is not False
        or spec.get("parallel_hybrid") is not False
        or spec.get("n_attention_layers") not in (None, layers)
    ):
        return unavailable("saved_attention_shape_unsupported")
    tp = candidate.tensor_parallel
    if tp > heads or heads % tp:
        return unavailable("whole_kv_head_partition_unavailable")
    if quant is None or any(
        type(value) is not int or not 1 <= value <= MAX_SAVED_CONTROL
        for value in (context, candidate.effective_batch)
    ):
        return unavailable("saved_memory_controls_unsupported")
    provenance = candidate.provenance.get("vram")
    formula = provenance.get("memory_formula") if isinstance(provenance, dict) else None
    arch = {
        "n_layers": layers,
        "n_kv_heads": heads,
        "d_head": width,
        "kv_elems_per_token_per_layer": 2 * heads * width,
    }
    expected = {
        "version": FORMULA_VERSION,
        "calculator": FORMULA_ID,
        "saved_b1_gib": original.saved_gib,
        "selected_batch": candidate.effective_batch,
        "context_length": context,
        "kv_quant": quant,
        "kv_bytes": decimal_text(KV_BYTES[quant]),
        "tensor_parallel": tp,
        "pipeline_parallel": 1,
        "spec_sha256": digest(spec),
        "architecture_sha256": digest(arch),
    }
    if (
        not isinstance(formula, dict)
        or set(formula) != _FIELDS
        or any(
            type(formula[key]) is not type(value) or formula[key] != value
            for key, value in expected.items()
        )
    ):
        return unavailable("producing_formula_unavailable")
    increment = (
        Fraction(layers * (heads // tp) * width * 2 * context, BYTES_PER_GIB) * KV_BYTES[quant]
    )
    lower = number(original.lower_gib) + (candidate.effective_batch - 1) * increment
    upper = number(original.upper_gib) + (candidate.effective_batch - 1) * increment
    if upper > MAX_SELECTED_GIB:
        return unavailable("selected_memory_range_unsupported")
    try:
        estimated = replace(
            result,
            per_sequence_increment_gib=decimal_text(increment),
            selected_lower_gib=decimal_text(lower),
            selected_upper_gib=decimal_text(upper),
            status="estimated",
            formula_id=FORMULA_ID,
        )
    except ValueError:
        return unavailable("selected_memory_range_unsupported")
    return estimated, (lower, upper)


def selected_comparison(
    mib: str | None, bounds: tuple[Fraction, Fraction] | None
) -> MemoryComparison:
    """Observe the old bounded source domain, compare exact internal selected bounds."""
    if mib is None or bounds is None:
        return "unknown"
    value = number(mib) / 1024
    if value >= bounds[1]:
        return "at_least_selected_batch_estimate"
    if value < bounds[0]:
        return "below_selected_batch_estimate"
    return "unknown"
