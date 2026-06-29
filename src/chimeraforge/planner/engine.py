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
    DEFAULT_PROMPT_TOKENS,
    HIGH_VARIANCE_CV2,
    MODEL_ARCH,
    MODEL_PARAMS_B,
    QUANT_BPW,
    QUANT_LEVELS,
)
from chimeraforge.planner.hardware import get_gpu
from chimeraforge.planner.models import PlannerModels
from chimeraforge.planner.resolver import (
    SOURCE_MANUAL,
    SOURCE_REGISTRY,
    SOURCE_REGISTRY_APPROX,
    ModelSpec,
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
    model_source: str = SOURCE_REGISTRY
    provenance: dict[str, str] = field(default_factory=dict)
    # KV-cache-bound max concurrent sequences a single GPU can hold (0.6.0).
    max_concurrent_seqs: int = 0
    # Latency split (0.6.0): prefill time-to-first-token + decode time-per-output-token.
    ttft_ms: float = 0.0
    tpot_ms: float = 0.0
    # Continuous-batching: requests served concurrently per GPU (B; 1 = single-stream).
    effective_batch: int = 1


def find_models_for_size(target_size: str) -> list[str]:
    """Map size class (1b, 3b, 8b, etc.) to available models."""
    target = target_size.lower().replace("b", "")
    try:
        target_val = float(target)
    except ValueError:
        return list(MODEL_PARAMS_B.keys())

    if target_val <= 0:
        return list(MODEL_PARAMS_B.keys())

    matches = []
    for model, params in MODEL_PARAMS_B.items():
        if abs(params - target_val) / target_val < 0.5:
            matches.append(model)

    if not matches:
        closest = min(MODEL_PARAMS_B, key=lambda m: abs(MODEL_PARAMS_B[m] - target_val))
        matches = [closest]

    return matches


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

    candidates: list[Candidate] = []

    for model in target_models:
        spec = specs.get(model)
        if spec is None and model in MODEL_PARAMS_B:
            spec = ModelSpec.from_registry(model)
        params_known = spec is not None or model in MODEL_PARAMS_B
        params_b = spec.params_b if spec else MODEL_PARAMS_B.get(model, 3.0)
        arch = spec.arch() if spec else None
        family = spec.family if spec else None
        # Don't mislabel an unknown model as "registry": only a real registry hit
        # or a resolved spec has a trustworthy source. (CLI paths always populate
        # specs; this guards direct enumerate_candidates() library callers.)
        model_source = (
            spec.source if spec else (SOURCE_REGISTRY if model in MODEL_PARAMS_B else SOURCE_MANUAL)
        )

        # TTFT (prefill) is compute-bound: same for all quants/backends of a model
        # on this GPU and prompt length, so compute it once. 0.0 when GPU compute
        # is unknown -> latency falls back to decode-only.
        ttft_ms = models.latency.predict_ttft_ms(params_b, prompt_tokens, hardware)

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
            # Gate 1: VRAM (exact for off-registry models via resolved arch)
            vram = models.vram.predict(model, quant, context_length, params_b=params_b, arch=arch)
            if vram > hw_vram:
                _reject(model, quant, "vram", f"{vram:.1f}GB > {hw_vram:.0f}GB capacity")
                continue

            # KV-cache-bound concurrency a single GPU can hold + per-sequence KV
            # size; both feed the batched-throughput model (0.6.0).
            arch_eff = arch or MODEL_ARCH.get(model, DEFAULT_ARCH)
            max_seqs = models.vram.max_concurrent_seqs(
                params_b, quant, arch_eff, context_length, hw_vram
            )
            kv_per_seq_gb = models.vram.kv_cache_gb(arch_eff, context_length, 1)

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
                    n1_tps = models.throughput.roofline_tps(params_b, quant, hardware)
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

                best = None  # (n, b, per_gpu_tps, per_req_tps, lat)
                for n in range(1, 17):
                    for b in batch_grid:
                        per_gpu = models.throughput.batched_decode_tps(
                            n1_tps, kv_per_seq_gb, b, hardware, params_b
                        )
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
                    cap_tps = 16 * models.throughput.batched_decode_tps(
                        n1_tps, kv_per_seq_gb, b_max, hardware, params_b
                    )
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

                # Gate 4: Cost
                monthly = models.cost.predict_monthly(hw_cost_hr) * best_n
                if monthly > budget:
                    _reject(
                        model,
                        quant,
                        "budget",
                        f"{backend}: ${monthly:.0f}/mo (N={best_n}) > ${budget:.0f}",
                    )
                    continue

                # Cost per 1M tokens: total_tps is N GPUs' throughput, so the rate
                # must be N GPUs' cost (else understated by N). N identical replicas
                # leave $/token unchanged -- which is the correct invariant.
                cost_1m = models.cost.predict_cost_per_1m(total_tps, hw_cost_hr * best_n)

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
                        model_source=model_source,
                        provenance=provenance,
                        max_concurrent_seqs=max_seqs,
                        ttft_ms=round(ttft_ms, 1),
                        tpot_ms=round(tpot_ms, 1),
                        effective_batch=best_b,
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
