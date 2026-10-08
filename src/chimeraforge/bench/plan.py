"""Bind a measured benchmark to a saved modeled scenario without claiming equivalence."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

from chimeraforge.plan_check import identity
from chimeraforge.planner.replay import digest, json_value

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
MAX_BENCHMARK_REQUESTS = 1000
BACKEND_WRAPPERS = {"llama.cpp": "ollama"}


@dataclass(frozen=True)
class PlanBenchmark:
    _data: dict

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact

        PlanArtifact(self.to_dict()).save(path)


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


def binding(data: dict, candidate: dict, execution: dict, served_model: str) -> dict:
    inputs = data["inputs"]
    context = data["result"].get("replay_context")
    after = execution["serving_after"]
    before = execution["serving_before"]
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
    result["replicas"] = bind(candidate["n_agents"], after.get("replicas"), source=source)
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
    result["model_geometry"] = bind(
        wanted_geometry,
        actual_geometry,
        source=source,
        state="unavailable" if wanted_geometry is None or actual_geometry is None else None,
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
    )
    original = {key: before.get(key) for key in stability_keys}
    current = {key: after.get(key) for key in stability_keys}
    changed = [
        key
        for key in stability_keys
        if original[key] is not None and current[key] is not None and original[key] != current[key]
    ]
    optional_stability = ("configuration_sha256", "weight_version_label")
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
    runs = execution["individual_runs"]
    prompt_counts = [row.get("prompt_tokens") for row in runs]
    output_counts = [row["tokens_generated"] for row in runs]
    result["prompt_tokens"] = bind(
        inputs["prompt_tokens"],
        prompt_counts,
        state="unavailable"
        if any(value is None for value in prompt_counts)
        else "matched"
        if all(value == inputs["prompt_tokens"] for value in prompt_counts)
        else "mismatch",
        source="server-reported prompt token counts",
    )
    result["output_tokens"] = bind(
        candidate["decode_tokens_per_req"],
        output_counts,
        state="matched"
        if all(value == candidate["decode_tokens_per_req"] for value in output_counts)
        else "mismatch",
        source="server-reported generated counts; output cap is not a guaranteed length",
    )
    cache = [row.get("cached_prompt_tokens") for row in runs]
    cache_disabled = after.get("prefix_cache") is False
    cache_observed = all(type(value) is int and value == 0 for value in cache)
    result["prefix_cache"] = bind(
        inputs["prefix_cache_hit_rate"],
        cache,
        state="matched"
        if inputs["prefix_cache_hit_rate"] == 0 and (cache_disabled or cache_observed)
        else "unavailable",
        source="server cache configuration/counters",
        detail="Repeating a prompt can warm caches; an input label cannot prove actual hits.",
    )
    modifiers = {
        "lora_adapters": candidate["lora_adapters"],
        "lora_rank": candidate["lora_rank"],
        "lora_target": inputs["lora_target"] if candidate["lora_adapters"] else None,
        "offload_fraction": candidate["offload_fraction"],
        "host_bandwidth_gbps": candidate["host_bandwidth_gbps"],
    }
    modified = candidate["lora_adapters"] > 0 or candidate["offload_fraction"] > 0
    result["scenario_modifiers"] = bind(
        modifiers,
        None,
        state="unavailable" if modified else "not_used",
        source="saved modeled scenario",
        detail="Runner does not apply/attest LoRA/offload; absence describes the modeled scenario.",
    )
    result["workload"] = bind(
        execution["request"]["workload"],
        execution["request"],
        state="applied",
        source="shared runner effective profile/options",
        detail="A single-stream probe does not execute the selected fleet.",
    )
    return result


def _metric(
    modeled: float | None,
    measured: float | None,
    unit: str,
    *,
    comparable: bool = False,
    modeled_basis: str,
    measured_basis: str,
    blockers: list[str],
) -> dict:
    known = all(
        type(value) in (int, float) and math.isfinite(value) for value in (modeled, measured)
    )
    return {
        "modeled": modeled,
        "measured": measured,
        "unit": unit,
        "raw_delta": measured - modeled if known else None,
        "delta": measured - modeled if known and comparable else None,
        "state": "comparable" if known and comparable else "unverified",
        "modeled_basis": modeled_basis,
        "measured_basis": measured_basis,
        "blocking_facts": blockers,
        "interpretation": "Raw difference is arithmetic, not accuracy or deployment qualification.",
    }


def audit(candidate: dict, measurement: dict, execution: dict, bound: dict) -> dict:
    required = (
        "backend",
        "model",
        "model_geometry",
        "quant",
        "hardware",
        "tensor_parallel",
        "pipeline_parallel",
        "context_length",
        "prompt_tokens",
        "output_tokens",
        "prefix_cache",
        "serving_stability",
    )
    blockers = [
        f"{field}: {bound[field]['state']}"
        for field in required
        if bound[field]["state"] != "matched"
    ]
    request = execution["request"]
    if request["workload"] != "single" or request["concurrency"] != 1:
        blockers.append("base decode comparator requires a single-stream workload")
    if candidate["tensor_parallel"] != 1 or candidate["pipeline_parallel"] != 1:
        blockers.append("saved base decode rate precedes selected TP/PP scaling")
    if execution["failed_count"]:
        blockers.append("failed requests excluded from survivor aggregates")
    if candidate["lora_adapters"] > 0:
        blockers.append("modeled LoRA adapter/rank/target is not observed or applied")
    if candidate["offload_fraction"] > 0:
        blockers.append("modeled CPU offload fraction/host bandwidth is not observed or applied")
    aggregate = measurement["aggregate"]
    observed = aggregate["throughput_tps"]["mean"]
    base = _metric(
        candidate["throughput_tps"],
        observed,
        "tokens/second",
        comparable=not blockers,
        modeled_basis="saved single-stream pre-batch/pre-TP/PP decode rate",
        measured_basis="successful request decode rates from the serving adapter",
        blockers=blockers,
    )
    selected_blockers = [
        "A base decode probe does not qualify selected batching, replicas or deployment hardware."
    ]
    p95_blockers = [
        "Shared runner per-request timing excludes client semaphore queue.",
        "Planner p95 includes modeled queue; serving duration/first-token bases differ.",
    ]
    wall = (
        measurement["aggregate"]["tokens_generated"] / execution["elapsed_seconds"]
        if execution["elapsed_seconds"] > 0
        else None
    )
    metrics = {
        "base_decode_tps": base,
        "fleet_tps": _metric(
            candidate["total_throughput_tps"],
            wall,
            "tokens/second",
            modeled_basis="modeled selected fleet capacity",
            measured_basis="completed tokens / workload wall seconds",
            blockers=selected_blockers,
        ),
        "p95_latency_ms": _metric(
            candidate["p95_latency_ms"],
            aggregate["total_duration_ms"]["p95"],
            "ms",
            modeled_basis="modeled queue-inclusive latency",
            measured_basis="successful adapter request durations",
            blockers=p95_blockers,
        ),
        "ttft_ms": _metric(
            candidate["ttft_ms"],
            aggregate["ttft_ms"]["mean"],
            "ms",
            modeled_basis="modeled prefill/first-token estimate",
            measured_basis=", ".join(
                sorted({row.get("ttft_basis", "unknown") for row in execution["individual_runs"]})
            ),
            blockers=p95_blockers,
        ),
    }
    return {
        "metrics": metrics,
        "selected_configuration": {"state": "unverified", "reasons": selected_blockers},
        "slo": {
            "state": "unverified",
            "reasons": p95_blockers
            + (["partial request coverage"] if execution["failed_count"] else []),
        },
        "weights": {
            "state": "unverified",
            "detail": "The saved ModelSpec lacks immutable model weights/revision binding.",
        },
    }


async def benchmark(
    saved: PlanArtifact | str | Path,
    *,
    candidate_index: int = 0,
    model: str | None = None,
    backend: str | None = None,
    prompt: str | None = None,
    runs: int = 5,
    workload: str = "single",
    rate: float | None = None,
    concurrency: int | None = None,
    base_url: str | None = None,
) -> PlanBenchmark:
    from chimeraforge.api import PlanArtifact, PlanError, artifact_from_dict, load_plan
    from chimeraforge.bench import runner
    from chimeraforge.bench.metrics import result_to_dict, now_iso

    artifact = (
        artifact_from_dict(saved.to_dict()) if isinstance(saved, PlanArtifact) else load_plan(saved)
    )
    data = artifact.to_dict()
    selected = json_value(artifact.candidate(candidate_index))
    if type(runs) is not int or not 1 <= runs <= MAX_BENCHMARK_REQUESTS:
        raise PlanError(f"runs must be between 1 and {MAX_BENCHMARK_REQUESTS}")
    if workload not in ("single", "batch", "server"):
        raise PlanError("workload must be single, batch or server")
    if prompt is not None and (not isinstance(prompt, str) or not prompt):
        raise PlanError("prompt must be a nonempty string")
    for name, value in (("rate", rate), ("concurrency", concurrency)):
        if value is not None and (
            type(value) not in (int, float) or not math.isfinite(value) or value <= 0
        ):
            raise PlanError(f"{name} must be positive and finite")
    if concurrency is not None and type(concurrency) is not int:
        raise PlanError("concurrency must be an integer")
    if workload == "single" and concurrency not in (None, 1):
        raise PlanError("single workload applies concurrency 1")
    if workload != "server" and rate is not None:
        raise PlanError("rate is applied only by the server workload")
    if backend is not None and (not isinstance(backend, str) or not backend.strip()):
        raise PlanError("backend must be a nonempty identifier")
    chosen_backend = backend or BACKEND_WRAPPERS.get(selected["backend"], selected["backend"])
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise PlanError("served model must be a nonempty identifier")
    served_model = (model if model is not None else selected["model"]).removeprefix("ollama:")
    options = {
        "num_predict" if chosen_backend == "ollama" else "max_tokens": selected[
            "decode_tokens_per_req"
        ]
    }
    execution = {}
    result = await runner.run_benchmark(
        model=served_model,
        backend_name=chosen_backend,
        workload=workload,
        runs=runs,
        rate=(rate if rate is not None else data["inputs"]["request_rate"])
        if workload == "server"
        else None,
        context_length=data["inputs"]["context_length"],
        base_url=base_url,
        prompt=prompt,
        options=options,
        concurrency=concurrency,
        _evidence=execution,
    )
    measurement = json_value(result_to_dict(result))
    from chimeraforge.bench.serving import sanitize_message

    measurement["warnings"] = [sanitize_message(row) for row in measurement["warnings"]]
    execution["individual_runs"] = measurement["individual_runs"]
    bound = binding(data, selected, execution, served_model)
    mismatch = any(row["state"] == "mismatch" for row in bound.values())
    report = {
        "schema_version": 1,
        "kind": "chimeraforge.plan-benchmark",
        "created_at": now_iso(),
        "plan": {
            "fingerprint": data["fingerprint"],
            "candidate_index": candidate_index,
            "identity": identity(selected),
            "served_model": served_model,
        },
        "execution": execution,
        "measurement": measurement,
        "binding": bound,
        "audit": audit(selected, measurement, execution, bound),
        "status": "partial" if execution["failed_count"] else "completed",
        "configuration_status": "mismatch" if mismatch else "unverified",
        "exit_code": int(mismatch or bool(execution["failed_count"])),
        "limits": "Endpoint measurements; GPU accuracy, fleet and SLO remain unverified.",
    }
    report = json_value(report)
    report["fingerprint"] = digest(report)
    return PlanBenchmark(report)
