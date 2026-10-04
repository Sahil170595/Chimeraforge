"""Advisories: where a plan sits relative to published guidance it does not model.

An advisory predicts nothing. It says that a plan is in a region where a cited
source says a technique is worth considering, quotes the source, and states what
the source says it will not do. Every condition below maps to a sentence in a
source, read at a pinned version, so none is a tuned threshold.
"""

from __future__ import annotations

# Zhong et al., read 2026-10-01 from arXiv (abstract and Sec. 7 "Discussion").
DISTSERVE = (
    "DistServe: Disaggregating Prefill and Decoding for Goodput-optimized Large "
    "Language Model Serving (OSDI 2024, arXiv:2401.09670)"
)
# Engines whose own docs, at the tag the planner's other engine facts were read at,
# document prefill/decode disaggregation. TGI v3.3.7 and Ollama document none.
DISAGG_ENGINE_DOCS = {
    "vllm": "https://github.com/vllm-project/vllm/blob/v0.30.0/docs/features/disagg_prefill.md",
    "sglang": (
        "https://github.com/sgl-project/sglang/blob/v0.5.20/docs/docs/advanced_features/"
        "pd_disaggregation.mdx"
    ),
}


def disaggregation_advisory(
    *,
    backend: str,
    ttft_slo: float | None,
    tpot_slo: float | None,
    gpus_total: int,
    batch_mode: bool,
    ttft_ms: float,
    tpot_ms: float,
    decode_tokens: int,
    prompt_tokens: int,
    interconnect_gbps: float,
    gpu_name: str,
) -> str:
    """The advisory for one candidate, or "" outside the documented region.

    In region: both TTFT and TPOT are gated (DistServe's premise -- colocated
    systems "have to prioritize one latency over the other, or over-provision
    compute resources to meet both"); serving is online (DistServe Sec. 7: for
    offline throughput work chunked prefill "may be preferred"); the fleet has
    more than one GPU (a single GPU cannot hold separate prefill and decode
    instances); and the engine documents the feature.
    """
    doc = DISAGG_ENGINE_DOCS.get(backend)
    if doc is None or batch_mode or not (ttft_slo and tpot_slo) or gpus_total < 2:
        return ""
    decode_ms = decode_tokens * tpot_ms
    share = ttft_ms / (ttft_ms + decode_ms) if ttft_ms + decode_ms > 0 else 0.0
    link = (
        f"{gpu_name} interconnect {interconnect_gbps:g} GB/s"
        if interconnect_gbps > 0
        else f"{gpu_name} interconnect unknown"
    )
    return (
        "disaggregation advisory: this plan gates TTFT and TPOT separately, the setting "
        "where splitting prefill and decode onto different GPUs is considered -- "
        f"{DISTSERVE} finds that colocated systems 'have to prioritize one latency over "
        "the other, or over-provision compute resources to meet both', and the engine's "
        f"docs ({doc}) give tuning TTFT and inter-token latency separately and "
        "controlling tail inter-token latency as its uses. No speedup is predicted: "
        "vLLM's docs mark the feature experimental and state 'Disaggregated prefill "
        "DOES NOT improve throughput', and chunked prefill (--max-num-batched-tokens) "
        "targets the same tail-latency problem. Context from this plan: prefill is "
        f"{share:.0%} of a request's modeled service time ({prompt_tokens} prompt, {decode_tokens} "
        f"output tokens); the KV handoff needs a fast link ({link}); and DistServe "
        "notes that with 'only a few or even a single GPU' the design space 'is "
        "significantly limited'"
    )
