"""Resolve arbitrary model identifiers to the planner's registry models.

Maps by (architecture/family, parameter size) rather than exact name, so an
Ollama tag (``llama3.2:1b-instruct-q8_0``), an HF path, or a registry name all
resolve to the same registry model -- letting the safety screen compare a live
backend tag against the bundled TR134/TR142 data.

Matching uses family + nearest parameter count. ``variant`` (instruct/base) is
parsed for transparency ("model type") but is not yet a matching axis -- the
bundled safety data is all instruction-tuned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from chimeraforge.planner.constants import MODEL_FAMILY, MODEL_PARAMS_B, QUANT_BPW

# Family generations recognised in identifiers. Derived from the registry so the
# two can't drift, plus extras we can parse even without registry coverage.
# Ordered longest-first so a specific generation ("llama3.2") is matched before a
# prefix of it ("llama3.1" / "llama3").
_EXTRA_FAMILIES = ("mistral", "gemma2", "gemma", "phi")
_FAMILIES = tuple(sorted(set(MODEL_FAMILY.values()) | set(_EXTRA_FAMILIES), key=len, reverse=True))

_PARAMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b\b", re.IGNORECASE)
# Match GGUF quant tags: K-quants (q4_K_M), legacy (q4_0/q5_1), i-quants (iq4_xs),
# and float types (fp16/f16/bf16/f32).
_QUANT_RE = re.compile(r"\b(iq\d[a-z0-9_]*|q\d_?[a-z0-9_]*|bf16|fp16|f16|f32)\b", re.IGNORECASE)
_VARIANT_RE = re.compile(r"\b(instruct|chat|base|it)\b", re.IGNORECASE)

# Accept the nearest same-family registry model within this fraction of params.
_PARAMS_TOLERANCE = 0.5


@dataclass(frozen=True)
class ModelIdentity:
    """Parsed identity: architecture/family, model type (variant), params, quant."""

    family: str | None
    variant: str | None  # instruct | base | chat | None
    params_b: float | None
    quant: str | None


def _norm(s: str) -> str:
    return re.sub(r"[-_.: ]", "", s.lower())


def parse_family(identifier: str) -> str | None:
    """Return the canonical family generation present in *identifier*, or None."""
    norm = _norm(identifier)
    for fam in _FAMILIES:
        if _norm(fam) in norm:
            return fam
    return None


def parse_params_b(identifier: str) -> float | None:
    """Extract a parameter count in billions (e.g. ``1b``, ``1.5b``)."""
    m = _PARAMS_RE.search(identifier)
    return float(m.group(1)) if m else None


def parse_quant(identifier: str) -> str | None:
    """Extract and normalise a quant tag (e.g. ``q4_K_M`` -> ``Q4_K_M``).

    Recognises any quant in ``QUANT_BPW`` (K-quants, legacy, i-quants, floats);
    returns None for unknown tags so callers fall back to the search ladder.
    """
    m = _QUANT_RE.search(identifier)
    if not m:
        return None
    q = m.group(1).upper()
    if q == "F16":
        q = "FP16"
    elif q == "F32":
        q = "FP32"
    return q if q in QUANT_BPW else None


def parse_variant(identifier: str) -> str | None:
    """Extract the model type (instruct/base/chat), normalising ``it`` -> instruct."""
    m = _VARIANT_RE.search(identifier)
    if not m:
        return None
    v = m.group(1).lower()
    return "instruct" if v == "it" else v


def parse_identity(identifier: str, quant_override: str | None = None) -> ModelIdentity:
    """Parse *identifier* into a ModelIdentity (an explicit quant overrides the tag)."""
    return ModelIdentity(
        family=parse_family(identifier),
        variant=parse_variant(identifier),
        params_b=parse_params_b(identifier),
        quant=(quant_override or parse_quant(identifier)),
    )


def resolve_model(identifier: str) -> str | None:
    """Return the registry model name matching *identifier*, or None.

    An exact registry name passes through. Otherwise match by family + nearest
    parameter count (within ``_PARAMS_TOLERANCE``); a family with a single
    registry model resolves regardless of the parsed size.
    """
    if identifier in MODEL_PARAMS_B:
        return identifier
    fam = parse_family(identifier)
    if fam is None:
        return None
    candidates = [m for m, f in MODEL_FAMILY.items() if f == fam]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    params = parse_params_b(identifier)
    if params is None or params <= 0:  # e.g. a degenerate "...0b" token -> no division
        return None
    best = min(candidates, key=lambda m: abs(MODEL_PARAMS_B[m] - params))
    return best if abs(MODEL_PARAMS_B[best] - params) / params <= _PARAMS_TOLERANCE else None
