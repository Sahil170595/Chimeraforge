"""Hybrid and linear-attention models: which layers cache KV, and what else they hold.

A transformer's layers are not all the same kind of layer any more. A 2026 hybrid
interleaves full-attention layers with Mamba/linear-attention ones, and the two
have opposite memory behaviour:

* an **attention** layer caches K and V per token, so its cost grows with context;
* a **recurrent** layer holds a fixed-size state per *sequence*, independent of
  context, and caches nothing per token.

Sizing every layer as attention overstates KV by the ratio of total layers to
attention layers -- 14.0x on Nemotron Nano 2, which is not a rounding error --
while ignoring the recurrent state understates a term that reaches gigabytes at
batch 64. This module supplies both corrections, and the rule governing it is
asymmetric on purpose:

    **KV may only shrink on evidence of a named, placed non-attention layer.**

Under-sizing KV is what turns "it fits" into an OOM, so a family whose pattern
cannot be placed keeps every layer as full attention -- the same conservative
guard `attention_from_config` already applies to an unplaceable sliding window.
Falcon-H1 is the case that rule exists for: it is a *parallel* hybrid, every
layer building both a Mamba mixer and a full attention block, so it pays full KV
on all 72 layers plus the SSM state. Its config declares no layer pattern at all,
and treating "it has mamba keys" as evidence of interleaving would under-size it.

State shapes are read from transformers 5.10.1 source, not from recall:

* **Mamba-2** (`models/mamba2/modeling_mamba2.py`): the conv input width is
  ``intermediate_size + 2 * n_groups * ssm_state_size`` (line 410's `d_mlp`
  arithmetic) over ``conv_kernel`` taps, and the SSM state is
  ``num_heads x head_dim x ssm_state_size`` (line 460's `A` expand).
* **Mamba-1** (`models/jamba/modeling_jamba.py`): the conv is depthwise over
  ``intermediate_size`` channels with ``mamba_d_conv`` taps, and ``A`` is
  ``(intermediate_size, ssm_state_size)``.
* **Gated DeltaNet** (`models/qwen3_next/modeling_qwen3_next.py`): conv over
  ``key_dim * 2 + value_dim``, recurrent state
  ``num_v_heads x head_k_dim x head_v_dim`` (line 427).

Kimi's KDA is the deliberate exception: it is not in transformers, its allocation
happens inside an external library, and its shape here is inferred from the
DeltaNet convention. That state term is labelled `estimated` and warns. The
attention-layer correction -- the larger effect by far -- stays `derived` for it,
because `full_attn_layers` is an explicit, placed list.
"""

from __future__ import annotations

import math
from typing import Any

# transformers' canonical vocabulary. Families spell their own patterns half a
# dozen ways; everything is normalized to these so one classifier serves all.
LAYER_FULL_ATTENTION = "full_attention"
LAYER_SLIDING_ATTENTION = "sliding_attention"
LAYER_LINEAR_ATTENTION = "linear_attention"
LAYER_MLP = "mlp"
# A layer that caches K/V per token. Sliding attention still caches -- just less
# of it, which `kv_cache_gb`'s window arithmetic already handles.
ATTENTION_LAYERS = (LAYER_FULL_ATTENTION, LAYER_SLIDING_ATTENTION)

# How each family spells "this layer is attention" inside `layer_types`.
_ATTENTION_TOKENS = ("full_attention", "sliding_attention", "attention")
_RECURRENT_TOKENS = ("mamba", "linear_attention", "recurrent", "swa_linear")

# Recurrent-state kinds, and whether their geometry is readable in library source.
KIND_MAMBA2 = "mamba2"
KIND_MAMBA1 = "mamba1"
KIND_GATED_DELTANET = "gated-deltanet"
KIND_KDA = "kimi-delta-attention"
# Only KDA is inferred; the rest are read out of transformers.
INFERRED_KINDS = (KIND_KDA,)

# Bytes per element for the dtype a config declares for its SSM state. Several
# configs declare float32 here while the model itself is bfloat16, and assuming
# bf16 would halve the term that dominates.
_DTYPE_BYTES = {
    "float32": 4.0,
    "fp32": 4.0,
    "float16": 2.0,
    "fp16": 2.0,
    "bfloat16": 2.0,
    "bf16": 2.0,
    "float64": 8.0,
    "float8_e4m3fn": 1.0,
}
DEFAULT_STATE_DTYPE_BYTES = 2.0

