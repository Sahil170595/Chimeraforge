"""`plan` command - predictive capacity planner."""

from __future__ import annotations

import json as json_mod
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

# constants is pure-stdlib (no heavy deps), so this module-level import is safe for
# the `--version` fast path; it supplies flag defaults/choices.
from chimeraforge.planner.constants import (
    DEFAULT_ELECTRICITY_RATE,
    DEFAULT_KV_QUANT,
    DEFAULT_LATENCY_SLO_MS,
    DEFAULT_LORA_TARGET,
    KV_QUANT_BYTES,
    PLAN_MODE_BATCH,
    PLAN_MODES,
)

# Which CLI flag each profile-supplied field corresponds to, so an explicitly
# passed flag can be detected and left alone.
_PROFILE_FLAG = {
    "request_rate": "request_rate",
    "prompt_tokens": "prompt_tokens",
    "avg_tokens": "avg_tokens",
    "workload_cv2": "workload",
    "prefix_cache_hit_rate": "prefix_cache_hit_rate",
}

_DIGITS = re.compile(r"\d+")

console = Console()
# Diagnostics go here so `--json` output on stdout stays exactly one document. A caller
# that has to strip lines before parsing does not have a contract.
err_console = Console(stderr=True)


def plan(
    ctx: typer.Context,
    model_size: str = typer.Option(
        "3b",
        "--model-size",
        "-m",
        help="Target model size class (e.g., 1b, 3b, 8b). Ignored if --model is given.",
    ),
    model: list[str] = typer.Option(
        None,
        "--model",
        "-M",
        help="Explicit model id(s): registry name, Ollama tag (ollama:NAME), or HF "
        "repo (org/name). Repeatable. Resolves real params/arch; overrides --model-size.",
    ),
    request_rate: float = typer.Option(
        1.0,
        "--request-rate",
        "-r",
        help="Requests per second.",
    ),
    latency_slo: float = typer.Option(
        None,
        "--latency-slo",
        "-l",
        help="Max p95 latency in milliseconds (default 5000). Online mode only.",
    ),
    mode: str = typer.Option(
        "online",
        "--mode",
        help="online: requests someone waits on (latency-gated, cheapest monthly bill). "
        "batch: an offline backlog (no latency gate; each GPU at its max-throughput "
        "batch, fleet sized to drain --request-rate, ranked by $/1M tokens).",
    ),
    quality_target: float = typer.Option(
        0.5,
        "--quality-target",
        "-q",
        help="Min composite quality score (0.0-1.0).",
    ),
    safety_target: float = typer.Option(
        None,
        "--safety-target",
        "-s",
        help="Min refusal rate 0.0-1.0 (TR134/TR142 screen). Opt-in; rejects unsafe cells.",
    ),
    budget: float = typer.Option(
        100.0,
        "--budget",
        "-b",
        help="Max monthly cost in USD.",
    ),
    hardware: str = typer.Option(
        "RTX 4080 12GB",
        "--hardware",
        "-hw",
        help="GPU name from the hardware dataset, or 'auto' to read the installed "
        "card. An unlisted GPU can be planned by supplying --gpu-vram-gb and "
        "--gpu-bandwidth-gbps.",
    ),
    gpu_vram_gb: float = typer.Option(
        None, "--gpu-vram-gb", help="Override/supply the GPU's VRAM in GB."
    ),
    gpu_bandwidth_gbps: float = typer.Option(
        None,
        "--gpu-bandwidth-gbps",
        help="Override/supply memory bandwidth in GB/s. Decode is bandwidth-bound, "
        "so without this an unlisted card's throughput is unknown, not guessed.",
    ),
    gpu_fp16_tflops: float = typer.Option(
        None, "--gpu-fp16-tflops", help="Override/supply dense FP16 TFLOPS (prefill/TTFT)."
    ),
    gpu_tdp_w: float = typer.Option(
        None, "--gpu-tdp-w", help="Override/supply board TDP in watts (energy, perf/watt)."
    ),
    gpu_interconnect_gbps: float = typer.Option(
        None, "--gpu-interconnect-gbps", help="Override/supply the TP interconnect in GB/s."
    ),
    unified_memory_fraction: float = typer.Option(
        None,
        "--unified-memory-fraction",
        help="For a unified-memory device (Apple Silicon, Strix Halo, DGX Spark): the "
        "share (0-1] of the shared pool the GPU may use. Required there, with no "
        "default -- the OS and other apps need their share.",
    ),
    platform: str = typer.Option(
        None,
        "--platform",
        help="OS the deployment runs on: linux, windows, wsl2 or macos. Each engine is "
        "offered only where its own docs say it runs (e.g. vLLM has no native "
        "Windows support). Default: linux, or this machine's OS with --hardware auto.",
    ),
    gpu_price_per_hour: float = typer.Option(
        None,
        "--gpu-price-per-hour",
        help="Override/supply $/GPU-hour. Your rate is a rate you were quoted; the "
        "bundled figures are a dated snapshot on a stated basis.",
    ),
    context_length: int = typer.Option(
        2048,
        "--context-length",
        help="Context window length in tokens.",
    ),
    avg_tokens: int = typer.Option(
        128,
        "--avg-tokens",
        help="Average output tokens per request (decode length).",
    ),
    reasoning_tokens: int = typer.Option(
        0,
        "--reasoning-tokens",
        help="Hidden thinking tokens generated per request by a reasoning model "
        "(R1/o-series/QwQ). The GPU decodes these and the KV cache holds them, but "
        "they are not in --avg-tokens. Your scenario input: measure it, do not guess.",
    ),
    allow_offload: bool = typer.Option(
        False,
        "--allow-offload",
        help="Allow configs where weights that do not fit VRAM stream from host RAM "
        "(what llama.cpp/Ollama do). It runs, but slowly: the derate is modelled "
        "from the bandwidth ratio, not measured.",
    ),
    host_bandwidth_gbps: float = typer.Option(
        None,
        "--host-bandwidth-gbps",
        help="Host link bandwidth for offloaded weights (default: the GPU's PCIe "
        "figure). Board- and lane-dependent, so it is your scenario input.",
    ),
    ttft_slo: float = typer.Option(
        None,
        "--ttft-slo",
        help="Max acceptable time-to-first-token in ms. Gates responsiveness "
        "separately from the blended p95, which hides which half a config fails.",
    ),
    tpot_slo: float = typer.Option(
        None,
        "--tpot-slo",
        help="Max acceptable time-per-output-token in ms (streaming smoothness). "
        "A large batch can win on p95 while making each token arrive too slowly.",
    ),
    duty_cycle: float = typer.Option(
        1.0,
        "--duty-cycle",
        help="Fraction of the month the fleet actually serves the planned rate "
        "(0.0-1.0). A rented GPU bills for wall-clock, so a fleet sized for a peak "
        "it sees 30%% of the day costs the same but delivers a third of the tokens.",
    ),
    gpu_price_multiplier: float = typer.Option(
        1.0,
        "--gpu-price-multiplier",
        help="Scale the GPU $/hr for spot, reserved, or negotiated rates (e.g. 0.3 "
        "for a 70%% spot discount). The bundled rates are approximate on-demand; the "
        "discount is provider- and region-specific, so it is your input.",
    ),
    prefix_cache_hit_rate: float = typer.Option(
        0.0,
        "--prefix-cache-hit-rate",
        help="Fraction of the prompt already in the prefix cache (0.0-1.0). Skips "
        "prefill for that span, lowering TTFT. Your scenario input: chatbot/agent "
        "traffic reuses a long system prompt, one-shot traffic does not.",
    ),
    prompt_tokens: int = typer.Option(
        512,
        "--prompt-tokens",
        help="Average input prompt length in tokens (drives prefill / TTFT).",
    ),
    quality_from: str = typer.Option(
        None,
        "--quality-from",
        help="Path to an lm-evaluation-harness results JSON. Its score REPLACES "
        "the bundled 20-item composite (they are different scales and must not be "
        "mixed), and --quality-target is then read against that metric.",
    ),
    max_num_batched_tokens: int = typer.Option(
        0,
        "--max-num-batched-tokens",
        help="Chunked-prefill token budget per scheduler step (vLLM V1 enables "
        "chunking by default). A prompt longer than this is split, and each chunk "
        "re-reads the earlier chunks' KV. 0 = model an unchunked prefill.",
    ),
    workload: str = typer.Option(
        "steady",
        "--workload",
        help="Service-time variance preset: steady, chatbot, bursty, agent. "
        "High-variance (agent) inflates the tail estimate and warns.",
    ),
    electricity_rate: float = typer.Option(
        DEFAULT_ELECTRICITY_RATE,
        "--electricity-rate",
        help="Electricity price in $/kWh for the energy estimate (default US "
        "commercial avg). Reported separately; cloud $/hr rates already include power.",
    ),
    kv_quant: str = typer.Option(
        DEFAULT_KV_QUANT,
        "--kv-quant",
        help="KV-cache dtype: fp16 (default), q8, or q4. A quantized cache lowers "
        "VRAM and raises the concurrency cap; its quality impact is not screened.",
    ),
    tensor_parallel: str = typer.Option(
        "1",
        "--tensor-parallel",
        "--tp",
        help="Tensor-parallel degree: 1 (single GPU), an integer to split a model "
        "across N GPUs, or 'auto' (smallest TP that fits). Lets a model too big for "
        "one GPU be planned across several; TP throughput is a comms-modelled estimate.",
    ),
    pipeline_parallel: str = typer.Option(
        "1",
        "--pipeline-parallel",
        "--pp",
        help="Pipeline-parallel degree: 1, an integer to split a model's layers "
        "across N GPUs, or 'auto'. Cheaper interconnect use than TP (good on PCIe) "
        "but needs batching to fill the pipeline. Cannot be combined with --tp yet.",
    ),
    models_path: str = typer.Option(
        None,
        "--models-path",
        help="Path to fitted_models.json (default: bundled data).",
    ),
    ollama_url: str = typer.Option(
        None,
        "--ollama-url",
        help="Ollama base URL; enables resolving --model tags via /api/show.",
    ),
    hf_token: str = typer.Option(
        None,
        "--hf-token",
        help="Hugging Face token for gated repos (else $HF_TOKEN).",
    ),
    revision: list[str] = typer.Option(
        None,
        "--revision",
        help=(
            "HF commit/branch/tag for one --model, or repeat MODEL=REF for selected HF models. "
            "Metadata is pinned to the resolved commit."
        ),
    ),
    no_network: bool = typer.Option(
        False,
        "--no-network",
        help="Never fetch metadata; resolve from registry/cache/overrides only.",
    ),
    params_b: float = typer.Option(
        None,
        "--params-b",
        help="Manual override: parameter count in billions (with a single --model).",
    ),
    n_layers: int = typer.Option(
        None,
        "--n-layers",
        help="Manual override: transformer block count.",
    ),
    n_kv_heads: int = typer.Option(
        None,
        "--n-kv-heads",
        help="Manual override: key/value head count.",
    ),
    d_head: int = typer.Option(
        None,
        "--d-head",
        help="Manual override: per-head dimension.",
    ),
    hidden_size: int = typer.Option(
        None,
        "--hidden-size",
        help="Manual override: model hidden dimension. Needed to size LoRA adapters "
        "and MoE experts exactly.",
    ),
    lora_adapters: int = typer.Option(
        0,
        "--lora-adapters",
        help="Serve N LoRA adapters alongside the base model (multi-tenant adapter "
        "serving). Adapters share the base weights; VRAM is exact geometry.",
    ),
    lora_rank: int = typer.Option(
        16,
        "--lora-rank",
        help="LoRA rank of the served adapters. Drives both adapter VRAM (exact) and "
        "the decode cost (estimated from one published sweep).",
    ),
    lora_target: str = typer.Option(
        DEFAULT_LORA_TARGET,
        "--lora-target",
        help="Which linear modules the adapters target: qv (PEFT default) or attn "
        "(q,k,v,o). MLP targets need an intermediate_size the resolver may not have, "
        "so they are not offered rather than guessed.",
    ),
    measure_first: bool = typer.Option(
        False,
        "--measure",
        help="Benchmark the --model live first (real throughput+scaling), then plan "
        "on the measured numbers. Requires a live backend serving the model.",
    ),
    save: str | None = typer.Option(
        None, "--save", help="Save a versioned plan artifact with inputs and provenance."
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON instead of Rich tables.",
    ),
    contributions: bool = typer.Option(
        False,
        "--contributions",
        help="Use quarantined contributed bench results (`chimeraforge contribute import`) "
        "for an exact model/engine/quant/GPU match, labelled `contributed` (unverified).",
    ),
    cloud: str = typer.Option(
        None,
        "--cloud",
        help="Price the fleet at aws or azure on-demand list prices (a dated snapshot of "
        "each cloud's public price list), instance by instance, instead of the bundled "
        "marketplace rate.",
    ),
    think_time: float = typer.Option(
        None,
        "--think-time",
        metavar="SECONDS",
        help="Seconds between a conversation's turns. With --session-turns, limits "
        "--prefix-cache-hit-rate to what the fleet's free KV can keep for idle "
        "conversations (Little's law: rate x (T-1)/T x think time of them).",
    ),
    session_turns: int = typer.Option(
        None,
        "--session-turns",
        help="Average turns per conversation (>= 2). Used with --think-time.",
    ),
    grid_region: str = typer.Option(
        None,
        "--grid-region",
        help="Report operational gCO2e per 1M tokens on this grid (ISO-3 code or "
        "country name, e.g. USA, DEU, France): Ember's annual-average lifecycle "
        "intensity via Our World in Data. SCI operational term only; embodied excluded.",
    ),
    carbon_intensity: float = typer.Option(
        None,
        "--carbon-intensity",
        help="Your own grid figure in gCO2e/kWh (e.g. a marginal or hourly value from "
        "your provider), instead of --grid-region.",
    ),
    pareto: bool = typer.Option(
        False,
        "--pareto",
        help="Show the cost/latency/quality trade-off frontier (the menu of "
        "non-dominated configs), not just the single cheapest pick.",
    ),
    launch: bool = typer.Option(
        False,
        "--launch",
        help="Also emit a copy-paste serve command (vllm/ollama/tgi) for the "
        "recommended config, with the plan's context/parallelism/batch/KV flags.",
    ),
    compare_api: bool = typer.Option(
        False,
        "--compare-api",
        help="Also price this workload against hosted APIs and report the break-even "
        "volume. Uses a dated snapshot of published list prices, not a live quote.",
    ),
    report: str = typer.Option(
        None,
        "--report",
        metavar="PATH",
        help="Write a decision brief (markdown) to PATH: recommendation, assumptions, "
        "alternatives, risks verbatim, and the command that reproduces it. Every number "
        "is provenance-labeled. Refuses to render on a stale price snapshot.",
    ),
    fleet: str = typer.Option(
        None,
        "--fleet",
        metavar="GPU,GPU,...",
        help="Size a HETEROGENEOUS fleet across these GPU types instead of N copies "
        "of one. Prices each type separately, then picks the cheapest mix that "
        "covers the rate. A mix needs a capability-aware router, which no serving "
        "engine ships -- the plan says so.",
    ),
    workload_profile: str = typer.Option(
        None,
        "--workload-profile",
        metavar="PATH",
        help="A profile from `chimeraforge workload`. Fills request rate, token "
        "lengths, traffic variance and prefix-cache hit rate from measured traffic. "
        "An explicit flag always wins; a field the profile did not measure is left "
        "for you to supply, never defaulted.",
    ),
    list_hardware: bool = typer.Option(
        False,
        "--list-hardware",
        help="List available GPUs in hardware DB.",
    ),
    list_models: bool = typer.Option(
        False,
        "--list-models",
        help="List available model sizes.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Recommend optimal LLM deployment configuration.

    Searches model x quantization x backend x instance-count space,
    filtering through VRAM, quality, latency, and budget gates.
    """
    import logging

    from chimeraforge.planner.formatter import (
        format_json,
        format_pareto,
        format_pareto_json,
        format_recommendation,
        print_hardware_table,
        print_models_table,
    )
    from chimeraforge.planner.hardware import get_gpu
    from chimeraforge.planner.resolver import ResolverError
    from chimeraforge.planner.service import run_plan

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    # These two honour --json. `--list-hardware` is the only way to discover a valid
    # --hardware value, so it is the listing an automated caller most needs to read; it
    # used to ignore --json and print a box-drawing table regardless.
    if list_hardware:
        if output_json:
            from chimeraforge.planner.hardware import GPU_DB, known_or_none

            payload = [
                {
                    "name": spec.name,
                    "vram_gb": spec.vram_gb,
                    "bandwidth_gbps": spec.bandwidth_gbps,
                    "cost_per_hour": known_or_none(spec.cost_per_hour),
                    "fp16_tflops": known_or_none(spec.fp16_tflops),
                }
                for _, spec in sorted(GPU_DB.items())
            ]
            console.print(json_mod.dumps(payload, indent=2), highlight=False, soft_wrap=True)
        else:
            print_hardware_table()
        raise typer.Exit()

    if list_models:
        if output_json:
            from chimeraforge.planner.engine import MODEL_PARAMS_B

            payload = [
                {"model": name, "params_b": params}
                for name, params in sorted(MODEL_PARAMS_B.items())
            ]
            console.print(json_mod.dumps(payload, indent=2), highlight=False, soft_wrap=True)
        else:
            print_models_table()
        raise typer.Exit()

    # Fail loud with a clean message. Under --json, emit {"error": ...} so an
    # automated consumer parsing stdout gets JSON on failure, not Rich-styled text.
    def _fail(msg: str) -> None:
        if output_json:
            import json as _json

            console.print(
                _json.dumps({"error": msg}), highlight=False, soft_wrap=True, markup=False
            )
        else:
            console.print(f"[red]Error:[/] {msg}")
        raise typer.Exit(code=1)

    # Validate inputs
    if request_rate <= 0:
        _fail("--request-rate must be positive.")
    if avg_tokens <= 0:
        _fail("--avg-tokens must be positive.")
    if reasoning_tokens < 0:
        _fail("--reasoning-tokens must be non-negative.")
    if not 0.0 <= prefix_cache_hit_rate <= 1.0:
        _fail("--prefix-cache-hit-rate must be between 0.0 and 1.0.")
    gpu_overrides = {
        "vram_gb": gpu_vram_gb,
        "bandwidth_gbps": gpu_bandwidth_gbps,
        "fp16_tflops": gpu_fp16_tflops,
        "tdp_watts": gpu_tdp_w,
        "interconnect_gbps": gpu_interconnect_gbps,
        "cost_per_hour": gpu_price_per_hour,
    }
    for _flag, _value in (
        ("--gpu-vram-gb", gpu_vram_gb),
        ("--gpu-bandwidth-gbps", gpu_bandwidth_gbps),
        ("--gpu-fp16-tflops", gpu_fp16_tflops),
        ("--gpu-tdp-w", gpu_tdp_w),
        ("--gpu-interconnect-gbps", gpu_interconnect_gbps),
        ("--gpu-price-per-hour", gpu_price_per_hour),
    ):
        if _value is not None and _value <= 0:
            _fail(f"{_flag} must be positive.")
    gpu_overrides = {k: v for k, v in gpu_overrides.items() if v is not None} or None
    if max_num_batched_tokens < 0:
        _fail("--max-num-batched-tokens must be non-negative (0 = unchunked).")
    # 0 means "model an unchunked prefill", which is the pre-P8.3 behaviour and
    # must stay reachable; None is what the engine reads as off.
    chunk_budget = max_num_batched_tokens or None
    # One override set describes one card, and a fleet is a mix of GPU types:
    # applying the same figures to each type would fabricate specs, and dropping
    # them would plan hardware the user did not describe.
    if fleet and unified_memory_fraction is not None:
        # One fraction cannot describe a mix of GPU types, and on a discrete card
        # it is an error rather than ignored.
        _fail(
            "--unified-memory-fraction describes one unified-memory device, and "
            "--fleet plans a mix of GPU types. Plan the device on its own."
        )
    if fleet and gpu_overrides:
        _fail(
            "--gpu-* overrides describe a single card, and --fleet plans a mix of "
            "GPU types; one set of figures cannot apply to both. Plan the unlisted "
            "card on its own, or drop the overrides."
        )
    if not 0.0 < duty_cycle <= 1.0:
        _fail("--duty-cycle must be greater than 0.0 and at most 1.0.")
    if gpu_price_multiplier <= 0:
        _fail("--gpu-price-multiplier must be positive.")
    if host_bandwidth_gbps is not None and host_bandwidth_gbps <= 0:
        _fail("--host-bandwidth-gbps must be positive.")
    if ttft_slo is not None and ttft_slo <= 0:
        _fail("--ttft-slo must be positive.")
    if tpot_slo is not None and tpot_slo <= 0:
        _fail("--tpot-slo must be positive.")
    if electricity_rate < 0:
        _fail("--electricity-rate must be non-negative.")
    kv_quant = kv_quant.lower()
    if kv_quant not in KV_QUANT_BYTES:
        _fail(f"--kv-quant must be one of: {', '.join(KV_QUANT_BYTES)}.")

    def _parse_degree(raw: str, flag: str) -> int | None:
        raw = raw.strip().lower()
        if raw == "auto":
            return None
        # Not bare int(): Python accepts numeric underscores, so "1_0" parsed as
        # 10 and a typo silently became a ten-way shard.
        if not _DIGITS.fullmatch(raw):
            _fail(f"{flag} must be a positive integer or 'auto'.")
        try:
            val = int(raw)
        except ValueError:
            _fail(f"{flag} must be a positive integer or 'auto'.")
        if val < 1:
            _fail(f"{flag} must be >= 1.")
        return val

    tp_val = _parse_degree(tensor_parallel, "--tensor-parallel")
    pp_val = _parse_degree(pipeline_parallel, "--pipeline-parallel")
    tp_on = tp_val is None or tp_val > 1
    pp_on = pp_val is None or pp_val > 1
    if tp_on and pp_on:
        _fail(
            "--tensor-parallel and --pipeline-parallel cannot be combined yet; "
            "set only one above 1."
        )
    if context_length <= 0:
        _fail("--context-length must be positive.")
    if budget <= 0:
        _fail("--budget must be positive.")
    if latency_slo is not None and latency_slo <= 0:
        _fail("--latency-slo must be positive.")
    if mode not in PLAN_MODES:
        _fail(f"--mode must be one of: {', '.join(PLAN_MODES)}.")
    if mode == PLAN_MODE_BATCH and any(v is not None for v in (latency_slo, ttft_slo, tpot_slo)):
        _fail(
            "batch mode has no latency gate, so --latency-slo/--ttft-slo/--tpot-slo "
            "would be silently ignored. Drop them, or use --mode online."
        )
    if mode != PLAN_MODE_BATCH and latency_slo is None:
        latency_slo = DEFAULT_LATENCY_SLO_MS
    if not 0.0 <= quality_target <= 1.0:
        _fail("--quality-target must be between 0.0 and 1.0.")
    if safety_target is not None and not 0.0 <= safety_target <= 1.0:
        _fail("--safety-target must be between 0.0 and 1.0.")

    from chimeraforge.planner.constants import WORKLOAD_CV2

    if workload not in WORKLOAD_CV2:
        _fail(f"--workload must be one of: {', '.join(WORKLOAD_CV2)}.")
    workload_cv2 = WORKLOAD_CV2[workload]
    if measure_first and not model:
        _fail("--measure requires --model.")

    model_revisions = None
    if revision:
        model_revisions = {}
        for selection in revision:
            if "=" in selection:
                repo, ref = selection.split("=", 1)
            elif model and len(model) == 1:
                repo, ref = model[0], selection
            else:
                _fail("--revision REF needs one --model; use MODEL=REF for multiple models")
            if repo in model_revisions:
                _fail(f"duplicate revision for {repo}")
            model_revisions[repo] = ref
        from chimeraforge.planner.checkpoint import revisions

        try:
            revisions(model_revisions, model)
        except ValueError as exc:
            _fail(str(exc))
        if measure_first:
            _fail("--measure uses Ollama and cannot attest an HF checkpoint; measure separately")

    # Optionally benchmark the model(s) live first, folding real throughput +
    # scaling into the local corpus so the plan below runs on measured numbers.
    if measure_first and model:
        import asyncio

        from chimeraforge.commands._deps import require_extra

        require_extra("bench", "httpx")  # --measure runs the bench backends (httpx)

        from chimeraforge.measure import measure_model

        for ident in model:
            console.print(f"[dim]Measuring {ident} on ollama (live)...[/]")
            try:
                mres = asyncio.run(measure_model(ident, backend="ollama", ollama_url=ollama_url))
            except RuntimeError as exc:
                console.print(f"[red]Error measuring '{escape(ident)}':[/] {escape(str(exc))}")
                raise typer.Exit(code=1)
            console.print(
                f"[green]Measured[/] {ident}: {mres.tps_n1} tok/s"
                + (f", eta(N={mres.n_concurrent})={mres.eta_at_n}" if mres.eta_at_n else "")
            )

    # A measured profile replaces the typed-in guesses -- but only where the caller
    # did NOT type something. An explicit flag is a deliberate scenario ("what if
    # traffic tripled"), and silently overwriting it with yesterday's measurement
    # would answer a question nobody asked.
    profile_applied: list[str] = []
    if workload_profile:
        from chimeraforge.workload import WorkloadError, WorkloadProfile

        try:
            wp = WorkloadProfile.load(workload_profile)
        except WorkloadError as exc:
            _fail(escape(str(exc)))

        # Click knows exactly which parameters came from the command line; sniffing
        # sys.argv would miss env vars and break under any programmatic invocation.
        #
        # Compared by NAME, not identity. Typer 0.27 vendors its own Click, so the
        # value returned here is a `typer._click.core.ParameterSource` member and an
        # `is` (or even `==`) test against the real `click.core` enum is False --
        # which silently made every explicit flag look unset, so the profile
        # overwrote it. Passed under Typer 0.25, failed under 0.27.
        def _was_passed(param: str) -> bool:
            return getattr(ctx.get_parameter_source(param), "name", None) == "COMMANDLINE"

        explicit = {p for p in _PROFILE_FLAG.values() if _was_passed(p)}
        for key, value in wp.plan_kwargs().items():
            flag = _PROFILE_FLAG[key]
            if flag in explicit:
                continue
            if key == "request_rate":
                request_rate = value
            elif key == "prompt_tokens":
                prompt_tokens = value
            elif key == "avg_tokens":
                avg_tokens = value
            elif key == "workload_cv2":
                workload_cv2 = value
            elif key == "prefix_cache_hit_rate":
                prefix_cache_hit_rate = value
            profile_applied.append(f"{key}={value}")
        if not output_json:
            src = f"{wp.engine} profile captured {wp.captured_at}"
            if profile_applied:
                console.print(f"[dim]From {escape(src)}:[/] {escape(', '.join(profile_applied))}")
            if wp.absent:
                err_console.print(
                    f"[yellow]Profile did not measure:[/] {', '.join(wp.absent)} "
                    "(using the values you passed / the defaults)"
                )

    # Manual overrides need exactly one --model.
    overrides = {
        "params_b": params_b,
        "n_layers": n_layers,
        "n_kv_heads": n_kv_heads,
        "d_head": d_head,
        "hidden_size": hidden_size,
    }
    if model and any(v is not None for v in overrides.values()) and len(model) != 1:
        _fail("manual overrides require exactly one --model.")

    # `auto` and an unlisted card described with --gpu-* are resolved by the
    # engine's resolver, which raises its own actionable HardwareError. This guard
    # ran first and refused both since 0.34.0, so neither ever worked from the CLI.
    resolved_elsewhere = gpu_overrides or (hardware or "").strip().lower() == "auto"
    if not resolved_elsewhere and get_gpu(hardware) is None:
        # Refused, not substituted. This used to warn and then plan on RTX 4080 12GB
        # specs, returning a full result set about a GPU nobody asked for -- and the
        # warning went to STDOUT, so a caller stripping non-JSON lines to recover the
        # payload got those rows with nothing in the JSON recording the substitution.
        from chimeraforge.planner.hardware import GPU_DB

        _fail(
            f"'{hardware}' is not in the hardware DB, so there is nothing to plan against. "
            f"Known GPUs: {', '.join(sorted(GPU_DB))}. "
            "Run `chimeraforge plan --list-hardware` for the table."
        )

    # Core search runs through the shared service (same path the MCP server uses).
    try:
        plan_inputs = dict(
            models=list(model) if model else None,
            model_size=model_size,
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
            prompt_tokens=prompt_tokens,
            gpu_overrides=gpu_overrides,
            platform=platform,
            unified_memory_fraction=unified_memory_fraction,
            quality_from=quality_from,
            max_num_batched_tokens=chunk_budget,
            safety_target=safety_target,
            workload_cv2=workload_cv2,
            electricity_rate=electricity_rate,
            kv_quant=kv_quant,
            tensor_parallel=tp_val,
            pipeline_parallel=pp_val,
            lora_adapters=lora_adapters,
            lora_rank=lora_rank,
            lora_target=lora_target,
            pareto=pareto,
            grid_region=grid_region,
            carbon_intensity=carbon_intensity,
            mode=mode,
            use_contributions=contributions,
            cloud=cloud,
            think_time_s=think_time,
            session_turns=session_turns,
            models_path=models_path,
            ollama_url=ollama_url,
            hf_token=hf_token,
            model_revisions=model_revisions,
            allow_network=not no_network,
            overrides=overrides,
        )
        if save:
            from chimeraforge.api import PlanRequest

            PlanRequest(**plan_inputs).validate()
        result = run_plan(**plan_inputs)
        if save:
            if fleet:
                _fail("--save does not yet support heterogeneous fleets")
            from chimeraforge.api import PlanRequest, snapshot

            snapshot(PlanRequest(**plan_inputs), result).save(save)
    except FileNotFoundError:
        _fail(f"models file not found: {models_path}")
    except ResolverError as exc:
        _fail(f"resolving model: {escape(str(exc))}")
    except ValueError as exc:  # JSONDecodeError (bad models file) subclasses ValueError
        _fail(f"invalid models file '{models_path}': {exc}" if models_path else escape(str(exc)))

    candidates = result.candidates
    trace = result.trace
    frontier = result.frontier

    # Echo resolved specs (human mode only), after the search.
    if model and not output_json:
        for ident, spec in result.specs.items():
            console.print(
                f"[dim]Resolved[/] {ident} -> {spec.params_b}B "
                f"({spec.n_layers}L/{spec.n_kv_heads}kv/{spec.d_head}d) "
                f"[dim]source={spec.source}[/]"
            )

    # Launch command for the winning config (opt-in). Built from the plan's own
    # parameters, so the flags match what was actually sized.
    launch_cmd = None
    if launch and candidates:
        from chimeraforge.planner.launch import build_launch_command

        best = candidates[0]
        try:
            launch_cmd = build_launch_command(
                best,
                result.specs.get(best.model),
                context_length=context_length,
                prompt_tokens=prompt_tokens,
                kv_quant=kv_quant,
                max_num_batched_tokens=chunk_budget,
            )
        except ValueError as exc:
            # A backend with no template must not kill an otherwise-valid plan.
            err_console.print(f"[yellow]Launch command unavailable:[/] {escape(str(exc))}")

    # Self-host vs hosted API (opt-in). Priced off the winning candidate's actual
    # monthly bill, so it reflects the fleet the planner just sized.
    fleet_plan = None
    if fleet:
        from chimeraforge.planner.fleet import FleetError, parse_fleet, plan_fleet

        try:
            gpu_names = parse_fleet(fleet)
            fleet_plan = plan_fleet(
                gpu_names,
                demand_rate=request_rate,
                budget=budget,
                plan_fn=run_plan,
                # The mix supplies scale-out, so each type is priced on its own
                # merits with the same gates the single-GPU path applies.
                plan_kwargs=dict(
                    models=model or None,
                    model_size=model_size,
                    latency_slo=latency_slo,
                    quality_target=quality_target,
                    avg_tokens=avg_tokens,
                    reasoning_tokens=reasoning_tokens,
                    prefix_cache_hit_rate=prefix_cache_hit_rate,
                    duty_cycle=duty_cycle,
                    gpu_price_multiplier=gpu_price_multiplier,
                    ttft_slo=ttft_slo,
                    tpot_slo=tpot_slo,
                    context_length=context_length,
                    prompt_tokens=prompt_tokens,
                    max_num_batched_tokens=chunk_budget,
                    platform=platform,
                    quality_from=quality_from,
                    safety_target=safety_target,
                    workload_cv2=workload_cv2,
                    electricity_rate=electricity_rate,
                    kv_quant=kv_quant,
                    grid_region=grid_region,
                    carbon_intensity=carbon_intensity,
                    mode=mode,
                    use_contributions=contributions,
                    cloud=cloud,
                    think_time_s=think_time,
                    session_turns=session_turns,
                    allow_network=not no_network,
                    overrides=overrides,
                ),
            )
        except FleetError as exc:
            _fail(escape(str(exc)))

    api_cmp = None
    if compare_api and candidates:
        from chimeraforge.planner.apicost import PricingError, compare as compare_apis

        try:
            api_cmp = compare_apis(
                self_host_monthly=candidates[0].monthly_cost,
                request_rate=request_rate * duty_cycle,
                prompt_tokens=prompt_tokens,
                output_tokens=avg_tokens + reasoning_tokens,
            )
        except PricingError as exc:
            err_console.print(f"[yellow]API comparison unavailable:[/] {escape(str(exc))}")

    if output_json:
        # highlight=False + soft_wrap: emit plain JSON so it stays valid (Rich
        # would otherwise reflow long string values and corrupt them) and pipes
        # cleanly to `jq`.
        payload = format_pareto_json(frontier) if pareto else format_json(candidates)
        if launch or compare_api or fleet:
            # Wrap only under --launch/--compare-api so the default --json contract
            # (a bare array) is unchanged for every existing consumer.
            wrapped = {"candidates": json_mod.loads(payload)}
            if launch:
                wrapped["launch"] = launch_cmd.to_dict() if launch_cmd else None
            if compare_api:
                wrapped["api_comparison"] = api_cmp.to_dict() if api_cmp else None
            if fleet:
                wrapped["fleet"] = fleet_plan.to_dict() if fleet_plan else None
            payload = json_mod.dumps(wrapped, indent=2)
        # markup=False is load-bearing, not cosmetic. Rich parses square brackets
        # as style tags, so a model id containing them had text silently deleted
        # ("org/x[bold]y-7b" -> "org/xy-7b"), emitted invalid JSON escapes, or
        # raised MarkupError -- on a payload whose whole contract is being valid
        # JSON. Ids reach here from the HF Hub and from MCP callers, not just a
        # keyboard.
        console.print(payload, highlight=False, soft_wrap=True, markup=False)
    elif pareto:
        format_pareto(frontier, hardware)
    else:
        format_recommendation(
            candidates,
            hardware,
            request_rate=request_rate,
            latency_slo=latency_slo,
            quality_target=quality_target,
            budget=budget,
            safety_target=safety_target,
            mode=mode,
        )

    if launch_cmd is not None and not output_json:
        from chimeraforge.planner.formatter import format_launch

        format_launch(launch_cmd)

    if not output_json and candidates:
        # The OS is an input, not something the planner can see; say which one the
        # engine offers were checked against.
        row = candidates[0].platform or "unknown GPU vendor: not checked"
        console.print(
            f"[dim]Engines checked against their docs for {escape(result.platform)} ({row}); "
            "--platform linux|windows|wsl2|macos to change.[/]"
        )

    if api_cmp is not None and not output_json:
        from chimeraforge.planner.formatter import format_api_comparison

        format_api_comparison(api_cmp)

    if report:
        from chimeraforge.planner.brief import (
            BriefError,
            BriefInputs,
            build_brief,
            render_markdown,
        )

        # tp_val/pp_val may be None ('auto'); record the degree actually chosen.
        win = candidates[0] if candidates else None
        try:
            brief = build_brief(
                inputs=BriefInputs(
                    hardware=hardware,
                    model=model,
                    model_size=model_size,
                    request_rate=request_rate,
                    latency_slo_ms=latency_slo,
                    quality_target=quality_target,
                    budget_usd_month=budget,
                    avg_output_tokens=avg_tokens,
                    reasoning_tokens=reasoning_tokens,
                    prompt_tokens=prompt_tokens,
                    context_length=context_length,
                    kv_quant=kv_quant,
                    workload=workload,
                    duty_cycle=duty_cycle,
                    tensor_parallel=win.tensor_parallel if win else (tp_val or 1),
                    pipeline_parallel=win.pipeline_parallel if win else (pp_val or 1),
                    prefix_cache_hit_rate=prefix_cache_hit_rate,
                    gpu_price_multiplier=gpu_price_multiplier,
                    safety_target=safety_target,
                    lora_adapters=lora_adapters,
                    lora_rank=lora_rank,
                    lora_target=lora_target,
                    ttft_slo_ms=ttft_slo,
                    tpot_slo_ms=tpot_slo,
                    grid_region=grid_region,
                    carbon_intensity=carbon_intensity,
                    mode=mode,
                    use_contributions=contributions,
                    cloud=cloud,
                    think_time_s=think_time,
                    session_turns=session_turns,
                ),
                candidates=candidates,
                api_comparison=api_cmp.to_dict() if api_cmp else None,
                launch=launch_cmd.to_dict() if launch_cmd else None,
            )
        except BriefError as exc:
            # A refusal is the feature, so it exits non-zero: a CI job that writes a
            # brief must fail rather than carry on with no file where one is expected.
            err_console.print(f"[red]Brief not written:[/] {escape(str(exc))}")
            raise typer.Exit(code=1) from exc

        path = Path(report)
        try:
            path.write_text(render_markdown(brief), encoding="utf-8")
        except OSError as exc:
            err_console.print(f"[red]Could not write {escape(str(path))}:[/] {escape(str(exc))}")
            raise typer.Exit(code=1) from exc
        if not output_json:
            console.print()
            console.print(f"[green]Decision brief written to[/] [bold]{escape(str(path))}[/]")

    if fleet_plan is not None and not output_json:
        from chimeraforge.planner.formatter import format_fleet

        format_fleet(fleet_plan)

    if not candidates and trace:
        from chimeraforge.planner.engine import summarize_trace

        # An empty result with no reason is indistinguishable from "you asked wrong".
        # The commonest case is the default --budget of 100 USD/month silently excluding
        # every datacenter GPU: an H100 at the DB's own $2.50/hr is ~$1,825/month, so the
        # most obvious question anyone can ask came back as `[]` with nothing to read.
        #
        # Under --json this goes to STDERR, not stdout: the payload stays exactly one JSON
        # array so `| jq` keeps working, and the diagnosis is still there for anyone who
        # reads the stream a failure would normally be reported on.
        lines = summarize_trace(trace)
        if output_json:
            err_console.print("Why nothing fit:", highlight=False)
            for line in lines:
                err_console.print(f"  - {line}", highlight=False)
        else:
            console.print("\n[bold]Why nothing fit:[/]")
            for line in lines:
                console.print(f"  [yellow]-[/] {line}")
