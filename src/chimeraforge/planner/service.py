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
    BATCH_LATENCY_REFUSAL,
    DEFAULT_ELECTRICITY_RATE,
    DEFAULT_KV_QUANT,
    DEFAULT_LATENCY_SLO_MS,
    DEFAULT_LORA_TARGET,
    DEFAULT_PLAN_MODE,
    KV_QUANT_BYTES,
    PLAN_MODE_BATCH,
    PLAN_MODES,
)
from chimeraforge.planner.carbon import grid_intensity
from chimeraforge.planner.engine import (
    Candidate,
    enumerate_candidates,
    find_models_for_size,
    pareto_frontier,
)
from chimeraforge.planner.models import load_effective_models, load_models
from chimeraforge.planner.hardware import AUTO_HARDWARE, get_gpu
from chimeraforge.planner.platform_support import DEFAULT_PLAN_PLATFORM, local_plan_platform
from chimeraforge.planner.qualityfile import aggregate, load_quality_file
from chimeraforge.planner.resolver import ModelSpec, resolve_spec


@dataclass
class PlanResult:
    """Outcome of a plan: candidates plus the resolution/rejection context."""

    candidates: list[Candidate]
    target_models: list[str]
    specs: dict[str, ModelSpec] = field(default_factory=dict)
    trace: list[tuple[str, str, str, str]] = field(default_factory=list)
    frontier: list[Candidate] | None = None
    # The OS the plan targeted (--platform). Engine support is checked against it.
    platform: str = DEFAULT_PLAN_PLATFORM


def _check_mode_targets(
    mode: str, latency_slo: float | None, ttft_slo: float | None, tpot_slo: float | None
) -> None:
    """Refuse a latency target in batch mode, where nothing would enforce it."""
    if mode == PLAN_MODE_BATCH and any(v is not None for v in (latency_slo, ttft_slo, tpot_slo)):
        raise ValueError(BATCH_LATENCY_REFUSAL)


def validate_plan_inputs(
    *,
    request_rate: float,
    avg_tokens: int,
    reasoning_tokens: int,
    prompt_tokens: int,
    prefix_cache_hit_rate: float,
    duty_cycle: float,
    gpu_price_multiplier: float,
    host_bandwidth_gbps: float | None,
    ttft_slo: float | None,
    tpot_slo: float | None,
    electricity_rate: float,
    kv_quant: str,
    latency_slo: float | None,
    context_length: int,
    mode: str = DEFAULT_PLAN_MODE,
) -> None:
    """Reject impossible inputs, raising ValueError with an actionable message.

    Deliberately NOT called by ``run_plan``. The engine clamps out-of-range
    values on purpose so that direct library callers cannot produce nonsense --
    ``tests/test_prefix_cache.py`` and ``tests/test_cost_realism.py`` pin that
    behaviour. This is the check the *user-facing entry points* apply first, so a
    typo is rejected rather than quietly rounded into something plausible.

    The CLI already had its own copy; the MCP tool had none, so ``kv_quant="q3"``
    escaped as an uncaught ``KeyError`` and ``request_rate=-1.0`` returned
    ``ok: true`` with a plan for negative traffic. Shared here so the two surfaces
    cannot drift, and the one an LLM drives is not the unguarded one.
    """
    checks: list[tuple[bool, str]] = [
        (request_rate <= 0, "request_rate must be positive"),
        (avg_tokens <= 0, "avg_output_tokens must be positive"),
        (reasoning_tokens < 0, "reasoning_tokens must be non-negative"),
        (prompt_tokens <= 0, "prompt_tokens must be positive"),
        (
            not 0.0 <= prefix_cache_hit_rate <= 1.0,
            "prefix_cache_hit_rate must be between 0.0 and 1.0",
        ),
        (
            not 0.0 < duty_cycle <= 1.0,
            "duty_cycle must be greater than 0.0 and at most 1.0",
        ),
        (gpu_price_multiplier <= 0, "gpu_price_multiplier must be positive"),
        (
            host_bandwidth_gbps is not None and host_bandwidth_gbps <= 0,
            "host_bandwidth_gbps must be positive",
        ),
        (ttft_slo is not None and ttft_slo <= 0, "ttft_slo must be positive"),
        (tpot_slo is not None and tpot_slo <= 0, "tpot_slo must be positive"),
        (electricity_rate < 0, "electricity_rate must be non-negative"),
        (latency_slo is not None and latency_slo <= 0, "latency_slo must be positive"),
        (context_length <= 0, "context_length must be positive"),
        (mode not in PLAN_MODES, f"mode must be one of: {', '.join(PLAN_MODES)}"),
    ]
    for failed, message in checks:
        if failed:
            raise ValueError(message)
    _check_mode_targets(mode, latency_slo, ttft_slo, tpot_slo)
    if str(kv_quant).lower() not in KV_QUANT_BYTES:
        raise ValueError(f"kv_quant must be one of: {', '.join(KV_QUANT_BYTES)}")