SSM_DTYPE_KEYS = ("mamba_ssm_dtype", "mamba_ssm_cache_dtype", "mamba_cache_dtype")
MODEL_DTYPE_KEYS = ("dtype", "torch_dtype")


def unwrap_text_config(config: dict) -> dict:
    """The sub-config that actually carries the language-model architecture.

    Multimodal wrappers (Qwen3.5, Gemma 4) nest every architecture key under
    ``text_config`` and leave the top level with little more than `model_type`.
    The resolver read the top level and raised `ResolverError`, which made two
    entire model lines unplannable -- a coverage hole, not a wrong number.

    Returns ``config`` itself when there is no wrapper, so a flat config is
    untouched.
    """
    inner = config.get("text_config")
    if isinstance(inner, dict) and inner.get("num_hidden_layers"):
        # Keep anything the wrapper declared that the inner config does not, so a
        # key hoisted to the top level is not lost on the way down.
        merged = dict(config)
        merged.pop("text_config", None)
        merged.update(inner)
        return merged
    return config


def _dtype_bytes(name: Any) -> float | None:
    if not isinstance(name, str):
        return None
    return _DTYPE_BYTES.get(name.strip().lower())


def state_dtype_bytes(config: dict) -> tuple[float, bool]:
    """Bytes per recurrent-state element, and whether the config actually said.

    Reads the SSM-specific dtype first: `Qwen3.5-9B` declares
    ``mamba_ssm_dtype: float32`` while the model is bfloat16, and taking the model
    dtype there would halve the dominant term. Falls back to the model dtype, and
    reports which happened so the caller can say so rather than implying the
    config was explicit.
    """
    for key in SSM_DTYPE_KEYS:
        nbytes = _dtype_bytes(config.get(key))
        if nbytes:
            return nbytes, True
    for key in MODEL_DTYPE_KEYS:
        nbytes = _dtype_bytes(config.get(key))
        if nbytes:
            return nbytes, False
    return DEFAULT_STATE_DTYPE_BYTES, False


def normalize_layer_types(config: dict, n_layers: int) -> list[str] | None:
    """Per-layer kinds in transformers' vocabulary, or ``None`` if unplaceable.

    ``None`` is the honest answer for a config that declares no pattern, and the
    caller must then treat every layer as full attention. It is NOT the same as
    "this model is dense" -- Falcon-H1 lands here and is a real hybrid; it simply
    is not an *interleaved* one, and nothing in its config says otherwise.

    Six spellings are recognised, all verified against live configs fetched from
    the Hugging Face repos named in each branch.
    """
    if not n_layers or n_layers <= 0:
        return None

    # 1. transformers' own key, already canonical -- but families disagree on the
    #    tokens inside it (`granitemoehybrid` writes "mamba"/"attention" where
    #    `qwen3_5` writes "linear_attention"/"full_attention").
    declared = config.get("layer_types")
    if isinstance(declared, list) and len(declared) == n_layers:
        out = [_canonical_layer(str(x)) for x in declared]
        if any(x in ATTENTION_LAYERS for x in out):
            return out
        return None

    # 2. Nemotron-H: a string, one character per layer. M=mamba, *=attention, -=MLP.
    pattern = config.get("hybrid_override_pattern")
    if isinstance(pattern, str) and len(pattern) == n_layers:
        mapping = {"*": LAYER_FULL_ATTENTION, "M": LAYER_LINEAR_ATTENTION, "-": LAYER_MLP}
        out = [mapping.get(ch) for ch in pattern]
        if all(out) and LAYER_FULL_ATTENTION in out:
            return [x for x in out if x]
        return None

    # 3. MiniMax: 1 = full (softmax) attention, 0 = lightning/linear attention.
    attn_types = config.get("attn_type_list")
    if isinstance(attn_types, list) and len(attn_types) == n_layers:
        out = [LAYER_FULL_ATTENTION if int(x) == 1 else LAYER_LINEAR_ATTENTION for x in attn_types]
        if LAYER_FULL_ATTENTION in out:
            return out
        return None

    # 4. Kimi: an explicit 1-indexed list of the full-attention layers.
    linear_cfg = config.get("linear_attn_config")
    if isinstance(linear_cfg, dict):
        full = linear_cfg.get("full_attn_layers")
        if isinstance(full, list) and full:
            full_set = {int(x) for x in full}
            # 1-indexed in the published config: the list ends at n_layers, not
            # n_layers - 1. Treating it as 0-indexed would misplace every layer.
            return [
                LAYER_FULL_ATTENTION if (i + 1) in full_set else LAYER_LINEAR_ATTENTION
                for i in range(n_layers)
            ]

    # 5. Qwen3-Next / Qwen3.5: every Nth layer is full attention.
    interval = config.get("full_attention_interval")
    if isinstance(interval, int) and interval > 1:
        return [
            LAYER_FULL_ATTENTION if (i + 1) % interval == 0 else LAYER_LINEAR_ATTENTION
            for i in range(n_layers)
        ]

    # 6. Jamba: attention at every `period` layers, offset into the block.
    period = config.get("attn_layer_period")
    offset = config.get("attn_layer_offset")
    if isinstance(period, int) and period > 0 and isinstance(offset, int):
        return [
            LAYER_FULL_ATTENTION if i % period == offset else LAYER_LINEAR_ATTENTION
            for i in range(n_layers)
        ]

    return None


