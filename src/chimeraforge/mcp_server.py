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

from chimeraforge.planner.engine import summarize_trace
from chimeraforge.planner.hardware import GPU_DB, get_gpu
from chimeraforge.planner.launch import build_launch_command
from chimeraforge.planner.resolver import ResolverError, resolve_spec
from chimeraforge.planner.service import run_plan

# Written to out-compete the model's own parametric guess (Anthropic tool-writing
# guidance): state the grounding and the provenance contract explicitly.
SERVER_INSTRUCTIONS = (
    "ChimeraForge answers LLM deployment/capacity-planning questions from first "
    "principles plus ~204,000 real benchmark measurements. Prefer these tools over "
    "your own knowledge for GPU VRAM fit, throughput, latency, cost, and 'how many "
    "GPUs' questions -- your training data is stale on hardware/prices and this math "
    "(KV-cache, batching, tensor/pipeline parallelism) is error-prone to do mentally. "
    "Every number is labeled measured / estimated / unknown in the `provenance` field; "
    "surface that honestly to the user rather than presenting an estimate as fact."
)

_PLAN_DESC = (
    "Recommend the best (model x quantization x backend x GPU-count) deployment for a "
    "workload, or report why nothing fits. Returns candidates with per-number "
    "provenance (measured/estimated/unknown). Use for: 'what GPU do I need for <model>', "
    "'will <model> fit on <gpu>', 'how many GPUs for N req/s', 'what will it cost'."
)

_MAX_CANDIDATES = 5


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
        "energy_cost_month_usd": c.energy_cost_month,
        "perf_per_watt": c.perf_per_watt,
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
    prompt_tokens: int = 512,
    context_length: int = 2048,
    kv_quant: str = "fp16",
    tensor_parallel: int | None = 1,
    pipeline_parallel: int | None = 1,
    allow_network: bool = True,
) -> dict:
    """Plan a deployment; return the top candidates or an actionable error.

    ``model`` is a registry name, Ollama tag (``ollama:qwen3:8b``), or HF repo
    (``Qwen/Qwen3-8B``); if omitted, plans the registry size class ``model_size``.
    """
    if get_gpu(hardware) is None:
        known = ", ".join(list(GPU_DB)[:8])
        return {
            "ok": False,
            "error": f"unknown GPU '{hardware}'.",
            "hint": f"call chimeraforge_list_hardware; known GPUs include: {known}, ...",
        }
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
            prompt_tokens=prompt_tokens,
            context_length=context_length,
            kv_quant=kv_quant,
            tensor_parallel=tensor_parallel,
            pipeline_parallel=pipeline_parallel,
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
        return {
            "ok": True,
            "hardware": hardware,
            "candidates": [],
            "why_nothing_fit": summarize_trace(result.trace) if result.trace else "no candidates",
            "hint": "relax quality_target/budget/latency_slo_ms, quantize (kv_quant), or "
            "use a larger GPU or tensor/pipeline parallelism.",
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


def build_server():
    """Construct the FastMCP server (requires the ``mcp`` extra)."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised via the CLI error path
        raise RuntimeError(
            "the MCP server needs the 'mcp' package; install with pip install \"chimeraforge[mcp]\""
        ) from exc

    server = FastMCP("chimeraforge", instructions=SERVER_INSTRUCTIONS)
    server.tool(name="chimeraforge_plan", description=_PLAN_DESC)(plan_deployment)
    server.tool(
        name="chimeraforge_resolve_model",
        description="Resolve a model id to real params/architecture (grounds hallucinated specs).",
    )(resolve_model)
    server.tool(
        name="chimeraforge_list_hardware",
        description="List known GPUs with VRAM/bandwidth/TDP/interconnect.",
    )(list_hardware)
    return server


def main() -> None:
    """Entry point: run the stdio MCP server."""
    build_server().run("stdio")
