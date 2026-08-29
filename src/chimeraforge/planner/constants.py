"""Constants - quant levels, model registry, backends.

Extracted from TR133 research. No repo-specific paths or imports.
"""

from __future__ import annotations

# Canonical search ladder for the planner's quant sweep (highest precision first).
# Ordered by MEASURED width, descending. Q8_0 is 8.5 bpw (a 34-byte block per 32
# weights) so it is wider than FP8's exact 8.0, and Q4_K_M's 4.90 is wider than
# a group-128 W4A16's ~4.5 -- under the old approximations both pairs appeared
# to be the other way round.
QUANT_LEVELS = ["FP16", "Q8_0", "FP8", "Q6_K", "Q5_K_M", "Q4_K_M", "AWQ", "GPTQ", "Q3_K_S", "Q2_K"]

# Effective bits-per-weight, INCLUDING block scales and the mixed-precision
# tensor promotions the k-quants apply. Broader than QUANT_LEVELS so a model's
# *native* quant (e.g. an Ollama `q4_0`/`IQ4_XS` tag) resolves to a real VRAM
# footprint instead of silently defaulting to FP16.
#
# Source: measured from bartowski/Meta-Llama-3-8B-Instruct-GGUF (HF API,
# ?blobs=true) on 2026-08-29 as file_bytes * 8 / 8.03e9. The previous values
# claimed to include block overhead and did not: Q8_0 was 8.0 when the llama.cpp
# block is 34 bytes per 32 weights (exactly 8.5), and the _K_M variants promote
# token_embd/output to a wider type, which is why Q4_K_M measures 4.90 and not
# 4.5. Every entry was understated, so VRAM -- Gate 1 -- was too, by 6% at the
# common quants and 21% at Q2_K: the planner said a model fit a card it would
# OOM on. Values are Llama-architecture 8B; expect a few percent by architecture.
# Regenerate with scripts/build_quant_bpw.py.
QUANT_BPW: dict[str, float] = {
    "FP32": 32.0,
    "FP16": 16.0,
    "BF16": 16.0,
    "FP8": 8.0,  # exact: 1 byte/param, no block-scale overhead
    # W4A16 (AWQ / GPTQ): 4-bit weights plus per-group scales+zeros. At the usual
    # group size 128 that overhead is ~0.5 bpw, so ~4.5 effective -- the same
    # arithmetic as a 4-bit GGUF k-quant, arrived at independently.
    "AWQ": 4.5,
    "GPTQ": 4.5,
    "Q8_0": 8.5,  # exact: llama.cpp block is 2-byte scale + 32 int8 = 34B/32w
    "Q6_K": 6.57,  # measured 6.571
    "Q5_K_M": 5.71,  # measured 5.712
    "Q5_K_S": 5.58,  # measured 5.578
    "Q5_1": 6.0,
    "Q5_0": 5.5,
    "Q4_K_M": 4.9,  # measured 4.902
    "Q4_K_S": 4.68,  # measured 4.675
    "Q4_1": 5.0,
    "Q4_0": 4.5,
    "Q3_K_L": 4.31,  # measured 4.306
    "Q3_K_M": 4.0,  # measured 4.004
    "Q3_K_S": 3.65,  # measured 3.651
    "Q2_K": 3.17,  # measured 3.167
    "Q2_K_S": 2.3,
    "IQ4_NL": 4.66,  # measured 4.661
    "IQ4_XS": 4.43,  # measured 4.431
    "IQ3_S": 3.67,  # measured 3.669
    "IQ3_XXS": 3.26,  # measured 3.263
    "IQ2_M": 2.94,  # measured 2.937
    "IQ2_XXS": 2.39,  # measured 2.390
    "IQ1_S": 2.01,  # measured 2.012
}

# Supported serving backends
# SGLang added in 0.23.0: the 2026 serving market is vLLM / SGLang / Ollama, and a
# planner that cannot name SGLang is describing a market that has moved on. It
# carries NO measured rows in the corpus, so it predicts from first principles and
# says so -- cloning vLLM's coefficients would have been the easy lie.
BACKENDS = ["ollama", "vllm", "tgi", "sglang"]

