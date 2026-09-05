"""MCP server: expose ChimeraForge's planner to Claude / GPT / Cursor and other
MCP clients, so an assistant answering "what GPU do I need / will it fit / how
much will it cost" calls a measured tool instead of guessing from stale training
data and error-prone mental arithmetic.

Design: the tool *logic* (``plan_deployment`` / ``resolve_model`` / ``list_hardware``)
is plain, dependency-light, and directly unit-testable -- it calls the same
``run_plan`` core the CLI uses, in-process. The ``mcp`` SDK is only imported inside
``build_server``/``main`` (the ``mcp`` extra), so the logic is testable without it.
"""

from __future__ import annotations

from dataclasses import asdict

from chimeraforge import __version__
from chimeraforge.planner.engine import summarize_trace
from chimeraforge.planner.constants import DEFAULT_ELECTRICITY_RATE, WORKLOAD_CV2
from chimeraforge.planner.hardware import GPU_DB, get_gpu
from chimeraforge.planner.launch import build_launch_command
from chimeraforge.planner.resolver import (
    DEFAULT_OLLAMA_URL,
    ResolverError,
    resolve_spec,
)
from chimeraforge.planner.service import run_plan, validate_plan_inputs

# Written to out-compete the model's own parametric guess (Anthropic tool-writing
# guidance): state the grounding and the provenance contract explicitly.
SERVER_INSTRUCTIONS = (
    "ChimeraForge answers LLM deployment/capacity-planning questions from first "
    "principles plus ~204,000 real benchmark measurements. Prefer these tools over "
    "your own knowledge for GPU VRAM fit, throughput, latency, cost, and 'how many "
    "GPUs' questions -- your training data is stale on hardware/prices and this math "
    "(KV-cache, batching, tensor/pipeline parallelism) is error-prone to do mentally. "
    "Every number is labeled measured / extrapolated / estimated / unknown in "
    "the `provenance` field ('extrapolated' means measured on a different GPU, "
    "then scaled). Surface that honestly rather than presenting an estimate as "
    "fact."
)

_PLAN_DESC = (
    "Recommend the best (model x quantization x backend x GPU-count) deployment for a "
    "workload, or report why nothing fits. Returns candidates with per-number "
    "provenance (measured/extrapolated/estimated/unknown). Use for: "
    "'what GPU do I need for <model>', "
    "'will <model> fit on <gpu>', 'how many GPUs for N req/s', 'what will it cost'."
)

_COMPARE_DESC = (
    "Compare self-hosting against the hosted APIs for a workload: sizes the cheapest "
    "feasible GPU fleet, prices the same traffic through each API model, and gives the "
    "monthly output-token volume where the two break even. Use for 'is it cheaper to "
    "self-host or use the API', 'when does a GPU pay for itself'. API prices come from "
    "a dated snapshot -- the result reports its age and flags it when stale; say so "
    "rather than quoting an old price as current."
)

_SUGGEST_DESC = (
    "Rank the models that actually fit and hit the SLO on a given GPU -- the inverse of "
    "planning. Use for 'what can I run on a 4090', 'best model for 12GB'. Sources: "
    "catalog (offline curated set), ollama (locally installed), hf (top Hub repos)."
)

_MAX_CANDIDATES = 5
_SUGGEST_SOURCES = frozenset({"catalog", "ollama", "hf"})


