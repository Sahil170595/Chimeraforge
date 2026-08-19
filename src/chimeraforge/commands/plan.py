"""`plan` command - predictive capacity planner."""

from __future__ import annotations

import json as json_mod

import typer
from rich.console import Console
from rich.markup import escape

# constants is pure-stdlib (no heavy deps), so this module-level import is safe for
# the `--version` fast path; it supplies flag defaults/choices.
from chimeraforge.planner.constants import (
    DEFAULT_ELECTRICITY_RATE,
    DEFAULT_KV_QUANT,
    KV_QUANT_BYTES,
)

console = Console()
# Diagnostics go here so `--json` output on stdout stays exactly one document. A caller
# that has to strip lines before parsing does not have a contract.
err_console = Console(stderr=True)


def plan(
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
        5000.0,
        "--latency-slo",
        "-l",
        help="Max p95 latency in milliseconds.",
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
        help="GPU name from hardware DB.",
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
    measure_first: bool = typer.Option(
        False,
        "--measure",
        help="Benchmark the --model live first (real throughput+scaling), then plan "
        "on the measured numbers. Requires a live backend serving the model.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON instead of Rich tables.",
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
            from chimeraforge.planner.hardware import GPU_DB

            payload = [
                {
                    "name": spec.name,
                    "vram_gb": spec.vram_gb,
                    "bandwidth_gbps": spec.bandwidth_gbps,
                    "cost_per_hour": spec.cost_per_hour,
                    "fp16_tflops": spec.fp16_tflops,
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

            console.print(_json.dumps({"error": msg}), highlight=False, soft_wrap=True)
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
    if not 0.0 < duty_cycle <= 1.0:
        _fail("--duty-cycle must be greater than 0.0 and at most 1.0.")
    if gpu_price_multiplier <= 0:
        _fail("--gpu-price-multiplier must be positive.")
    if electricity_rate < 0:
        _fail("--electricity-rate must be non-negative.")
    kv_quant = kv_quant.lower()
    if kv_quant not in KV_QUANT_BYTES:
        _fail(f"--kv-quant must be one of: {', '.join(KV_QUANT_BYTES)}.")

    def _parse_degree(raw: str, flag: str) -> int | None:
        raw = raw.strip().lower()
        if raw == "auto":
            return None
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
    if latency_slo <= 0:
        _fail("--latency-slo must be positive.")
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

    # Manual overrides need exactly one --model.
    overrides = {
        "params_b": params_b,
        "n_layers": n_layers,
        "n_kv_heads": n_kv_heads,
        "d_head": d_head,
    }
    if model and any(v is not None for v in overrides.values()) and len(model) != 1:
        _fail("manual overrides require exactly one --model.")

    if get_gpu(hardware) is None:
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
        result = run_plan(
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
            context_length=context_length,
            prompt_tokens=prompt_tokens,
            safety_target=safety_target,
            workload_cv2=workload_cv2,
            electricity_rate=electricity_rate,
            kv_quant=kv_quant,
            tensor_parallel=tp_val,
            pipeline_parallel=pp_val,
            pareto=pareto,
            models_path=models_path,
            ollama_url=ollama_url,
            hf_token=hf_token,
            allow_network=not no_network,
            overrides=overrides,
        )
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
            )
        except ValueError as exc:
            # A backend with no template must not kill an otherwise-valid plan.
            err_console.print(f"[yellow]Launch command unavailable:[/] {escape(str(exc))}")

    # Self-host vs hosted API (opt-in). Priced off the winning candidate's actual
    # monthly bill, so it reflects the fleet the planner just sized.
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
        if launch or compare_api:
            # Wrap only under --launch/--compare-api so the default --json contract
            # (a bare array) is unchanged for every existing consumer.
            wrapped = {"candidates": json_mod.loads(payload)}
            if launch:
                wrapped["launch"] = launch_cmd.to_dict() if launch_cmd else None
            if compare_api:
                wrapped["api_comparison"] = api_cmp.to_dict() if api_cmp else None
            payload = json_mod.dumps(wrapped, indent=2)
        console.print(payload, highlight=False, soft_wrap=True)
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
        )

    if launch_cmd is not None and not output_json:
        from chimeraforge.planner.formatter import format_launch

        format_launch(launch_cmd)

    if api_cmp is not None and not output_json:
        from chimeraforge.planner.formatter import format_api_comparison

        format_api_comparison(api_cmp)

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