# Which backends do continuous (in-flight) batching -- one GPU serves many
# sequences concurrently, amortizing weight reads. Ollama (llama.cpp) effectively
# serves one stream per slot, so it is modelled at batch=1 (replicas, not batch).
BACKEND_CONTINUOUS_BATCHING: dict[str, bool] = {
    "ollama": False,
    "vllm": True,
    "tgi": True,
    # SGLang batches continuously (RadixAttention prefix sharing on top).
    "sglang": True,
}

# Decode compute-utilisation ceiling for batched decode (when large batches turn
# the FC/MLP kernels compute-bound). Decode is mostly memory-bound, so this acts
# as a safety cap rarely reached on consumer GPUs.
DECODE_COMPUTE_MFU = 0.5

# Workload service-time variance (squared coefficient of variation, Cs^2) presets.
# Analytical queueing is conservative for low-variance traffic but under-estimates
# the tail for high-variance/agent workloads (heavy-tailed service: a few requests
# run 100x longer and hold a slot). Cs^2=0 is deterministic (reproduces M/D/1).
WORKLOAD_CV2: dict[str, float] = {
    "steady": 0.0,  # fixed-length, deterministic
    "chatbot": 1.0,  # variable output length (typical)
    "bursty": 4.0,  # mixed short/long
    "agent": 8.0,  # heavy-tailed (long tool calls / multi-turn)
}

# At/above this Cs^2 the analytical p95 is not trustworthy on its own -- warn and
# advise a real load test / simulation (the head-of-line-blocking regime).
HIGH_VARIANCE_CV2 = 4.0

# Roofline throughput estimate for off-registry models. Decode is memory-bound:
# each token streams all weights once, so tok/s ~= MBU * bandwidth / weight_bytes.
# MBU (memory-bandwidth utilisation) calibrated from the llama3.2-1b ollama FP16
# datapoint: 146.33 tok/s / (432 GB/s / 2.48 GB) = 0.84 (see models.ThroughputModel).
#
# This was 0.65 against a 556 GB/s reference bandwidth that the card does not have.
# The measured rate never changed -- only the denominator -- so the reference GPU's
# own roofline is identical either way (0.65*556 == 0.84*432). What moves is every
# OTHER GPU: the rig was achieving 84% of its real bandwidth, not 65%, so assuming
# equal MBU elsewhere predicts ~29% more throughput than the old figure did.
# The reference rig's memory bandwidth, in decimal GB/s. Kept here so the
# roofline's no-hardware fallbacks cannot drift from GPU_DB: four of them were
# left at a stale 556.0 when the reference card was corrected to 432, which
# combined with MBU_DEFAULT to imply 467 GB/s from a 432 GB/s card.
REFERENCE_BANDWIDTH_GBPS = 432.0

MBU_DEFAULT = 0.84

# Weights come out of `params_b * bpw / 8` in DECIMAL GB (a billion parameters is
# 1e9, not 2^30), while KV cache and GPU capacity are both binary GiB -- GDDR/HBM
# capacities are powers of two, so a "24 GB" card is 24 GiB. Summing the two and
# comparing against VRAM overstated weights by 7.37% and refused configs that fit.
#
# Only for capacity arithmetic. The roofline divides decimal GB/s of bandwidth by
# decimal GB of weights, which is already dimensionally consistent and must not be
# converted.
GB_TO_GIB = 1e9 / (1024**3)

# Default architecture used only when a model's real config cannot be resolved.
DEFAULT_ARCH: dict[str, int] = {"n_layers": 32, "n_kv_heads": 8, "d_head": 128}
DEFAULT_PARAMS_B = 3.0

# Fraction of VRAM a batched server can devote to KV-cache after weights +
# activations + framework overhead. PagedAttention packs KV at block granularity,
# so realised utilisation is high but not 1.0. Used to bound concurrent sequences.
KV_CACHE_UTILISATION = 0.9

# KV-cache element size in bytes for the default (FP16) cache.
KV_DTYPE_BYTES = 2