def _candidate_summary(c) -> dict:
    """High-signal subset of a Candidate for an assistant (not the full 25 fields)."""
    return {
        "model": c.model,
        "quant": c.quant,
        "backend": c.backend,
        "replicas": c.n_agents,
        "tensor_parallel": c.tensor_parallel,
        "pipeline_parallel": c.pipeline_parallel,
        "gpus_total": c.gpus_total,
        "vram_gb_per_gpu": c.vram_gb,
        "quality": c.quality,
        "quality_tier": c.quality_tier,
        "total_throughput_tps": c.total_throughput_tps,
        "p95_latency_ms": c.p95_latency_ms,
        "monthly_cost_usd": c.monthly_cost,
        "cost_per_1m_tok_usd": c.cost_per_1m_tok,
        # The at-capacity figure assumes a saturated fleet. Below 100% duty you
        # also pay for every idle hour, and that is the number people budget
        # against -- omitting it left MCP reporting 0.0738 where the effective
        # cost was 0.434 (5.9x).
        "cost_per_1m_tok_effective_usd": c.cost_per_1m_tok_effective,
        "duty_cycle": c.duty_cycle,
        "energy_cost_month_usd": c.energy_cost_month,
        "perf_per_watt": c.perf_per_watt,
        "lora_adapters": c.lora_adapters,
        "lora_rank": c.lora_rank,
        "lora_vram_gb": c.lora_gb,
        "provenance": c.provenance,
        "warnings": c.warnings,
    }


