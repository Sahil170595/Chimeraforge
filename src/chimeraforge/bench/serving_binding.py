"""Shared observed serving identity/configuration binding, independent of generated traffic."""

from __future__ import annotations

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
        result["hardware"] = bind(
            hardware,
            observed_hw,
            source=source,
            state="unavailable" if hardware is None or observed_hw is None else None,
            detail="Client NVML and server GPU-loaded bytes do not establish serving GPU geometry.",
        )
    spec = (context or {}).get("model_specs", {}).get(candidate["model"])
    actual_spec = after.get("model_spec")
    wanted_geometry = {name: spec[name] for name in GEOMETRY_FIELDS} if spec else None
    actual_geometry = (
        {name: actual_spec.get(name) for name in GEOMETRY_FIELDS}
        if isinstance(actual_spec, dict)
        else None
    )
    geometry_state = "unavailable"
    if wanted_geometry is not None and isinstance(actual_spec, dict):
        changed_geometry = any(
            name in actual_spec
            and actual_geometry[name] is not None
            and wanted_geometry[name] != actual_geometry[name]
            for name in GEOMETRY_FIELDS
        )
        missing_geometry = any(
            name not in actual_spec
            or wanted_geometry[name] is not None
            and actual_geometry[name] is None
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
        detail="Metadata geometry does not bind an immutable planned weights revision.",
    )
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
    changed = [
        key
        for key in stability_keys
        if original[key] is not None and current[key] is not None and original[key] != current[key]
    ]
    optional_stability = (
        "configuration_sha256",
        "weight_version_label",
        "serving_data_parallel_size",
    )
    required_stability = tuple(key for key in stability_keys if key not in optional_stability)
    missing = [key for key in required_stability if original[key] is None or current[key] is None]
    missing.extend(
        key
        for key in optional_stability
        if (original[key] is not None or current[key] is not None)
        and (original[key] is None or current[key] is None)
    )
    result["serving_stability"] = bind(
        original,
        current,
        state="mismatch" if changed else "unavailable" if missing else "matched",
        source="before/after serving observations",
        detail={
            "changed_fields": changed,
            "unavailable_fields": missing,
            "limit": "Lazy-loaded unknown configuration is unverified, not a known change.",
        },
    )
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
