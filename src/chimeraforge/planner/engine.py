"""4-gate search engine for capacity planning.

Searches the (model, quant, backend, N) solution space and filters
through VRAM, quality, latency, and budget gates to find viable
deployment configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chimeraforge.planner.constants import (
    BACKEND_CONTINUOUS_BATCHING,
    BACKENDS,
    DEFAULT_ARCH,
    DEFAULT_ELECTRICITY_RATE,
    DEFAULT_KV_QUANT,
    DEFAULT_PROMPT_TOKENS,
    HIGH_VARIANCE_CV2,
    KV_DTYPE_BYTES,
    KV_QUANT_BYTES,
    MODEL_ARCH,
    MODEL_PARAMS_B,
    NVLINK_DOMAIN_SIZE,
    QUANT_BPW,
    QUANT_LEVELS,
    TP_SEARCH_DEGREES,
)
from chimeraforge.planner.hardware import get_gpu
from chimeraforge.planner.models import PlannerModels
from chimeraforge.planner.resolver import (
    SOURCE_MANUAL,
    SOURCE_REGISTRY,
    SOURCE_REGISTRY_APPROX,
    ModelSpec,
    ResolverError,
)


@dataclass
class Candidate:
    model: str
    quant: str
    backend: str
    n_agents: int
    vram_gb: float
    quality: float
    quality_tier: str
    throughput_tps: float
    total_throughput_tps: float
    eta: float
    p95_latency_ms: float
    utilisation: float
    monthly_cost: float
    cost_per_1m_tok: float
    safety_refusal: float | None
    rtsi_risk: str
    warnings: list[str]
    # Model-agnostic metadata: where the model facts and each prediction came from.
    params_b: float = 0.0
    # Params read per token (0.14.0). Equals params_b for a dense model; smaller for
    # MoE, where VRAM sizes on total but throughput/TTFT scale with active.
    active_params_b: float = 0.0
    model_source: str = SOURCE_REGISTRY
    provenance: dict[str, str] = field(default_factory=dict)
    # KV-cache-bound max concurrent sequences a single GPU can hold (0.6.0).
    max_concurrent_seqs: int = 0
    # Latency split (0.6.0): prefill time-to-first-token + decode time-per-output-token.
    ttft_ms: float = 0.0
    tpot_ms: float = 0.0
    # Continuous-batching: requests served concurrently per GPU (B; 1 = single-stream).
    effective_batch: int = 1
    # Energy (0.8.0): board TDP, monthly electricity cost, per-token energy cost, and
    # throughput efficiency. All 0.0 when the GPU's TDP is unknown. Reported alongside
    # -- not inside -- monthly_cost/cost_per_1m_tok (cloud $/hr already bundles power).
    tdp_watts: float = 0.0
    energy_cost_month: float = 0.0
    energy_cost_per_1m_tok: float = 0.0
    perf_per_watt: float = 0.0
    # Multi-GPU parallelism (0.10.0 TP / 0.11.0 PP): degrees per replica, and total
    # fleet GPUs (N * tp * pp).
    tensor_parallel: int = 1
    pipeline_parallel: int = 1
    gpus_total: int = 0


def find_models_for_size(target_size: str) -> list[str]:
    """Map a size class (1b, 3b, 8b) to registry models, or refuse.

    Refusing matters more than matching here. This used to substitute silently in two
    ways, and both produced a confident answer about a model the registry does not hold:

      - an unparseable class ("banana") returned EVERY model, so nonsense planned fine;
      - a class outside the registry's span returned the single nearest model, so
        `--model-size 70b` answered with llama3.1-8b's 8.03B parameters and 4.55 GB of
        VRAM, with nothing in the output saying the request had been changed.

    The registry tops out near 8B, so every request above roughly 12B took that second
    path. A planner's only product is a number someone trusts, and a wrong one wearing
    the right shape is worse than a refusal — so the caller is now told what the registry
    can model and how to plan for anything else.
    """
    target = target_size.strip().lower().removesuffix("b")
    try:
        target_val = float(target)
    except ValueError:
        raise ResolverError(
            f"unrecognised --model-size {target_size!r}. {_size_class_hint()}"
        ) from None

    if target_val <= 0:
        raise ResolverError(
            f"--model-size must be positive, got {target_size!r}. {_size_class_hint()}"
        )

    matches = [
        model
        for model, params in MODEL_PARAMS_B.items()
        if abs(params - target_val) / target_val < 0.5
    ]

    if not matches:
        span = f"{min(MODEL_PARAMS_B.values())}B-{max(MODEL_PARAMS_B.values())}B"
        raise ResolverError(
            f"no registry model is within 50% of {target_size!r} "
            f"(the registry spans {span}). {_size_class_hint()}"
        )

    return matches


def _size_class_hint() -> str:
    """What the caller can do instead — named, rather than left to guess."""
    spans = ", ".join(f"{params}B" for params in sorted(MODEL_PARAMS_B.values()))
    return (
        f"The registry holds: {spans}. For anything it does not carry, pass "
        "--model <hf-repo or ollama:tag> so real parameters are resolved from the source, "
        "or --params-b <n> with a single --model to override."
    )


def enumerate_candidates(
    models: PlannerModels,
    target_models: list[str],
    hardware: str,
    request_rate: float,
    latency_slo: float,
    quality_target: float,
    budget: float,
    avg_tokens: int,
    context_length: int,
    safety_target: float | None = None,
    specs: dict[str, ModelSpec] | None = None,
    trace: list[tuple[str, str, str, str]] | None = None,
    prompt_tokens: int = DEFAULT_PROMPT_TOKENS,
    workload_cv2: float = 0.0,
    electricity_rate: float = DEFAULT_ELECTRICITY_RATE,
    kv_quant: str = DEFAULT_KV_QUANT,
    tensor_parallel: int | None = 1,
    pipeline_parallel: int | None = 1,
) -> list[Candidate]:
    """Search (model, quant, backend, N) space with gates.

    Gates: VRAM, quality, latency, budget - plus an opt-in safety gate
    (rejects cells whose refusal rate < ``safety_target``). When
    ``safety_target`` is None the safety gate is inert but each candidate
    still carries its refusal rate and RTSI risk tier.

    ``specs`` maps a model name to a resolved :class:`ModelSpec`. Off-registry
    models drive VRAM from real architecture and throughput from a roofline
    estimate; registry models fall back to bundled data with identical numbers
    to before. Every candidate records per-prediction provenance.

    ``trace`` (optional out-param): if a list is passed, each rejected cell is
    appended as ``(model, quant, gate, detail)`` so callers can explain why a
    search returned nothing. No overhead when ``None``.
    """

    def _reject(model: str, quant: str, gate: str, detail: str) -> None:
        if trace is not None:
            trace.append((model, quant, gate, detail))

    specs = specs or {}
    gpu = get_gpu(hardware)
    hw_vram = gpu.vram_gb if gpu else 12.0
    hw_cost_hr = gpu.cost_per_hour if gpu else 0.035
    # KV-cache element size: a quantized cache (q8/q4) shrinks KV VRAM and lifts the
    # concurrency cap. Only VRAM is affected -- KV-quant quality impact is unscreened.
    kv_bytes = KV_QUANT_BYTES.get(kv_quant, KV_DTYPE_BYTES)
    kv_quantized = kv_bytes != KV_DTYPE_BYTES
    # Multi-GPU parallelism interconnect for the selected GPU (NVLink/PCIe). Each of
    # tensor_parallel / pipeline_parallel is an explicit degree, or None = auto
    # (smallest degree that makes the model fit). Only one may be engaged (MVP: TP
    # and PP are not combined yet).
    interconnect_gbps = gpu.interconnect_gbps if gpu else 0.0
    tp_auto = tensor_parallel is None
    pp_auto = pipeline_parallel is None
    tp_engaged = tp_auto or (tensor_parallel or 1) > 1
    pp_engaged = pp_auto or (pipeline_parallel or 1) > 1
    if tp_engaged and pp_engaged:
        raise ValueError(
            "tensor and pipeline parallelism cannot be combined yet -- set only one of "
            "--tensor-parallel / --pipeline-parallel above 1"
        )

    def _min_degree_to_fit(
        model_id: str, quant_id: str, params: float, arch_dict: dict | None, dim: str
    ) -> int:
        """Smallest TP/PP degree in the grid whose per-GPU VRAM fits; 0 if none."""
        for d in TP_SEARCH_DEGREES:
            kw = {"tp": d} if dim == "tp" else {"pp": d}
            per_gpu = models.vram.predict(
                model_id,
                quant_id,
                context_length,
                params_b=params,
                arch=arch_dict,
                kv_bytes=kv_bytes,
                **kw,
            )
            if per_gpu <= hw_vram:
                return d
        return 0

    candidates: list[Candidate] = []

    for model in target_models:
        spec = specs.get(model)
        if spec is None and model in MODEL_PARAMS_B:
            spec = ModelSpec.from_registry(model)
        params_known = spec is not None or model in MODEL_PARAMS_B
        params_b = spec.params_b if spec else MODEL_PARAMS_B.get(model, 3.0)
        # MoE splits the parameter count in two, and the planner must use the right
        # one in each place: VRAM holds EVERY expert (total), but a decoded token
        # only reads the experts it routed to (active). Using total for throughput
        # under-predicts an MoE model by the active/total ratio -- 3.6x on
        # Mixtral-8x7B, 18x on DeepSeek-V3. Dense models: active == total.
        active_params_b = spec.active_params_b if spec else params_b
        is_moe = bool(spec and spec.is_moe)
        arch = spec.arch() if spec else None
        family = spec.family if spec else None
        # Don't mislabel an unknown model as "registry": only a real registry hit
        # or a resolved spec has a trustworthy source. (CLI paths always populate
        # specs; this guards direct enumerate_candidates() library callers.)
        model_source = (
            spec.source if spec else (SOURCE_REGISTRY if model in MODEL_PARAMS_B else SOURCE_MANUAL)
        )

        # Hidden size drives the TP all-reduce volume: from the resolved spec, else
        # the standard params ~= 12 * n_layers * hidden^2 transformer estimate.
        arch_model = arch or MODEL_ARCH.get(model, DEFAULT_ARCH)
        hidden_size = (spec.hidden_size if (spec and spec.hidden_size) else 0) or int(
            round((params_b * 1e9 / (12 * max(arch_model["n_layers"], 1))) ** 0.5)
        )

        # TTFT (prefill) is compute-bound: same for all quants/backends of a model
        # on this GPU and prompt length, so compute it once. 0.0 when GPU compute
        # is unknown -> latency falls back to decode-only.
        # Prefill FLOPs scale with the params a token actually passes through, so
        # MoE prefill uses active params too.
        ttft_ms = models.latency.predict_ttft_ms(active_params_b, prompt_tokens, hardware)

        # ``alias`` is the registry model whose measured data we may reuse: the
        # model itself for registry hits, the matched model for offline
        # approximations, else None for genuinely off-registry models (which use
        # first-principles roofline + estimated/unknown quality & safety).
        alias = (spec.registry_alias if spec else None) or (
            model if model in MODEL_PARAMS_B else None
        )
        use_measured = alias is not None
        lookup_name = alias or model

        # A fully-specified tag (e.g. ``...:q8_0``, ``...:q4_0``) IS that quant --
        # evaluate only it (any quant with a known bpw, not just the search
        # ladder). An identifier without a native quant searches all quants.
        quants = [spec.native_quant] if (spec and spec.native_quant in QUANT_BPW) else QUANT_LEVELS

        for quant in quants:
            # TP/PP degree: explicit, or auto = smallest degree that fits VRAM. Only
            # one dimension is engaged (validated above); the other stays 1.
            tp, pp = 1, 1
            if tp_auto:
                tp = _min_degree_to_fit(model, quant, params_b, arch, "tp")
            elif pp_auto:
                pp = _min_degree_to_fit(model, quant, params_b, arch, "pp")
            else:
                tp = max(int(tensor_parallel), 1)
                pp = max(int(pipeline_parallel), 1)
            if tp == 0 or pp == 0:
                dim = "TP" if tp_auto else "PP"
                _reject(model, quant, "vram", f"exceeds VRAM even at {dim}={TP_SEARCH_DEGREES[-1]}")
                continue

            # Gate 1: VRAM per GPU (weights shard 1/(TP*PP); exact off-registry via arch)
            vram = models.vram.predict(
                model,
                quant,
                context_length,
                params_b=params_b,
                arch=arch,
                kv_bytes=kv_bytes,
                tp=tp,
                pp=pp,
            )
            if vram > hw_vram:
                detail = f"{vram:.1f}GB/GPU > {hw_vram:.0f}GB"
                par = f" (TP={tp})" if tp > 1 else (f" (PP={pp})" if pp > 1 else "")
                _reject(model, quant, "vram", detail + par)
                continue

            # KV-cache-bound concurrency one GPU of the TP*PP group holds + per-sequence
            # (unsharded) KV size; both feed the batched/TP/PP throughput models.
            arch_eff = arch or MODEL_ARCH.get(model, DEFAULT_ARCH)
            max_seqs = models.vram.max_concurrent_seqs(
                params_b, quant, arch_eff, context_length, hw_vram, kv_bytes=kv_bytes, tp=tp, pp=pp
            )
            kv_per_seq_gb = models.vram.kv_cache_gb(arch_eff, context_length, 1, kv_bytes=kv_bytes)

            # Gate 2: Quality (with provenance: measured | estimated | unknown)
            quality, quality_source = models.quality.estimate(lookup_name, quant, family)
            if quality < quality_target:
                _reject(model, quant, "quality", f"{quality:.2f} < target {quality_target}")
                continue

            quality_tier = models.quality.quality_tier(lookup_name, quant, family)

            # Safety gate (Gate 5): safety data is per (model, quant) and
            # backend-independent, so evaluate it here - before the backend/N
            # loop - to skip known-unsafe cells early. Opt-in via safety_target.
            safety_refusal = models.safety.predict_refusal(lookup_name, quant)
            rtsi_risk = models.safety.rtsi_risk(lookup_name, quant)
            if (
                safety_target is not None
                and safety_refusal is not None
                and safety_refusal < safety_target
            ):
                _reject(
                    model, quant, "safety", f"refusal {safety_refusal:.2f} < target {safety_target}"
                )
                continue  # known-unsafe cell: refusal rate below target

            for backend in BACKENDS:
                # Predict N=1 throughput, recording provenance. A direct
                # (model|backend|quant) lookup is "measured"; the bundled
                # fp16/power-law fallback for a registry(-aliased) model, or a
                # roofline estimate for a genuinely off-registry model, is
                # "estimated".
                used_roofline = False
                if f"{lookup_name}|{backend}|{quant}" in models.throughput.lookup:
                    n1_tps = models.throughput.predict(lookup_name, backend, quant, hardware)
                    throughput_source = "measured"
                elif use_measured:
                    n1_tps = models.throughput.predict(lookup_name, backend, quant, hardware)
                    throughput_source = "estimated"
                else:
                    n1_tps = models.throughput.roofline_tps(active_params_b, quant, hardware)
                    throughput_source = "estimated"
                    used_roofline = True

                # Search (N replicas x B batch-per-GPU) for the cheapest config
                # meeting the rate under the latency SLO. N replicas scale linearly
                # (eta=1). For a continuous-batching backend (vLLM/TGI) one GPU
                # serves B concurrent sequences -- aggregate throughput rises with
                # B up to the KV-cache cap -- so a single GPU can replace several
                # single-stream (Ollama) replicas. Higher B trades per-request
                # latency (TPOT) for aggregate throughput; we pick the smallest
                # feasible (N, then B) for lowest cost + lowest latency.
                eta = 1.0
                required_tps = request_rate * avg_tokens
                batched = BACKEND_CONTINUOUS_BATCHING.get(backend, False)
                b_max = max_seqs if (batched and max_seqs > 1) else 1
                batch_grid = _batch_grid(b_max)

                # A "unit" is a parallel group of `tp*pp` GPUs (per_gpu is the group's
                # aggregate); N such groups run in parallel -> total GPUs = N*tp*pp.
                def _unit_tps(b: int) -> float:
                    if tp > 1:
                        return models.throughput.tp_decode_tps(
                            n1_tps,
                            kv_per_seq_gb,
                            b,
                            tp,
                            hidden_size,
                            arch_eff["n_layers"],
                            interconnect_gbps,
                            hardware,
                            active_params_b,
                        )
                    if pp > 1:
                        return models.throughput.pp_decode_tps(
                            n1_tps,
                            kv_per_seq_gb,
                            b,
                            pp,
                            hidden_size,
                            interconnect_gbps,
                            hardware,
                            active_params_b,
                        )
                    return models.throughput.batched_decode_tps(
                        n1_tps, kv_per_seq_gb, b, hardware, active_params_b
                    )

                best = None  # (n, b, per_gpu_tps, per_req_tps, lat)
                for n in range(1, 17):
                    for b in batch_grid:
                        per_gpu = _unit_tps(b)
                        if n * per_gpu < required_tps:
                            continue
                        per_req = per_gpu / b
                        lat = models.latency.predict_p95(
                            lookup_name,
                            backend,
                            request_rate,
                            n_agents=n,
                            avg_tokens=avg_tokens,
                            quant=quant,
                            hardware=hardware,
                            n1_tps=per_req,
                            ttft_ms=ttft_ms,
                            concurrent_per_agent=b,
                            service_cv2=workload_cv2,
                        )
                        if lat["p95_ms"] <= latency_slo:
                            best = (n, b, per_gpu, per_req, lat)
                            break
                    if best:
                        break

                if best is None:
                    cap_tps = 16 * _unit_tps(b_max)
                    if cap_tps < required_tps:
                        _reject(
                            model,
                            quant,
                            "throughput",
                            f"{backend}: max {cap_tps:.0f} tok/s at N=16 B={b_max} "
                            f"< {required_tps:.0f} needed",
                        )
                    else:
                        _reject(
                            model, quant, "latency", f"{backend}: p95 > {latency_slo:.0f}ms SLO"
                        )
                    continue

                best_n, best_b, per_gpu_tps, per_req_tps, lat = best
                total_tps = best_n * per_gpu_tps
                tpot_ms = 1000.0 / per_req_tps if per_req_tps > 0 else 0.0
                # Each of the N replicas is a parallel group of `tp*pp` GPUs, so the
                # fleet is N*tp*pp GPUs -- cost and energy scale with the total, not N.
                total_gpus = best_n * tp * pp

                # Gate 4: Cost (N replicas x TP*PP GPUs each)
                monthly = models.cost.predict_monthly(hw_cost_hr) * total_gpus
                if monthly > budget:
                    tp_note = f" x TP={tp}" if tp > 1 else (f" x PP={pp}" if pp > 1 else "")
                    _reject(
                        model,
                        quant,
                        "budget",
                        f"{backend}: ${monthly:.0f}/mo (N={best_n}{tp_note}) > ${budget:.0f}",
                    )
                    continue

                # Cost per 1M tokens: total_tps is the fleet throughput, so the rate
                # must be the fleet's (N*tp) GPU cost (else understated). Identical
                # replicas leave $/token unchanged -- the correct invariant.
                cost_1m = models.cost.predict_cost_per_1m(total_tps, hw_cost_hr * total_gpus)

                # Energy (0.8.0): reported alongside the hardware cost, not summed into
                # the budget gate (cloud $/hr already bundles power). 0.0 when TDP unknown.
                tdp_watts = gpu.tdp_watts if gpu else 0.0
                energy_month = models.cost.energy_cost_per_month(
                    tdp_watts, total_gpus, electricity_rate
                )
                energy_1m = models.cost.energy_cost_per_1m(
                    total_tps, tdp_watts, total_gpus, electricity_rate
                )
                ppw = models.cost.perf_per_watt(total_tps, tdp_watts, total_gpus)

                safety_source = "measured" if safety_refusal is not None else "unknown"
                # VRAM is first-principles either way; it's "measured" when arch
                # came from the registry, "estimated" when from a resolved spec.
                vram_source = "measured" if use_measured else "estimated"
                provenance = {
                    "vram": vram_source,
                    "throughput": throughput_source,
                    "quality": quality_source,
                    "safety": safety_source,
                }

                warnings = []
                if is_moe:
                    warnings.append(
                        f"MoE: {active_params_b}B of {params_b}B params active per token "
                        f"({spec.experts_per_token}/{spec.num_experts} experts). VRAM sizes "
                        "on total (all experts resident); throughput/TTFT on active. Expert "
                        "parallelism and routing load-imbalance are not modelled"
                    )
                if kv_quantized:
                    warnings.append(
                        f"KV cache quantized ({kv_quant}): VRAM/concurrency reflect it, but "
                        "the (small) quality impact of KV-quant is not screened here"
                    )
                if tp > 1:
                    warnings.append(
                        f"tensor-parallel TP={tp} ({total_gpus} GPUs total): throughput is a "
                        "first-principles estimate (all-reduce comms modelled, not measured)"
                    )
                    # PCIe links (<=128 GB/s) vs NVLink (>=600): TP comms is far costlier.
                    if 0 < interconnect_gbps < 200:
                        warnings.append(
                            f"TP over PCIe (~{interconnect_gbps:.0f} GB/s): high comms overhead -- "
                            "prefer an NVLink GPU or pipeline parallelism (per vLLM guidance)"
                        )
                    if tp > NVLINK_DOMAIN_SIZE:
                        warnings.append(
                            f"TP={tp} exceeds the {NVLINK_DOMAIN_SIZE}-GPU NVLink domain -- "
                            "crossing a node boundary collapses TP throughput"
                        )
                if pp > 1:
                    warnings.append(
                        f"pipeline-parallel PP={pp} ({total_gpus} GPUs total): throughput is a "
                        "first-principles estimate (pipeline bubble modelled, not measured)"
                    )
                    # PP needs enough in-flight sequences to fill the pipeline; at low
                    # batch the GPipe bubble wastes most of the parallelism.
                    if best_b < pp:
                        warnings.append(
                            f"PP={pp} under-filled at batch {best_b}: the pipeline bubble caps "
                            f"efficiency near {best_b}/{best_b + pp - 1:.0f} -- raise concurrency "
                            "or use a continuous-batching backend"
                        )
                if workload_cv2 >= HIGH_VARIANCE_CV2:
                    warnings.append(
                        "high service-time variance (agent/bursty): analytical p95 "
                        "under-estimates the tail -- validate with a load test"
                    )
                if lat["saturated"]:
                    warnings.append("utilisation > 70% safety cap")
                if quality_tier == "concerning":
                    warnings.append("quality drop concerning (-10 to -15pp)")
                if best_n > 8:
                    warnings.append(f"requires {best_n} GPU instances")
                if vram / hw_vram > 0.9:
                    warnings.append("VRAM usage > 90% of capacity")
                if safety_target is not None and safety_refusal is None:
                    warnings.append("safety not screened (no TR134/TR142 data)")
                if rtsi_risk in ("HIGH", "MODERATE"):
                    warnings.append(f"RTSI refusal-instability risk: {rtsi_risk}")
                if model_source == SOURCE_REGISTRY_APPROX:
                    warnings.append(
                        f"approximated to registry model '{alias}' by family/size; "
                        "metadata not from the actual model"
                    )
                if used_roofline:
                    warnings.append(
                        f"off-registry model ({model_source}): throughput is a roofline "
                        "estimate, not measured"
                    )
                if not params_known:
                    warnings.append(
                        f"params/architecture unknown; assumed {params_b:.1f}B -- "
                        "pass a resolvable --model or manual overrides"
                    )
                if quality_source == "unknown":
                    warnings.append("quality unscreened (neutral 0.5 prior, not measured)")
                elif quality_source == "estimated" and not use_measured:
                    warnings.append("quality estimated from family prior, not measured")

                candidates.append(
                    Candidate(
                        model=model,
                        quant=quant,
                        backend=backend,
                        n_agents=best_n,
                        vram_gb=round(vram, 2),
                        quality=round(quality, 3),
                        quality_tier=quality_tier,
                        throughput_tps=round(n1_tps, 1),
                        total_throughput_tps=round(total_tps, 1),
                        eta=round(eta, 3),
                        p95_latency_ms=round(lat["p95_ms"], 1),
                        utilisation=round(lat["utilisation"], 3),
                        monthly_cost=round(monthly, 2),
                        cost_per_1m_tok=round(cost_1m, 4),
                        safety_refusal=(
                            round(safety_refusal, 3) if safety_refusal is not None else None
                        ),
                        rtsi_risk=rtsi_risk,
                        warnings=warnings,
                        params_b=round(params_b, 4),
                        active_params_b=round(active_params_b, 4),
                        model_source=model_source,
                        provenance=provenance,
                        max_concurrent_seqs=max_seqs,
                        ttft_ms=round(ttft_ms, 1),
                        tpot_ms=round(tpot_ms, 1),
                        effective_batch=best_b,
                        tdp_watts=round(tdp_watts, 1),
                        energy_cost_month=round(energy_month, 2),
                        energy_cost_per_1m_tok=round(energy_1m, 4),
                        perf_per_watt=round(ppw, 4),
                        tensor_parallel=tp,
                        pipeline_parallel=pp,
                        gpus_total=total_gpus,
                    )
                )

    # Sort by monthly cost (primary), then by quality (secondary, desc)
    candidates.sort(key=lambda c: (c.monthly_cost, -c.quality))
    return candidates


def pareto_frontier(candidates: list[Candidate]) -> list[Candidate]:
    """Non-dominated configs on (cost down, p95 latency down, quality up).

    For a fixed workload every candidate already meets the throughput + SLO gates,
    so the remaining trade-offs are cost vs latency vs quality. A candidate is
    dominated if another is no worse on all three and strictly better on one. The
    frontier is the menu of real trade-offs (cheapest, lowest-latency, highest
    quality, and the bends between) -- not a single cost-sorted point. Returned
    sorted by monthly cost ascending.
    """

    def dominates(b: Candidate, a: Candidate) -> bool:
        no_worse = (
            b.monthly_cost <= a.monthly_cost
            and b.p95_latency_ms <= a.p95_latency_ms
            and b.quality >= a.quality
        )
        strictly_better = (
            b.monthly_cost < a.monthly_cost
            or b.p95_latency_ms < a.p95_latency_ms
            or b.quality > a.quality
        )
        return no_worse and strictly_better

    front = [a for a in candidates if not any(dominates(b, a) for b in candidates if b is not a)]
    front.sort(key=lambda c: (c.monthly_cost, c.p95_latency_ms))
    return front


def _batch_grid(b_max: int) -> list[int]:
    """Batch sizes to try, 1..b_max on a log grid (cheap search, B can be large)."""
    if b_max <= 1:
        return [1]
    grid, b = [], 1
    while b < b_max:
        grid.append(b)
        b *= 2
    grid.append(b_max)
    return grid


# Order in which a (model, quant) cell is tested; used to pick the *binding*
# gate (the furthest one reached) when summarising a failed search.
_GATE_ORDER = ["vram", "quality", "safety", "throughput", "latency", "budget"]


def summarize_trace(trace: list[tuple[str, str, str, str]]) -> list[str]:
    """Turn a rejection trace into human-readable 'why nothing fit' lines.

    For each model, reports the furthest gate any of its quants reached (the
    binding constraint) plus one concrete example detail.
    """
    by_model: dict[str, list[tuple[str, str, str]]] = {}
    for model, quant, gate, detail in trace:
        by_model.setdefault(model, []).append((quant, gate, detail))

    lines: list[str] = []
    for model, rejects in by_model.items():
        furthest = max(
            rejects, key=lambda r: _GATE_ORDER.index(r[1]) if r[1] in _GATE_ORDER else -1
        )
        _, gate, detail = furthest
        lines.append(f"{model}: blocked at {gate} gate - {detail}")
    return lines
