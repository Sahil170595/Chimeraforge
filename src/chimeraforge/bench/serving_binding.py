"""Shared observed serving identity/configuration binding, independent of generated traffic."""

from __future__ import annotations

import math
from typing import Any

GEOMETRY_FIELDS = (
    "params_b",
    "n_layers",
    "n_kv_heads",
    "d_head",
    "hidden_size",
    "vocab_size",
    "num_experts",
    "experts_per_token",
    "moe_intermediate_size",
    "n_dense_layers",
    "kv_lora_rank",
    "qk_rope_head_dim",
    "sliding_window",
    "swa_global_every",
    "n_attention_layers",
    "recurrent_state_bytes_per_seq",
    "recurrent_kind",
    "recurrent_state_dtype_declared",
    "parallel_hybrid",
)
BACKEND_WRAPPERS = {"llama.cpp": "ollama"}
PHYSICAL_HARDWARE_FIELDS = (
    "name",
    "vram_gb",
    "bandwidth_gbps",
    "fp16_tflops",
    "tdp_watts",
    "interconnect_gbps",
    "fp8_supported",
    "tflops_basis",
    "vendor",
    "product_line",
    "unified_memory",
)


def _hardware_known(name: str, value: Any) -> bool:
    if name in ("fp8_supported", "unified_memory"):
        return type(value) is bool
    if name in ("name", "tflops_basis", "vendor", "product_line"):
        return isinstance(value, str) and bool(value)
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _physical(values: Any) -> dict | None:
    if not isinstance(values, dict):
        return None
    return {
        name: values.get(name) if _hardware_known(name, values.get(name)) else None
        for name in PHYSICAL_HARDWARE_FIELDS
    }


def _geometry(spec: Any) -> dict | None:
    if not isinstance(spec, dict):
        return None
    result = {name: spec.get(name) for name in GEOMETRY_FIELDS}

    def absent(names: tuple[str, ...]) -> None:
        for name in names:
            if name in spec and result[name] is None:
                result[name] = 0

    # ModelSpec documents these defaults as dense/standard absence. Missing keys
    # and unknown hidden/vocab dimensions remain unknown, never default-filled.
    if all(name in spec for name in ("num_experts", "experts_per_token")) and not (
        spec["num_experts"] or spec["experts_per_token"]
    ):
        absent(("num_experts", "experts_per_token", "moe_intermediate_size"))
    if "kv_lora_rank" in spec and spec["kv_lora_rank"] is None:
        absent(("kv_lora_rank", "qk_rope_head_dim"))
    absent(("sliding_window",))
    if "n_attention_layers" in spec and spec["n_attention_layers"] is None:
        result["n_attention_layers"] = spec.get("n_layers")
    if (
        "recurrent_kind" in spec
        and spec["recurrent_kind"] is None
        and spec.get("recurrent_state_bytes_per_seq") == 0
    ):
        result["recurrent_kind"] = ""
    return result


def bind(
    expected: Any,
    observed: Any,
    *,
    state: str | None = None,
    source: str | None = None,
    detail: Any = None,
) -> dict:
    return {
        "state": state
        or (
            "unavailable" if observed is None else "matched" if expected == observed else "mismatch"
        ),
        "expected": expected,
        "observed": observed,
        "source": source,
        "detail": detail,
    }


def _observed_model(value: Any, requested: str) -> str | None:
    if not isinstance(value, str):
        return None
    wanted = requested.removeprefix("ollama:")
    if value == wanted or value == wanted + ":latest":
        return wanted
    return value


def _stability(before: dict, after: dict) -> dict:
    stability_keys = (
        "backend",
        "version",
        "model",
        "model_digest",
        "quant",
        "model_spec",
        "context_length",
        "tensor_parallel",
        "pipeline_parallel",
        "replicas",
        "hardware",
        "device",
        "prefix_cache",
        "configuration_sha256",
        "weight_version_label",
        "serving_data_parallel_size",
    )
    original = {key: before.get(key) for key in stability_keys}
    current = {key: after.get(key) for key in stability_keys}
    nested_changes = {}
    nested_missing = {}
    for key, projection in (("hardware", _physical), ("model_spec", _geometry)):
        original[key] = projection(original[key])
        current[key] = projection(current[key])
        old, new = original[key] or {}, current[key] or {}
        names = PHYSICAL_HARDWARE_FIELDS if key == "hardware" else GEOMETRY_FIELDS
        nested_changes[key] = [
            name
            for name in names
            if old.get(name) is not None and new.get(name) is not None and old[name] != new[name]
        ]
        nested_missing[key] = [
            name for name in names if old.get(name) is None or new.get(name) is None
        ]
    changed = [
        key
        for key in stability_keys
        if (
            bool(nested_changes[key])
            if key in nested_changes
            else original[key] is not None
            and current[key] is not None
            and original[key] != current[key]
        )
    ]
    optional_stability = (
        "configuration_sha256",
        "weight_version_label",
        "serving_data_parallel_size",
    )
    required_stability = tuple(key for key in stability_keys if key not in optional_stability)
    missing = [key for key in required_stability if original[key] is None or current[key] is None]
    missing.extend(key for key in nested_missing if nested_missing[key] and key not in missing)
    missing.extend(
        key
        for key in optional_stability
        if (original[key] is not None or current[key] is not None)
        and (original[key] is None or current[key] is None)
    )
    return bind(
        original,
        current,
        state="mismatch" if changed else "unavailable" if missing else "matched",
        source="before/after serving observations",
        detail={
            "changed_fields": changed,
            "unavailable_fields": missing,
            "nested_changed_fields": nested_changes,
            "nested_unavailable_fields": nested_missing,
            "limit": "Lazy-loaded unknown configuration is unverified, not a known change.",
        },
    )