# KV-cache element size (bytes per K or V element) by cache dtype. Backends can
# quantize the KV cache independently of the weights -- llama.cpp `--cache-type-k`,
# vLLM fp8 KV -- roughly halving (q8) or quartering (q4) KV VRAM, which matters most
# at long context. Only the VRAM/concurrency effect is modelled; KV-quant's (small)
# quality impact is NOT screened here (no bundled measurements), so `plan --kv-quant`
# warns when it is enabled. fp16 stays tied to KV_DTYPE_BYTES.
KV_QUANT_BYTES: dict[str, float] = {"fp16": float(KV_DTYPE_BYTES), "q8": 1.0, "q4": 0.5}
DEFAULT_KV_QUANT = "fp16"

# Prefill is compute-bound: ~2 FLOPs per parameter per prompt token. MFU (model
# FLOPs utilisation) discounts peak TFLOPS to realised; 0.3-0.5 is typical for a
# single-stream forward pass. Calibratable later from measured TTFT.
FLOPS_PER_PARAM_PER_TOKEN = 2
PREFILL_MFU = 0.4

# Default prompt (input) length in tokens for TTFT estimation when unspecified.
DEFAULT_PROMPT_TOKENS = 512

# Energy modeling (0.8.0). Sustained LLM decode rarely holds 100% of board TDP;
# steady serving typically draws ~80-90%. Named so the assumption is explicit and
# tunable, not a magic number buried in the cost math.
POWER_UTILISATION = 0.85
# Default electricity price ($/kWh) -- roughly the US commercial average; override
# per run with `plan --electricity-rate`. Energy is reported as a SEPARATE line,
# not folded into the hardware cost or the budget gate, because a cloud `$/hr`
# rate already bundles power (double-count) while an amortised consumer card cost
# does not -- so the energy figure is most meaningful for self-hosted hardware.
DEFAULT_ELECTRICITY_RATE = 0.12
# Hours per month for cost/energy accrual (matches CostModel.predict_monthly's 24*30).
HOURS_PER_MONTH = 720

# Tensor parallelism (0.10.0). A model is sharded across `tp` GPUs: weights /tp,
# KV across heads. Decode gets ~tp x aggregate HBM bandwidth, minus Megatron
# all-reduce comms (2 per layer) whose cost scales with batch and shrinks with
# interconnect bandwidth (GPUSpec.interconnect_gbps) -- so TP erodes on slow PCIe
# or at high batch (Pope et al. 2022; Narayanan et al. 2021; vLLM docs).
ACT_DTYPE_BYTES = 2  # activations stay FP16 for the all-reduce, regardless of weight quant
# Realized fraction of peak interconnect bandwidth for ring all-reduce (NCCL rarely
# hits peak; PCIe contends with the host root complex). A calibration constant, not
# a datasheet figure -- the `measure` path can refine it. Literature gives no clean
# %-of-peak number, so this is deliberately conservative.
# The GPU's link to HOST DRAM, for CPU offload. PCIe 4.0 x16 is 31.5 GB/s per
# direction; weight streaming is unidirectional, so the aggregate figure does
# not apply. This is deliberately NOT GPUSpec.interconnect_gbps, which is the
# tensor-parallel GPU-to-GPU fabric -- using an H100's 900 GB/s NVLink as its
# path to system memory overstated offloaded decode by more than an order of
# magnitude, on the exact configs where offload is the only way to fit.
DEFAULT_HOST_LINK_GBPS = 32.0

INTERCONNECT_EFFICIENCY = 0.75
# GPUs inside one non-blocking NVLink domain (HGX baseboard). TP beyond this crosses
# a slower node boundary and collapses; Blackwell GB200 NVL72 extends it to 72.
NVLINK_DOMAIN_SIZE = 8
# TP degrees the planner searches in `auto` mode (powers of two up to the domain).
TP_SEARCH_DEGREES = [1, 2, 4, 8]

# Model registry: params in billions
MODEL_PARAMS_B: dict[str, float] = {
    "qwen2.5-0.5b": 0.49,
    "llama3.2-1b": 1.24,
    "qwen2.5-1.5b": 1.54,
    "phi-2": 2.78,
    "qwen2.5-3b": 3.09,
    "llama3.2-3b": 3.21,
    "llama3.1-8b": 8.03,
}