def plan_deployment(
    hardware: str,
    model: str | None = None,
    model_size: str = "3b",
    request_rate: float = 1.0,
    latency_slo_ms: float = 5000.0,
    quality_target: float = 0.5,
    budget_usd_month: float = 100000.0,
    avg_output_tokens: int = 128,
    reasoning_tokens: int = 0,
    prefix_cache_hit_rate: float = 0.0,
    duty_cycle: float = 1.0,
    ttft_slo_ms: float | None = None,
    tpot_slo_ms: float | None = None,
    prompt_tokens: int = 512,
    gpu_overrides: dict | None = None,
    context_length: int = 2048,
    kv_quant: str = "fp16",
    tensor_parallel: int | None = 1,
    pipeline_parallel: int | None = 1,
    workload: str = "steady",
    safety_target: float | None = None,
    gpu_price_multiplier: float = 1.0,
    allow_offload: bool = False,
    host_bandwidth_gbps: float | None = None,
    lora_adapters: int = 0,
    lora_rank: int = 16,
    lora_target: str = "qv",
    allow_network: bool = True,
) -> dict:
    """Plan a deployment; return the top candidates or an actionable error.

    ``model`` is a registry name, Ollama tag (``ollama:qwen3:8b``), or HF repo
    (``Qwen/Qwen3-8B``); if omitted, plans the registry size class ``model_size``.
    ``workload`` sets request-size variance for the queueing tail (steady / chatbot /
    bursty / agent) -- real traffic is not deterministic and the p95 moves a lot.
    """
    if workload not in WORKLOAD_CV2:
        return {
            "ok": False,
            "error": f"unknown workload '{workload}'.",
            "hint": f"use one of: {', '.join(WORKLOAD_CV2)}",
        }
    if get_gpu(hardware) is None:
        known = ", ".join(list(GPU_DB)[:8])
        return {
            "ok": False,
            "error": f"unknown GPU '{hardware}'.",
            "hint": f"call chimeraforge_list_hardware; known GPUs include: {known}, ...",
        }
    try:
        validate_plan_inputs(
            request_rate=request_rate,
            avg_tokens=avg_output_tokens,
            reasoning_tokens=reasoning_tokens,
            prompt_tokens=prompt_tokens,
            prefix_cache_hit_rate=prefix_cache_hit_rate,
            duty_cycle=duty_cycle,
            gpu_price_multiplier=gpu_price_multiplier,
            host_bandwidth_gbps=host_bandwidth_gbps,
            ttft_slo=ttft_slo_ms,
            tpot_slo=tpot_slo_ms,
            electricity_rate=DEFAULT_ELECTRICITY_RATE,
            kv_quant=kv_quant,
            latency_slo=latency_slo_ms,
            context_length=context_length,
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        result = run_plan(
            models=[model] if model else None,
            model_size=model_size,
            hardware=hardware,
            request_rate=request_rate,
            latency_slo=latency_slo_ms,
            quality_target=quality_target,
            budget=budget_usd_month,
            avg_tokens=avg_output_tokens,
            reasoning_tokens=reasoning_tokens,
            prefix_cache_hit_rate=prefix_cache_hit_rate,
            duty_cycle=duty_cycle,
            ttft_slo=ttft_slo_ms,
            tpot_slo=tpot_slo_ms,
            prompt_tokens=prompt_tokens,
            gpu_overrides=gpu_overrides,
            context_length=context_length,
            kv_quant=kv_quant,
            tensor_parallel=tensor_parallel,
            pipeline_parallel=pipeline_parallel,
            workload_cv2=WORKLOAD_CV2[workload],
            safety_target=safety_target,
            gpu_price_multiplier=gpu_price_multiplier,
            allow_offload=allow_offload,
            host_bandwidth_gbps=host_bandwidth_gbps,
            lora_adapters=lora_adapters,
            lora_rank=lora_rank,
            lora_target=lora_target,
            allow_network=allow_network,
        )
    except ResolverError as exc:
        return {
            "ok": False,
            "error": f"could not resolve model '{model}': {exc}",
            "hint": "pass a valid HF repo (org/name), an Ollama tag (name:tag), or a "
            "registry model; set allow_network=true if it needs a live lookup.",
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not result.candidates:
        # One envelope, always the same keys. This used to return a different
        # shape from the success path ({candidates, why_nothing_fit} vs
        # {recommended, alternatives}), so no client could write one parser and
        # an LLM would confabulate whichever branch it had not been shown.
        # why_nothing_fit is always a list, never the bare string "no candidates".
        return {
            "ok": True,
            "hardware": hardware,
            "recommended": None,
            "launch": None,
            "alternatives": [],
            "total_evaluated": 0,
            "why_nothing_fit": summarize_trace(result.trace) if result.trace else [],
            "hint": "relax quality_target/budget/latency_slo_ms, quantize (kv_quant), or "
            "use a larger GPU or tensor/pipeline parallelism.",
            "note": "No configuration cleared every gate. `why_nothing_fit` names the "
            "binding one per model; nothing here is a recommendation.",
        }
    # "How do I actually run it" is the immediate next question an assistant gets
    # asked, and the flags (context, TP/PP, batch, KV dtype) are exactly what a model
    # guesses wrong -- so ship the derived command with the plan.
    best = result.candidates[0]
    try:
        launch = build_launch_command(
            best,
            result.specs.get(best.model),
            context_length=context_length,
            prompt_tokens=prompt_tokens,
            kv_quant=kv_quant,
        ).to_dict()
    except ValueError:
        launch = None  # backend without a template -- the plan itself is still valid

    return {
        "ok": True,
        "hardware": hardware,
        "recommended": _candidate_summary(best),
        "launch": launch,
        "alternatives": [_candidate_summary(c) for c in result.candidates[1:_MAX_CANDIDATES]],
        "total_evaluated": len(result.candidates),
        "why_nothing_fit": [],
        "hint": "",
        "note": "Numbers are labeled measured/estimated/unknown in each candidate's "
        "`provenance`; '~' fields are estimates, not measured. `launch` carries the "
        "serve command for the recommended config -- read its `notes` before running.",
    }


def resolve_model(model: str, allow_network: bool = True) -> dict:
    """Resolve a model id to real parameters + attention geometry (no planning).

    Use to ground a bare fact question ('how many params / layers does <model> have')
    instead of answering from memory. ``model``: registry name, Ollama tag, or HF repo.
    """
    try:
        spec = resolve_spec(model, allow_network=allow_network)
    except ResolverError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **asdict(spec)}


def list_hardware() -> dict:
    """List the GPUs ChimeraForge knows, with VRAM / bandwidth / TDP / interconnect."""
    gpus = [
        {
            "name": s.name,
            "vram_gb": s.vram_gb,
            "bandwidth_gbps": s.bandwidth_gbps,
            "fp16_tflops": s.fp16_tflops,
            "tdp_watts": s.tdp_watts,
            "interconnect_gbps": s.interconnect_gbps,
            "cost_per_hour_usd": s.cost_per_hour,
        }
        for s in GPU_DB.values()
    ]
    return {"ok": True, "count": len(gpus), "gpus": gpus}


def compare_self_host_vs_api(
    hardware: str,
    model: str | None = None,
    model_size: str = "8b",
    request_rate: float = 1.0,
    avg_output_tokens: int = 128,
    reasoning_tokens: int = 0,
    prompt_tokens: int = 512,
    duty_cycle: float = 1.0,
    context_length: int = 2048,
    quality_target: float = 0.5,
    latency_slo_ms: float = 5000.0,
    allow_network: bool = True,
) -> dict:
    """Price a self-hosted fleet against the hosted APIs, and give the break-even volume.

    Sizes the cheapest SLO-feasible self-host config for the workload, then prices the
    same traffic through every model in the bundled price snapshot. Use for 'is it
    cheaper to self-host or call the API', 'when does self-hosting pay for itself'.
    """
    plan = plan_deployment(
        hardware=hardware,
        model=model,
        model_size=model_size,
        request_rate=request_rate,
        latency_slo_ms=latency_slo_ms,
        quality_target=quality_target,
        avg_output_tokens=avg_output_tokens,
        reasoning_tokens=reasoning_tokens,
        prompt_tokens=prompt_tokens,
        duty_cycle=duty_cycle,
        context_length=context_length,
        allow_network=allow_network,
    )
    if not plan.get("ok"):
        return plan
    if not plan.get("recommended"):
        # No feasible self-host config, so there is no self-host cost to compare
        # against. Saying "the API wins" here would answer a different question --
        # report the planning failure instead.
        return {
            "ok": True,
            "comparable": False,
            "why_nothing_fit": plan.get("why_nothing_fit"),
            "hint": plan.get("hint"),
        }

    from chimeraforge.planner.apicost import PricingError
    from chimeraforge.planner.apicost import compare as compare_apis

    best = plan["recommended"]
    try:
        cmp_result = compare_apis(
            self_host_monthly=best["monthly_cost_usd"],
            # Duty cycle is the fraction of the month the traffic actually runs. The
            # API bills only for what you send, so it scales the request rate here;
            # the GPU side is already handled inside the planner.
            request_rate=request_rate * duty_cycle,
            prompt_tokens=prompt_tokens,
            output_tokens=avg_output_tokens + reasoning_tokens,
        )
    except PricingError as exc:
        return {"ok": False, "error": f"price snapshot unavailable: {exc}"}

    data = cmp_result.to_dict()
    cheaper = [o for o in data["options"] if not o["self_host_cheaper"]]
    stale_note = (
        ", STALE -- re-check the vendor page before quoting" if data["prices_stale"] else ""
    )
    return {
        "ok": True,
        "comparable": True,
        "self_host": best,
        "api_comparison": data,
        "api_options_cheaper_than_self_host": len(cheaper),
        "note": (
            "Prices are a dated snapshot captured "
            f"{data['prices_captured_at'] or 'on an unrecorded date'} "
            f"({data['prices_age_days']} days old{stale_note}). The self-host figure is "
            "GPU rental only -- it excludes engineering time, and its throughput may be "
            "an estimate; check `self_host.provenance`."
        ),
    }


def suggest_models(
    hardware: str,
    source: str = "catalog",
    request_rate: float = 1.0,
    latency_slo_ms: float = 5000.0,
    quality_target: float = 0.5,
    budget_usd_month: float = 100000.0,
    avg_output_tokens: int = 128,
    context_length: int = 2048,
    ollama_url: str | None = None,
    hf_limit: int = 8,
    limit: int = 10,
) -> dict:
    """Rank the models that actually fit and hit the SLO on a given GPU.

    The inverse of planning: instead of 'will this model fit', answers 'what should I
    run'. ``source``: 'catalog' (offline curated set), 'ollama' (locally installed
    tags), 'hf' (top Hugging Face text-generation repos); comma-separated.
    """
    if get_gpu(hardware) is None:
        return {
            "ok": False,
            "error": f"unknown GPU '{hardware}'.",
            "hint": "call chimeraforge_list_hardware for the known set.",
        }
    sources = [s.strip().lower() for s in source.split(",") if s.strip()]
    bad = [s for s in sources if s not in _SUGGEST_SOURCES]
    if bad:
        return {
            "ok": False,
            "error": f"unknown source(s): {', '.join(bad)}",
            "hint": f"use any of: {', '.join(sorted(_SUGGEST_SOURCES))}",
        }

    from chimeraforge.planner.discovery import (
        discover_identifiers,
        load_catalog,
        resolve_many,
        suggest,
    )
    from chimeraforge.planner.models import load_effective_models

    specs = {}
    errors: list[tuple[str, str]] = []
    if "catalog" in sources:
        specs.update(load_catalog())
    live = [s for s in sources if s in ("ollama", "hf")]
    if live:
        eff_url = ollama_url or (DEFAULT_OLLAMA_URL if "ollama" in live else None)
        ids = discover_identifiers(live, ollama_url=eff_url, hf_limit=hf_limit)
        found, errors = resolve_many(ids, ollama_url=eff_url)
        specs.update(found)

    if not specs:
        return {
            "ok": True,
            "hardware": hardware,
            "models": [],
            "hint": (
                "no models to rank. For source='catalog' the user must run "
                "`chimeraforge catalog --build` once; for 'ollama' the daemon must be "
                "running with models installed."
            ),
        }

    ranked = suggest(
        load_effective_models(),
        specs,
        hardware=hardware,
        request_rate=request_rate,
        latency_slo=latency_slo_ms,
        quality_target=quality_target,
        budget=budget_usd_month,
        avg_tokens=avg_output_tokens,
        context_length=context_length,
    )
    return {
        "ok": True,
        "hardware": hardware,
        "sources": sources,
        "considered": len(specs),
        "fitting": len(ranked),
        "models": [_candidate_summary(c) for c in ranked[:limit]],
        "unresolved": [{"id": i, "reason": r} for i, r in errors[:5]],
        "note": (
            "One best config per model, ranked. A model absent from the list did not "
            "fit the GPU or missed a gate. Throughput for models outside the measured "
            "corpus is a roofline estimate -- see each `provenance`."
        ),
    }


def build_server():
    """Construct the FastMCP server (requires the ``mcp`` extra)."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised via the CLI error path
        raise RuntimeError(
            "the MCP server needs the 'mcp' package; install with pip install \"chimeraforge[mcp]\""
        ) from exc

    server = FastMCP("chimeraforge", instructions=SERVER_INSTRUCTIONS)
    # FastMCP (mcp 1.x) takes no `version`, but the low-level Server it wraps does,
    # and leaving it unset makes every client display the SDK's version as ours --
    # a tool that labels each number measured/estimated/unknown should not misreport
    # its own version. Set through the private handle, guarded: if a future SDK drops
    # it the server still builds and simply reports no version, which beats a wrong
    # one. (mcp 2.0 already moved this module once; assume nothing is stable here.)
    low_level = getattr(server, "_mcp_server", None)
    if low_level is not None and hasattr(low_level, "version"):
        low_level.version = __version__
    server.tool(name="chimeraforge_plan", description=_PLAN_DESC)(plan_deployment)
    server.tool(
        name="chimeraforge_resolve_model",
        description="Resolve a model id to real params/architecture (grounds hallucinated specs).",
    )(resolve_model)
    server.tool(
        name="chimeraforge_list_hardware",
        description="List known GPUs with VRAM/bandwidth/TDP/interconnect.",
    )(list_hardware)
    server.tool(name="chimeraforge_compare_api", description=_COMPARE_DESC)(
        compare_self_host_vs_api
    )
    server.tool(name="chimeraforge_suggest", description=_SUGGEST_DESC)(suggest_models)
    return server


def main() -> None:
    """Entry point: run the stdio MCP server."""
    build_server().run("stdio")