def serving_binding(data: dict, candidate: dict, before: dict, after: dict) -> dict:
    inputs = data["inputs"]
    context = data["result"].get("replay_context")
    source = after.get("source")
    result = {}
    engine = after.get("backend")
    wrapper = (
        candidate["backend"] in BACKEND_WRAPPERS
        and engine == BACKEND_WRAPPERS[candidate["backend"]]
    )
    result["backend"] = bind(
        candidate["backend"],
        engine,
        source=source,
        state="unavailable" if wrapper else None,
        detail="Observed wrapper does not attest the planned execution engine/version."
        if wrapper
        else None,
    )
    result["execution_engine"] = bind(
        candidate["backend"],
        after.get("execution_engine"),
        source=source,
        detail="Serving family/version does not attest an underlying Ollama execution engine.",
    )
    result["model"] = bind(
        candidate["model"].removeprefix("ollama:"),
        _observed_model(after.get("model"), candidate["model"]),
        source=source,
        detail="Serving alias does not prove planned model identity; geometry is separate.",
    )
    result["quant"] = bind(candidate["quant"], after.get("quant"), source=source)
    result["context_length"] = bind(
        inputs["context_length"], after.get("context_length"), source=source
    )
    for field in ("tensor_parallel", "pipeline_parallel"):
        result[field] = bind(candidate[field], after.get(field), source=source)
    result["replicas"] = bind(
        candidate["n_agents"],
        after.get("replicas"),
        source=source,
        detail="Engine DP size does not attest the full endpoint/load-balancer replica topology.",
    )
    result["serving_data_parallel_size"] = bind(
        None,
        after.get("serving_data_parallel_size"),
        state="observed" if after.get("serving_data_parallel_size") is not None else "unavailable",
        source=source,
        detail="Serving engine configuration only; not the saved fleet replica count.",
    )
    hardware = (context or {}).get("hardware", {}).get("effective")
    observed_hw = after.get("hardware")
    if after.get("device") == "cpu" and hardware is not None:
        result["hardware"] = bind(
            hardware,
            {"device": "cpu"},
            state="mismatch",
            source=source,
            detail="CPU execution cannot qualify the modeled GPU configuration.",
        )
    else:
        expected_physical = _physical(hardware)
        observed_physical = _physical(observed_hw)
        hardware_state = "unavailable"
        if expected_physical is not None and observed_physical is not None:
            changed = any(
                _hardware_known(name, expected_physical[name])
                and _hardware_known(name, observed_physical[name])
                and expected_physical[name] != observed_physical[name]
                for name in PHYSICAL_HARDWARE_FIELDS
            )
            missing = any(
                not _hardware_known(name, expected_physical[name])
                or not _hardware_known(name, observed_physical[name])
                for name in PHYSICAL_HARDWARE_FIELDS
            )
            hardware_state = "mismatch" if changed else "unavailable" if missing else "matched"
        result["hardware"] = bind(
            expected_physical,
            observed_physical,
            source=source,
            state=hardware_state,
            detail="Partial agreeing hardware remains unavailable; "
            "price and source dates are not physical geometry. "
            "Client NVML and server GPU-loaded bytes do not establish serving GPU geometry.",
        )
    spec = (context or {}).get("model_specs", {}).get(candidate["model"])
    actual_spec = after.get("model_spec")
    wanted_geometry = _geometry(spec)
    actual_geometry = _geometry(actual_spec)
    geometry_state = "unavailable"
    if wanted_geometry is not None and isinstance(actual_spec, dict):
        changed_geometry = any(
            name in actual_spec
            and wanted_geometry[name] is not None
            and actual_geometry[name] is not None
            and wanted_geometry[name] != actual_geometry[name]
            for name in GEOMETRY_FIELDS
        )
        missing_geometry = any(
            wanted_geometry[name] is None or actual_geometry[name] is None
            for name in GEOMETRY_FIELDS
        )
        geometry_state = (
            "mismatch" if changed_geometry else "unavailable" if missing_geometry else "matched"
        )
    result["model_geometry"] = bind(
        wanted_geometry,
        actual_geometry,
        source=source,
        state=geometry_state,
        detail="Declared dense/standard absence is normalized; "
        "unknown dimensions remain unavailable. "
        "Metadata geometry does not bind an immutable planned weights revision.",
    )
    result["serving_stability"] = _stability(before, after)
    for name, row in result.items():
        row["scope"] = (
            "serving engine configuration; not endpoint/load-balancer fleet"
            if name == "serving_data_parallel_size"
            else "endpoint/load-balancer fleet topology"
            if name == "replicas"
            else "before/after metadata observations"
            if name == "serving_stability"
            else "observed serving configuration versus saved modeled facts"
        )
    return result