# Canonical architecture/family per registry model. Used to resolve arbitrary
# identifiers (Ollama tags, HF paths) to a registry model by family + params
# rather than exact name (see planner.identity).
MODEL_FAMILY: dict[str, str] = {
    "qwen2.5-0.5b": "qwen2.5",
    "llama3.2-1b": "llama3.2",
    "qwen2.5-1.5b": "qwen2.5",
    "phi-2": "phi",
    "qwen2.5-3b": "qwen2.5",
    "llama3.2-3b": "llama3.2",
    "llama3.1-8b": "llama3.1",
}

# Architecture metadata for KV-cache formula
MODEL_ARCH: dict[str, dict[str, int]] = {
    "qwen2.5-0.5b": {"n_layers": 24, "n_kv_heads": 2, "d_head": 64},
    "llama3.2-1b": {"n_layers": 16, "n_kv_heads": 8, "d_head": 64},
    "qwen2.5-1.5b": {"n_layers": 28, "n_kv_heads": 2, "d_head": 128},
    "phi-2": {"n_layers": 32, "n_kv_heads": 32, "d_head": 80},
    "qwen2.5-3b": {"n_layers": 36, "n_kv_heads": 2, "d_head": 128},
    "llama3.2-3b": {"n_layers": 28, "n_kv_heads": 8, "d_head": 128},
    "llama3.1-8b": {"n_layers": 32, "n_kv_heads": 8, "d_head": 128},
}

# Mixture-of-Experts (0.14.0). A SwiGLU expert is three matrices (gate, up, down),
# each hidden x moe_intermediate. Used to size the routed experts a token does NOT
# select, which is what separates an MoE model's active params from its total.
MOE_EXPERT_MATRICES = 3

# HF config.json key aliases for MoE geometry -- every family names these
# differently (Mixtral num_local_experts, DeepSeek n_routed_experts, Qwen
# num_experts), so resolution tries each in order.
MOE_NUM_EXPERTS_KEYS = ("num_local_experts", "n_routed_experts", "num_experts")
MOE_TOPK_KEYS = ("num_experts_per_tok", "moe_topk", "num_experts_per_token")
MOE_INTERMEDIATE_KEYS = ("moe_intermediate_size", "expert_intermediate_size", "intermediate_size")
MOE_DENSE_LAYER_KEYS = ("first_k_dense_replace",)

# Which weight formats each backend actually serves (0.15.0). Before this, the
# planner offered every GGUF level on every backend -- so it would recommend
# "vLLM + Q2_K", which vLLM does not serve in the normal path, and priced it using
# a speedup multiplier measured on llama.cpp. The bundled corpus only ever measured
# FP16 on vLLM/TGI, so those GGUF cells were extrapolation stacked on a mismatch.
# GGUF is llama.cpp's format (Ollama); vLLM/TGI serve float and FP8 checkpoints.
QUANT_FAMILY_FLOAT = "float"
QUANT_FAMILY_FP8 = "fp8"
QUANT_FAMILY_GGUF = "gguf"
QUANT_FAMILY_W4A16 = "w4a16"

FLOAT_QUANTS = frozenset({"FP32", "FP16", "BF16"})
# 4-bit weight / 16-bit activation checkpoints served by vLLM, SGLang and TGI.
W4A16_QUANTS = frozenset({"AWQ", "GPTQ"})

BACKEND_QUANT_FAMILIES: dict[str, frozenset[str]] = {
    "ollama": frozenset({QUANT_FAMILY_FLOAT, QUANT_FAMILY_GGUF}),
    "vllm": frozenset({QUANT_FAMILY_FLOAT, QUANT_FAMILY_FP8, QUANT_FAMILY_W4A16}),
    "tgi": frozenset({QUANT_FAMILY_FLOAT, QUANT_FAMILY_FP8, QUANT_FAMILY_W4A16}),
    # Same serving formats as vLLM: float checkpoints and FP8, not GGUF.
    "sglang": frozenset({QUANT_FAMILY_FLOAT, QUANT_FAMILY_FP8, QUANT_FAMILY_W4A16}),
}