def run_plan(
    *,
    models: list[str] | None = None,
    model_size: str = "3b",
    hardware: str = "RTX 4080 12GB",
    request_rate: float = 1.0,
    latency_slo: float | None = None,
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
    gpu_overrides: dict | None = None,
    platform: str | None = None,
    unified_memory_fraction: float | None = None,
    quality_from: str | None = None,
    max_num_batched_tokens: int | None = None,
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
    grid_region: str | None = None,
    carbon_intensity: float | None = None,
    mode: str = DEFAULT_PLAN_MODE,
    use_contributions: bool = False,
    cloud: str | None = None,
    think_time_s: float | None = None,
    session_turns: int | None = None,
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

    ``latency_slo`` None means the online default (``DEFAULT_LATENCY_SLO_MS``);
    ``mode="batch"`` refuses any latency target with ValueError rather than
    accepting one it would not enforce.
    """
    if mode not in PLAN_MODES:
        raise ValueError(f"mode must be one of: {', '.join(PLAN_MODES)}")
    _check_mode_targets(mode, latency_slo, ttft_slo, tpot_slo)
    if latency_slo is None:
        latency_slo = DEFAULT_LATENCY_SLO_MS
    # Normalise the closed-set inputs before anything consumes them. Validation
    # lowercased only for its membership test and then forwarded the raw string,
    # so `kv_quant="Q4"` passed the check and then missed KV_QUANT_BYTES,
    # silently producing the FP16 plan -- a different VRAM figure with no "KV
    # cache quantized" warning. The CLI lowercased first; the MCP path did not,
    # so the two surfaces disagreed on the same input.
    if isinstance(kv_quant, str):
        kv_quant = kv_quant.lower()
    # Resolved before any work so a bad region fails fast (CarbonError is a ValueError).
    grid = grid_intensity(grid_region, carbon_intensity)

    planner_models = load_models(models_path) if models_path else load_effective_models()

    # The deployment OS. Unset means Linux -- the OS the matrix's GPU rows
    # describe -- unless the plan is for THIS machine (`auto`), whose OS is known.
    if platform is None:
        is_auto = (hardware or "").strip().lower() == AUTO_HARDWARE
        named = None if is_auto else get_gpu(hardware)
        if is_auto:
            platform = local_plan_platform()
        elif named is not None and named.vendor == "apple":
            platform = "macos"  # Apple Silicon runs macOS; its engines are the macOS row
        else:
            platform = DEFAULT_PLAN_PLATFORM

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

    # An external harness's score replaces the bundled composite wholesale. A
    # bad path or an unrecognised file is an error here rather than a silent
    # fallback: the user would otherwise believe their eval was in force.
    quality_override = None
    if quality_from:
        quality_override = aggregate(load_quality_file(quality_from))

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
        gpu_overrides=gpu_overrides,
        platform=platform,
        unified_memory_fraction=unified_memory_fraction,
        quality_override=quality_override,
        max_num_batched_tokens=max_num_batched_tokens,
        workload_cv2=workload_cv2,
        electricity_rate=electricity_rate,
        kv_quant=kv_quant,
        tensor_parallel=tensor_parallel,
        pipeline_parallel=pipeline_parallel,
        lora_adapters=lora_adapters,
        lora_rank=lora_rank,
        lora_target=lora_target,
        grid=grid,
        mode=mode,
        use_contributions=use_contributions,
        cloud=cloud,
        think_time_s=think_time_s,
        session_turns=session_turns,
    )
    frontier = pareto_frontier(candidates) if pareto else None
    return PlanResult(
        candidates=candidates,
        target_models=target_models,
        specs=specs,
        trace=trace,
        frontier=frontier,
        platform=platform,
    )