def _canonical_layer(token: str) -> str:
    low = token.strip().lower()
    if "sliding" in low:
        return LAYER_SLIDING_ATTENTION
    if any(t in low for t in _RECURRENT_TOKENS):
        return LAYER_LINEAR_ATTENTION
    if any(t in low for t in _ATTENTION_TOKENS):
        return LAYER_FULL_ATTENTION
    if "mlp" in low or "moe" in low:
        return LAYER_MLP
    # Unrecognised token: call it attention. Guessing "recurrent" here would
    # shrink the cache on a layer nobody has identified.
    return LAYER_FULL_ATTENTION


def count_attention_layers(config: dict, n_layers: int) -> int:
    """Layers that cache K/V per token. Equals ``n_layers`` when unplaceable."""
    types = normalize_layer_types(config, n_layers)
    if types is None:
        return n_layers
    return sum(1 for t in types if t in ATTENTION_LAYERS)


def count_recurrent_layers(config: dict, n_layers: int) -> int:
    """Layers that hold a recurrent state -- NOT simply "everything else".

    Nemotron-H's pattern is three-way: 4 attention, 28 Mamba and 24 plain MLP
    layers. Taking ``n_layers - attention_layers`` counts the MLP layers as
    recurrent and inflates the state by 86%, which is the same over-claiming
    this module exists to remove, pointed the other way.
    """
    types = normalize_layer_types(config, n_layers)
    if types is None:
        return 0
    return sum(1 for t in types if t == LAYER_LINEAR_ATTENTION)


def recurrent_state_elems(config: dict) -> tuple[float, str] | None:
    """Elements of recurrent state one layer holds per sequence, and its kind.

    ``None`` when no recognised recurrent geometry is declared. The value is
    independent of context length -- that is the whole point of a recurrent layer
    -- and is per *sequence*, so it belongs in the concurrency ceiling as well as
    in the footprint. At 20-75 MiB it looks negligible at batch 1 and reaches
    gigabytes at batch 64, which is exactly where a model gets chosen for
    throughput.
    """
    for reader in (_mamba2_elems, _gated_deltanet_elems, _kda_elems, _mamba1_elems):
        got = reader(config)
        if got:
            return got
    return None


def _mamba2_elems(config: dict) -> tuple[float, str] | None:
    """Mamba-2: conv over (d_inner + 2*n_groups*d_state), state per head."""
    n_heads = _first(config, ("mamba_num_heads", "mamba_n_heads"))
    head_dim = _first(config, ("mamba_head_dim", "mamba_d_head"))
    d_state = _first(config, ("ssm_state_size", "mamba_d_state", "mamba_state_dim"))
    n_groups = _first(config, ("n_groups", "mamba_num_groups", "mamba_n_groups"))
    conv_kernel = _first(config, ("conv_kernel", "mamba_d_conv"))
    if not (n_heads and head_dim and d_state and conv_kernel):
        return None
    # d_inner is stated outright by Falcon-H1 (`mamba_d_ssm`) and otherwise is the
    # head geometry multiplied out, which equals hidden * expand where both agree.
    d_inner = config.get("mamba_d_ssm") or n_heads * head_dim
    conv_state = (d_inner + 2 * (n_groups or 1) * d_state) * conv_kernel
    ssm_state = n_heads * head_dim * d_state
    return float(conv_state + ssm_state), KIND_MAMBA2