def quant_family(quant: str) -> str:
    """Classify a quant into the serving format family a backend must support."""
    if quant == "FP8":
        return QUANT_FAMILY_FP8
    if quant in W4A16_QUANTS:
        return QUANT_FAMILY_W4A16
    if quant in FLOAT_QUANTS:
        return QUANT_FAMILY_FLOAT
    return QUANT_FAMILY_GGUF


def backend_supports_quant(backend: str, quant: str) -> bool:
    """True if ``backend`` can serve a checkpoint in ``quant``'s format.

    Unknown backends are permissive -- a caller registering a custom backend
    should not have every quant silently rejected.
    """
    families = BACKEND_QUANT_FAMILIES.get(backend)
    return True if families is None else quant_family(quant) in families


# Attention cache shape (0.18.0). MLA (DeepSeek-V2/V3) caches a compressed latent
# instead of per-head K/V; sliding-window attention caps local layers at a window.
MLA_LORA_RANK_KEYS = ("kv_lora_rank",)
MLA_ROPE_DIM_KEYS = ("qk_rope_head_dim",)
SWA_WINDOW_KEYS = ("sliding_window",)
# 1 full-attention layer every N. Gemma-3 spells this `sliding_window_pattern`.
SWA_PATTERN_KEYS = ("sliding_window_pattern", "global_attn_every_n_layers")

# One billing month, in seconds. Shared by the cost model and the API break-even
# so a "month" means the same thing in both (30 days, matching predict_monthly).
SECONDS_PER_MONTH = 60 * 60 * 24 * 30

# -- Multi-LoRA serving (0.27.0) ---------------------------------------
#
# Which linear modules an adapter targets. The planner sizes only what it can
# derive exactly: q/k/v/o dimensions all follow from hidden_size, n_kv_heads and
# d_head, which every resolved ModelSpec carries. MLP targets need the dense
# intermediate_size, which the resolver does not always have, so "all" is not
# offered rather than guessed -- an under-sized adapter claims a fit that is not
# there.
LORA_TARGETS: dict[str, tuple[str, ...]] = {
    "qv": ("q", "v"),  # the PEFT default
    "attn": ("q", "k", "v", "o"),
}
DEFAULT_LORA_TARGET = "qv"
# Adapters are served in fp16 regardless of base-model quantization: the low-rank
# update is applied in the compute dtype, and quantizing a rank-16 matrix saves
# megabytes while costing accuracy nobody has measured.
LORA_BYTES_PER_PARAM = 2.0
# LoRA factorises a (d_in x d_out) weight into A (d_in x r) and B (r x d_out), so
# one target module costs r * (d_in + d_out) parameters.
LORA_MATRICES_PER_MODULE = 2

# Rank-indexed throughput cost, from the only public multi-LoRA sweep with per-rank
# numbers: SqueezeBits, vLLM 0.6.3 on A100 80GB PCIe, Llama-3.1-8B-Instruct, 1K in /
# 1K out (https://blog.squeezebits.com/37065). Two endpoints are published --
# 23.9% degradation at the low rank and 47.0% at the high -- and NOT the two
# intermediate points, so anything between these is interpolated, never measured.
# Kept as endpoints rather than a fitted curve so the interpolation stays visible.
LORA_RANK_THROUGHPUT: dict[int, float] = {8: 0.761, 64: 0.530}
LORA_SOURCE = "SqueezeBits vLLM 0.6.3 / A100 80GB / Llama-3.1-8B (blog.squeezebits.com/37065)"
# Same source: throughput was near-flat from 2 to 64 concurrent adapters (~10%
# spread), so adapter COUNT drives VRAM here and not the decode rate. The residual
# ~10% is unmodelled and warned about rather than fitted to two digits.
LORA_COUNT_UNMODELLED_SPREAD = 0.10
# vLLM's own ceiling on simultaneously-loaded adapters per batch.
MAX_LORA_ADAPTERS = 64
MAX_LORA_RANK = 64
