"""Shared planning core: one orchestration path for the CLI and the MCP server.

``run_plan`` loads the effective model corpus, resolves any explicit model ids to
concrete :class:`ModelSpec`s, runs the gate search, and returns a structured
:class:`PlanResult`. It is presentation-free (no Rich/Typer) and raises typed
errors (``ResolverError`` / ``FileNotFoundError`` / ``ValueError``) so each caller
renders them its own way -- the CLI as Rich text, the MCP server as an error result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chimeraforge.planner.constants import (
    DEFAULT_ELECTRICITY_RATE,
    DEFAULT_KV_QUANT,
    DEFAULT_LORA_TARGET,
)
from chimeraforge.planner.engine import (
    Candidate,
    enumerate_candidates,
    find_models_for_size,
    pareto_frontier,
)
from chimeraforge.planner.models import load_effective_models, load_models
from chimeraforge.planner.resolver import ModelSpec, resolve_spec


@dataclass
class PlanResult:
    """Outcome of a plan: candidates plus the resolution/rejection context."""

    candidates: list[Candidate]
    target_models: list[str]
    specs: dict[str, ModelSpec] = field(default_factory=dict)
    trace: list[tuple[str, str, str, str]] = field(default_factory=list)
    frontier: list[Candidate] | None = None


def run_plan(
    *,
    models: list[str] | None = None,
    model_size: str = "3b",
    hardware: str = "RTX 4080 12GB",
    request_rate: float = 1.0,
    latency_slo: float = 5000.0,
    quality_target: float = 0.5,
    budget: float = 100.0,
    avg_tokens: int = 128,
    reasoning_tokens: int = 0,
    prefix_cache_hit_rate: float = 0.0,
    duty_cycle: float = 1.0,
    gpu_price_multiplier: float = 1.0,
    allow_offload: bool = False,
    host_bandwidth_gbps: float | None = None,
    ttft_slo: float | None = None,
    tpot_slo: float | None = None,
    context_length: int = 2048,
    prompt_tokens: int = 512,
    safety_target: float | None = None,
    workload_cv2: float = 0.0,
    electricity_rate: float = DEFAULT_ELECTRICITY_RATE,
    kv_quant: str = DEFAULT_KV_QUANT,
    tensor_parallel: int | None = 1,
    pipeline_parallel: int | None = 1,
    lora_adapters: int = 0,
    lora_rank: int = 16,
    lora_target: str = DEFAULT_LORA_TARGET,
    pareto: bool = False,
    models_path: str | None = None,
    ollama_url: str | None = None,
    hf_token: str | None = None,
    allow_network: bool = True,
    overrides: dict | None = None,
) -> PlanResult:
    """Resolve targets and run the gate search; return a structured result.

    When ``models`` is given, each id is resolved to a :class:`ModelSpec`
    (registry / cache / Ollama / HF / manual overrides), and the search runs over
    exactly those; otherwise it falls back to the registry size-class search on
    ``model_size``. Raises ``ResolverError`` if an id can't be resolved,
    ``FileNotFoundError`` / ``ValueError`` for a bad ``models_path``.
    """
    planner_models = load_models(models_path) if models_path else load_effective_models()

    specs: dict[str, ModelSpec] = {}
    if models:
        overrides = overrides or {}
        for ident in models:
            specs[ident] = resolve_spec(
                ident,
                ollama_url=ollama_url,
                hf_token=hf_token,
                overrides=overrides,
                allow_network=allow_network,
            )
        target_models = list(specs.keys())
    else:
        target_models = find_models_for_size(model_size)

    trace: list = []
    candidates = enumerate_candidates(
        models=planner_models,
        target_models=target_models,
        hardware=hardware,
        request_rate=request_rate,
        latency_slo=latency_slo,
        quality_target=quality_target,
        budget=budget,
        avg_tokens=avg_tokens,
        reasoning_tokens=reasoning_tokens,
        prefix_cache_hit_rate=prefix_cache_hit_rate,
        duty_cycle=duty_cycle,
        gpu_price_multiplier=gpu_price_multiplier,
        allow_offload=allow_offload,
        host_bandwidth_gbps=host_bandwidth_gbps,
        ttft_slo=ttft_slo,
        tpot_slo=tpot_slo,
        context_length=context_length,
        safety_target=safety_target,
        specs=specs,
        trace=trace,
        prompt_tokens=prompt_tokens,
        workload_cv2=workload_cv2,
        electricity_rate=electricity_rate,
        kv_quant=kv_quant,
        tensor_parallel=tensor_parallel,
        pipeline_parallel=pipeline_parallel,
        lora_adapters=lora_adapters,
        lora_rank=lora_rank,
        lora_target=lora_target,
    )
    frontier = pareto_frontier(candidates) if pareto else None
    return PlanResult(
        candidates=candidates,
        target_models=target_models,
        specs=specs,
        trace=trace,
        frontier=frontier,
    )