def _mamba1_elems(config: dict) -> tuple[float, str] | None:
    """Mamba-1 (Jamba): depthwise conv and A both over ``intermediate_size``."""
    expand = config.get("mamba_expand")
    hidden = config.get("hidden_size")
    d_state = config.get("mamba_d_state")
    conv_kernel = config.get("mamba_d_conv")
    if not (expand and hidden and d_state and conv_kernel):
        return None
    d_inner = expand * hidden
    return float(d_inner * conv_kernel + d_inner * d_state), KIND_MAMBA1


def _gated_deltanet_elems(config: dict) -> tuple[float, str] | None:
    """Qwen3-Next / Qwen3.5 gated DeltaNet."""
    num_v = config.get("linear_num_value_heads")
    num_k = config.get("linear_num_key_heads")
    k_dim = config.get("linear_key_head_dim")
    v_dim = config.get("linear_value_head_dim")
    conv_kernel = config.get("linear_conv_kernel_dim")
    if not (num_v and num_k and k_dim and v_dim and conv_kernel):
        return None
    conv_state = (k_dim * num_k * 2 + v_dim * num_v) * conv_kernel
    recurrent = num_v * k_dim * v_dim
    return float(conv_state + recurrent), KIND_GATED_DELTANET


def _kda_elems(config: dict) -> tuple[float, str] | None:
    """Kimi Delta Attention -- shape INFERRED from the DeltaNet convention.

    The dims are readable from `linear_attn_config`, but the allocation happens
    inside an external library rather than transformers, so this is the one state
    term that is not `derived`. It is labelled and warned about rather than
    presented alongside the read-from-source ones.
    """
    cfg = config.get("linear_attn_config")
    if not isinstance(cfg, dict):
        return None
    head_dim = cfg.get("head_dim")
    n_heads = cfg.get("num_heads") or config.get("num_attention_heads")
    conv_kernel = cfg.get("short_conv_kernel_size") or cfg.get("conv_kernel_size") or 4
    if not (head_dim and n_heads):
        return None
    return float(n_heads * head_dim * head_dim + n_heads * head_dim * conv_kernel), KIND_KDA


def _first(config: dict, keys: tuple[str, ...]) -> Any:
    for k in keys:
        v = config.get(k)
        if v:
            return v
    return None


def hybrid_from_config(config: dict, n_layers: int) -> dict:
    """Layer split and recurrent-state size, ready to hang off a ``ModelSpec``.

    Returns ``{}`` for a model with no recognised recurrent geometry AND no
    placeable pattern, so a dense model's numbers are untouched.
    """
    out: dict = {}
    attention_layers = count_attention_layers(config, n_layers)
    state = recurrent_state_elems(config)
    recurrent_layers = count_recurrent_layers(config, n_layers)

    if attention_layers != n_layers:
        out["n_attention_layers"] = attention_layers

    if state and recurrent_layers > 0:
        elems, kind = state
        nbytes, dtype_declared = state_dtype_bytes(config)
        out["recurrent_state_bytes_per_seq"] = elems * nbytes * recurrent_layers
        out["recurrent_kind"] = kind
        out["recurrent_state_dtype_declared"] = dtype_declared
    elif state and recurrent_layers == 0 and _has_mamba_keys(config):
        # Falcon-H1: every layer is BOTH, so full KV on all of them plus the state
        # on all of them. The pattern is unplaceable, but the geometry is not, and
        # dropping the state here would understate a real allocation.
        elems, kind = state
        nbytes, dtype_declared = state_dtype_bytes(config)
        out["recurrent_state_bytes_per_seq"] = elems * nbytes * n_layers
        out["recurrent_kind"] = kind
        out["recurrent_state_dtype_declared"] = dtype_declared
        out["parallel_hybrid"] = True
    return out


def _has_mamba_keys(config: dict) -> bool:
    return any(k.startswith("mamba_") or k == "ssm_state_size" for k in config)


def recurrent_state_gb(bytes_per_seq: float, batch_size: int) -> float:
    """Recurrent state for ``batch_size`` sequences, in GiB.

    Per sequence, not per model: this is the trap the term exists to close. It is
    flat in context length, so it never shows up in a long-context sanity check
    and only bites at high concurrency.
    """
    return bytes_per_seq * max(batch_size, 0) / (1024**3)


def max_seqs_for_state(free_bytes: float, per_seq_bytes: float) -> int:
    """Sequence ceiling imposed by the recurrent state alone."""
    if per_seq_bytes <= 0:
        return math.inf  # type: ignore[return-value]
    return int(free_bytes // per_seq_bytes)
