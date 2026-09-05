"""Resolve any model identifier to a concrete ModelSpec (params + architecture).

Turns an arbitrary identifier -- a registry name (``llama3.2-3b``), an Ollama tag
(``llama3.2:3b`` / ``ollama:qwen2.5:7b``), or a Hugging Face repo
(``Qwen/Qwen2.5-1.5B-Instruct``) -- into a ``ModelSpec`` carrying the parameter
count and attention geometry the planner's VRAM/throughput models need.

Metadata sources, in priority order:

1. ``overrides`` -- explicit ``--params-b/--n-layers/...`` flags (air-gapped path).
2. Bundled registry (``MODEL_PARAMS_B`` / ``MODEL_ARCH``) -- offline, exact.
3. Local spec cache (``~/.cache/chimeraforge/specs``) -- previously resolved.
4. Ollama ``POST /api/show`` -- GGUF metadata for a pulled tag.
5. Hugging Face ``config.json`` + ``model_info`` -- for anything on the Hub.
6. Family/size approximation against the registry (last resort).

Parsing (dict -> ModelSpec) is separated from fetching (network -> dict) so the
parsers are unit-testable against captured JSON without touching the network.
Network failures raise ``ResolverError`` -- never a silent fallback.
"""

from __future__ import annotations

import datetime as _dt

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from chimeraforge.planner.constants import (
    DEFAULT_ARCH,
    DEFAULT_LORA_TARGET,
    LORA_BYTES_PER_PARAM,
    LORA_TARGETS,
    MLA_LORA_RANK_KEYS,
    MLA_ROPE_DIM_KEYS,
    MODEL_ARCH,
    MODEL_FAMILY,
    MODEL_PARAMS_B,
    MOE_DENSE_LAYER_KEYS,
    MOE_EXPERT_MATRICES,
    MOE_INTERMEDIATE_KEYS,
    MOE_NUM_EXPERTS_KEYS,
    MOE_TOPK_KEYS,
    QUANT_BPW,
    SWA_PATTERN_KEYS,
    SWA_WINDOW_KEYS,
)
from chimeraforge.planner.hybrid import hybrid_from_config, unwrap_text_config
from chimeraforge.planner.identity import parse_identity, parse_quant, resolve_model

log = logging.getLogger("chimeraforge.planner.resolver")

# Provenance tags for a resolved spec.
SOURCE_REGISTRY = "registry"
SOURCE_REGISTRY_APPROX = "registry-approx"
SOURCE_OLLAMA = "ollama"
SOURCE_HF = "hf"
SOURCE_MANUAL = "manual"
SOURCE_CACHE = "cache"

DEFAULT_OLLAMA_URL = "http://localhost:11434"
_HF_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
_PARAM_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([bm])", re.IGNORECASE)
_NETWORK_TIMEOUT_S = 15.0


class ResolverError(RuntimeError):
    """Raised when a model identifier cannot be resolved to a ModelSpec."""


@dataclass(frozen=True)
class ModelSpec:
    """Concrete model facts needed by the planner's predictive models.

    Attributes:
        name: Canonical identifier (registry name, Ollama tag, or HF repo).
        params_b: Parameter count in billions (true count, incl. embeddings).
        n_layers: Transformer block count.
        n_kv_heads: Key/value heads (GQA); equals attention heads for MHA.
        d_head: Per-head dimension.
        hidden_size: Model hidden dimension, when known.
        vocab_size: Vocabulary size, when known.
        native_quant: The model's own quant (e.g. an Ollama tag's ``Q4_K_M``).
        family: Architecture family (``llama3.2``, ``qwen2.5``, ...), when known.
        variant: ``instruct`` / ``base`` / ``chat``, when known.
        source: Provenance tag (one of the ``SOURCE_*`` constants).
        registry_alias: Registry model this spec maps to exactly, if any. Set for
            registry hits and offline family/size approximations so the planner
            can reuse that model's *measured* throughput/quality/safety data
            instead of a roofline estimate. ``None`` for genuinely off-registry
            models (Ollama/HF/manual), which fall back to first-principles.
        num_experts: Routed experts per MoE layer (Mixtral 8, DeepSeek-V3 256).
        experts_per_token: Routed experts each token is dispatched to (top-k).
        moe_intermediate_size: Per-expert FFN width. Needed to size an expert.
        n_dense_layers: Leading layers that are dense, not MoE (DeepSeek's
            ``first_k_dense_replace``); the rest carry routed experts.
    """

    name: str
    params_b: float
    n_layers: int
    n_kv_heads: int
    d_head: int
    hidden_size: int | None = None
    vocab_size: int | None = None
    native_quant: str | None = None
    family: str | None = None
    variant: str | None = None
    source: str = SOURCE_MANUAL
    registry_alias: str | None = None
    # Mixture-of-Experts geometry (0.14.0). All None/0 for a dense model.
    num_experts: int | None = None
    experts_per_token: int | None = None
    moe_intermediate_size: int | None = None
    n_dense_layers: int = 0
    # Attention cache shape (0.18.0). Standard MHA/GQA caches 2 (K+V) * n_kv_heads *
    # d_head per token per layer; these two families do not.
    kv_lora_rank: int | None = None  # MLA: width of the compressed KV latent
    qk_rope_head_dim: int | None = None  # MLA: decoupled RoPE key cached alongside it
    sliding_window: int | None = None  # SWA: attention window, when layers are local
    swa_global_every: int = 0  # SWA: 1 full-attention layer every N (0 = unknown)
    # Hybrid / linear-attention geometry (P8.2). A hybrid's layers are not all the
    # same kind of layer: only some cache K/V per token, and the rest hold a
    # fixed-size recurrent state per SEQUENCE that no per-token cache models.
    # `None` for n_attention_layers means "every layer caches" -- the conservative
    # default, and the only honest one when a pattern cannot be placed.
    n_attention_layers: int | None = None
    recurrent_state_bytes_per_seq: float = 0.0
    recurrent_kind: str | None = None
    recurrent_state_dtype_declared: bool = False
    parallel_hybrid: bool = False

    @property
    def is_moe(self) -> bool:
        """True when the model routes tokens to a subset of per-layer experts."""
        return bool(
            self.num_experts
            and self.experts_per_token
            and self.num_experts > self.experts_per_token
        )

    @property
    def active_params_b(self) -> float:
        """Parameters actually read per decoded token, in billions.

        A dense model reads every weight per token, so active == total. An MoE
        layer reads only the ``experts_per_token`` routed experts it dispatched
        to, so the weights of the *unselected* routed experts are never touched:

            active = total - n_moe_layers * (num_experts - experts_per_token)
                             * MOE_EXPERT_MATRICES * hidden * moe_intermediate

        Subtracting the unselected experts (rather than summing what *is* active)
        avoids having to model attention, embeddings, shared experts, and norms
        at all -- everything outside that subtraction is read every token either
        way. Verified against published active counts: Mixtral-8x7B 12.9B (exact),
        DeepSeek-V3 37.5B vs 37B, Qwen3-30B-A3B 3.32B vs 3.3B.

        Falls back to ``params_b`` whenever the geometry is incomplete -- an
        under-informed guess here would silently *inflate* predicted throughput,
        so the conservative dense answer is the honest one.
        """
        if not self.is_moe or not self.hidden_size or not self.moe_intermediate_size:
            return self.params_b
        n_moe_layers = max(self.n_layers - max(self.n_dense_layers, 0), 0)
        if n_moe_layers <= 0:
            return self.params_b
        unselected = self.num_experts - self.experts_per_token
        inactive_b = (
            n_moe_layers
            * unselected
            * MOE_EXPERT_MATRICES
            * self.hidden_size
            * self.moe_intermediate_size
        ) / 1e9
        # Never return a nonsensical (<=0) or larger-than-total active count.
        return round(min(max(self.params_b - inactive_b, 0.0) or self.params_b, self.params_b), 4)

    @property
    def is_mla(self) -> bool:
        """Multi-head Latent Attention (DeepSeek-V2/V3): KV cached as one latent."""
        return bool(self.kv_lora_rank and self.qk_rope_head_dim)

    def lora_params_per_adapter(self, rank: int, target: str = DEFAULT_LORA_TARGET) -> int:
        """Trainable parameters in one LoRA adapter, exactly.

        LoRA factorises each target weight (d_in x d_out) into A (d_in x r) and
        B (r x d_out), so a module costs ``r * (d_in + d_out)`` and the adapter is
        that summed over targets and layers. This is arithmetic, not a fit: for
        Llama-2-7B q/v it reproduces the published ``524288 * r``.

        Falls back to ``hidden = n_kv_heads * d_head`` only when hidden_size is
        absent, which is the GQA-collapsed case and understates a real GQA model --
        so callers treat a spec without hidden_size as unsized rather than trusting
        the number.
        """
        modules = LORA_TARGETS.get(target)
        if not modules or rank <= 0:
            return 0
        hidden = self.hidden_size or (self.n_kv_heads * self.d_head)
        kv_dim = self.n_kv_heads * self.d_head
        # q and o are hidden->hidden; k and v project down to the (grouped) KV width.
        widths = {
            "q": (hidden, hidden),
            "o": (hidden, hidden),
            "k": (hidden, kv_dim),
            "v": (hidden, kv_dim),
        }
        per_layer = sum(rank * (widths[m][0] + widths[m][1]) for m in modules)
        return per_layer * self.n_layers

    def lora_gb_per_adapter(self, rank: int, target: str = DEFAULT_LORA_TARGET) -> float:
        """VRAM one resident adapter occupies, in GB (fp16 weights)."""
        return self.lora_params_per_adapter(rank, target) * LORA_BYTES_PER_PARAM / 1e9

    @property
    def kv_elems_per_token_per_layer(self) -> int:
        """Cache elements held per token, per layer.

        MHA/GQA cache K and V separately for every KV head, so
        ``2 * n_kv_heads * d_head``. MLA instead caches a single compressed latent
        plus a decoupled RoPE key -- ``kv_lora_rank + qk_rope_head_dim`` -- which
        is dramatically smaller and is the whole point of the design (DeepSeek-V3:
        576 vs 32,768 elements, a 57x difference).
        """
        if self.is_mla:
            return self.kv_lora_rank + self.qk_rope_head_dim
        return 2 * self.n_kv_heads * self.d_head

    @property
    def attention_layers(self) -> int:
        """Layers that actually cache K/V. Falls back to every layer.

        The fallback is the whole safety property: a model whose layer pattern
        could not be placed is sized as if every layer were attention, because
        under-sizing KV is what turns "it fits" into an OOM.
        """
        if self.n_attention_layers and 0 < self.n_attention_layers <= self.n_layers:
            return self.n_attention_layers
        return self.n_layers

    def arch(self) -> dict[str, int]:
        """Return the arch dict consumed by ``VRAMModel.predict``."""
        arch: dict[str, int] = {
            "n_layers": self.n_layers,
            "n_kv_heads": self.n_kv_heads,
            "d_head": self.d_head,
            "kv_elems_per_token_per_layer": self.kv_elems_per_token_per_layer,
        }
        # Emitted only when it actually differs, so a dense model's arch dict --
        # and therefore every number downstream of it -- is byte-identical.
        if self.attention_layers != self.n_layers:
            arch["n_attention_layers"] = self.attention_layers
        if self.recurrent_state_bytes_per_seq > 0:
            arch["recurrent_state_bytes_per_seq"] = self.recurrent_state_bytes_per_seq
        # Only advertise a window when the interleave pattern is known too. Applying
        # a window we cannot place would SHRINK the predicted cache, and an
        # under-estimate is the direction that says "it fits" when it does not.
        if self.sliding_window and self.swa_global_every:
            arch["swa_window"] = self.sliding_window
            arch["swa_global_every"] = self.swa_global_every
        return arch

    def weight_gb(self, quant: str) -> float:
        """Raw weight size in GB for a quant level (params * bpw / 8)."""
        return self.params_b * QUANT_BPW.get(quant, 16.0) / 8.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ModelSpec:
        fields = {k: d.get(k) for k in cls.__dataclass_fields__ if k in d}
        return cls(**fields)

    @classmethod
    def from_registry(cls, name: str) -> ModelSpec:
        """Build a spec from the bundled registry (offline, exact)."""
        arch = MODEL_ARCH.get(name, DEFAULT_ARCH)
        ident = parse_identity(name)
        return cls(
            name=name,
            params_b=MODEL_PARAMS_B[name],
            n_layers=arch["n_layers"],
            n_kv_heads=arch["n_kv_heads"],
            d_head=arch["d_head"],
            family=MODEL_FAMILY.get(name),
            variant=ident.variant,
            native_quant=ident.quant,
            source=SOURCE_REGISTRY,
            registry_alias=name,
        )


# -- Pure parsers (dict -> ModelSpec) ----------------------------------


def parse_param_size(label: str | None) -> float | None:
    """Parse an Ollama ``parameter_size`` label (e.g. ``3.2B``, ``494.03M``)."""
    if not label:
        return None
    m = _PARAM_SIZE_RE.search(label)
    if not m:
        return None
    value = float(m.group(1))
    return value / 1000.0 if m.group(2).lower() == "m" else value


def spec_from_ollama_show(name: str, payload: dict) -> ModelSpec:
    """Build a ModelSpec from an Ollama ``/api/show`` response.

    Reads GGUF metadata under ``model_info`` (``<arch>.block_count``,
    ``<arch>.attention.head_count[_kv]``, ``<arch>.embedding_length``) and the
    human ``details`` block (parameter size, quantization level).
    """
    details = payload.get("details") or {}
    info = payload.get("model_info") or {}
    arch = info.get("general.architecture") or details.get("family") or ""

    def _info(suffix: str) -> int | None:
        val = info.get(f"{arch}.{suffix}")
        return int(val) if isinstance(val, (int, float)) else None

    n_layers = _info("block_count")
    n_heads = _info("attention.head_count")
    n_kv_heads = _info("attention.head_count_kv") or n_heads
    hidden = _info("embedding_length")
    # d_head: prefer explicit key_length, else hidden / heads.
    d_head = _info("attention.key_length")
    if d_head is None and hidden and n_heads:
        d_head = hidden // n_heads

    params_b = parse_param_size(details.get("parameter_size"))
    if params_b is None and info:
        total = info.get("general.parameter_count")
        if isinstance(total, (int, float)):
            params_b = float(total) / 1e9

    missing = [
        k
        for k, v in {
            "params_b": params_b,
            "n_layers": n_layers,
            "n_kv_heads": n_kv_heads,
            "d_head": d_head,
        }.items()
        if not v
    ]
    if missing:
        raise ResolverError(
            f"Ollama /api/show for '{name}' missing required fields: {', '.join(missing)} "
            f"(architecture key '{arch}'). Use manual overrides."
        )

    ident = parse_identity(name)
    return ModelSpec(
        name=name,
        params_b=round(params_b, 4),
        n_layers=n_layers,
        n_kv_heads=n_kv_heads,
        d_head=d_head,
        hidden_size=hidden,
        native_quant=ident.quant or parse_quant(details.get("quantization_level") or ""),
        family=ident.family or (arch or None),
        variant=ident.variant,
        source=SOURCE_OLLAMA,
    )


def _first_key(config: dict, keys: tuple[str, ...]) -> int | None:
    """First present, positive int among ``keys`` in an HF config."""
    for k in keys:
        v = config.get(k)
        if isinstance(v, int) and v > 0:
            return v
    return None


def moe_from_config(config: dict) -> dict:
    """Extract MoE geometry from an HF ``config.json``.

    Every family spells these differently (Mixtral ``num_local_experts``,
    DeepSeek ``n_routed_experts``, Qwen ``num_experts``), so each field is tried
    against a list of aliases. Returns empty-ish values for a dense model.

    ``intermediate_size`` is only accepted as the expert width when the config
    also declares experts -- on a dense model that key is the ordinary FFN width
    and would otherwise be mistaken for an expert.
    """
    num_experts = _first_key(config, MOE_NUM_EXPERTS_KEYS)
    top_k = _first_key(config, MOE_TOPK_KEYS)
    if not num_experts or not top_k:
        return {}
    return {
        "num_experts": num_experts,
        "experts_per_token": top_k,
        "moe_intermediate_size": _first_key(config, MOE_INTERMEDIATE_KEYS),
        "n_dense_layers": _first_key(config, MOE_DENSE_LAYER_KEYS) or 0,
    }


def attention_from_config(config: dict) -> dict:
    """Extract non-standard attention cache geometry from an HF ``config.json``.

    Returns only what is actually declared. A sliding window is reported without a
    pattern when the config gives no pattern, and ``arch()`` then declines to apply
    it -- an unplaceable window would shrink the cache estimate, and under-sizing
    KV is what turns "it fits" into an OOM.
    """
    config = unwrap_text_config(config)
    out: dict = {}
    lora = _first_key(config, MLA_LORA_RANK_KEYS)
    rope = _first_key(config, MLA_ROPE_DIM_KEYS)
    if lora and rope:
        out["kv_lora_rank"] = lora
        out["qk_rope_head_dim"] = rope
    window = _first_key(config, SWA_WINDOW_KEYS)
    if window:
        out["sliding_window"] = window
        pattern = _first_key(config, SWA_PATTERN_KEYS)
        if pattern:
            out["swa_global_every"] = pattern
        else:
            layer_types = config.get("layer_types")
            if isinstance(layer_types, list) and layer_types:
                full = sum(1 for x in layer_types if "full" in str(x))
                if full:
                    out["swa_global_every"] = max(round(len(layer_types) / full), 1)
    return out


def spec_from_hf(repo: str, config: dict, params_b: float | None) -> ModelSpec:
    """Build a ModelSpec from an HF ``config.json`` (+ param count from the API).

    Handles the real-world case where ``head_dim`` is ``null`` (compute it from
    ``hidden_size / num_attention_heads``) and GQA absent (MHA: kv == heads).
    """
    # Multimodal wrappers (Qwen3.5, Gemma 4) nest every architecture key under
    # `text_config`; reading the top level made both lines unplannable outright.
    config = unwrap_text_config(config)
    n_layers = config.get("num_hidden_layers")
    n_heads = config.get("num_attention_heads")
    n_kv_heads = config.get("num_key_value_heads") or n_heads
    hidden = config.get("hidden_size")
    d_head = config.get("head_dim")
    if not d_head and hidden and n_heads:
        d_head = hidden // n_heads

    missing = [
        k
        for k, v in {
            "num_hidden_layers": n_layers,
            "num_attention_heads": n_heads,
            "hidden_size": hidden,
            "params (safetensors.total)": params_b,
        }.items()
        if not v
    ]
    if missing:
        raise ResolverError(
            f"HF config for '{repo}' missing required fields: {', '.join(missing)}. "
            f"Use manual overrides (--params-b/--n-layers/--n-kv-heads/--d-head)."
        )

    ident = parse_identity(repo)
    return ModelSpec(
        name=repo,
        params_b=round(params_b, 4),
        n_layers=n_layers,
        n_kv_heads=n_kv_heads,
        d_head=d_head,
        hidden_size=hidden,
        vocab_size=config.get("vocab_size"),
        native_quant=ident.quant,
        family=ident.family or config.get("model_type"),
        variant=ident.variant,
        source=SOURCE_HF,
        **moe_from_config(config),
        **attention_from_config(config),
        **hybrid_from_config(config, n_layers),
    )


def spec_from_overrides(name: str, overrides: dict) -> ModelSpec | None:
    """Build a manual ModelSpec if overrides supply the full required set.

    Returns None if any of params_b/n_layers/n_kv_heads/d_head is absent, so the
    caller can fall through to other sources.
    """
    required = ("params_b", "n_layers", "n_kv_heads", "d_head")
    if not all(overrides.get(k) for k in required):
        return None
    ident = parse_identity(name)
    return ModelSpec(
        name=name,
        params_b=float(overrides["params_b"]),
        n_layers=int(overrides["n_layers"]),
        n_kv_heads=int(overrides["n_kv_heads"]),
        d_head=int(overrides["d_head"]),
        hidden_size=overrides.get("hidden_size"),
        native_quant=ident.quant,
        family=ident.family,
        variant=ident.variant,
        source=SOURCE_MANUAL,
    )


# -- Spec cache --------------------------------------------------------


def _cache_dir() -> Path:
    """Resolved-spec cache directory (override with CHIMERAFORGE_CACHE)."""
    base = os.environ.get("CHIMERAFORGE_CACHE")
    root = Path(base) if base else Path.home() / ".cache" / "chimeraforge"
    return root / "specs"


def measured_corpus_path() -> Path:
    """Path to the on-demand measured fitted_models.json (sibling of the cache).

    ``measure`` writes real benchmark-derived coefficients here; ``plan`` and
    ``suggest`` prefer it over the bundled data when it exists, so measured
    numbers are used automatically without ``--models-path``.
    """
    return _cache_dir().parent / "fitted_models.json"


def _cache_key(identifier: str) -> str:
    return re.sub(r"[^\w.-]", "_", identifier.lower())


# Cached specs describe someone else's repo, which can change under us. Long
# enough that offline work keeps working, short enough that a config edit lands.
SPEC_CACHE_TTL_DAYS = 30
_CACHE_STAMP = "_captured_at"


def _cache_age_days(captured: str | None) -> int | None:
    """Age of a cache stamp in days, or None when absent or unparseable."""
    if not captured:
        return None
    try:
        return (_dt.date.today() - _dt.date.fromisoformat(captured)).days
    except (ValueError, TypeError):
        return None


def _cache_load(identifier: str) -> ModelSpec | None:
    """Read a cached spec, ignoring one that is older than ``SPEC_CACHE_TTL_DAYS``.

    The cache is consulted ahead of the network, so without an expiry a repo whose
    config.json changes upstream is answered from the old copy indefinitely and
    there is no way to notice. A stamped, expiring entry re-fetches on its own.
    Entries written before stamping existed have no date and are treated as
    expired rather than trusted.
    """
    path = _cache_dir() / f"{_cache_key(identifier)}.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        captured = raw.pop(_CACHE_STAMP, None)
        age = _cache_age_days(captured)
        if age is None or age > SPEC_CACHE_TTL_DAYS:
            log.debug("spec cache for %s is stale (age=%s d), refetching", identifier, age)
            return None
        spec = ModelSpec.from_dict(raw)
        log.debug("spec cache hit for %s (age %s d)", identifier, age)
        return spec
    except (ValueError, TypeError) as exc:
        log.warning("ignoring corrupt spec cache %s: %s", path, exc)
        return None


def _cache_store(identifier: str, spec: ModelSpec) -> None:
    try:
        d = _cache_dir()
        d.mkdir(parents=True, exist_ok=True)
        payload = dict(spec.to_dict())
        payload[_CACHE_STAMP] = _dt.date.today().isoformat()
        (d / f"{_cache_key(identifier)}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        log.warning("could not write spec cache for %s: %s", identifier, exc)


# -- Network fetchers (network -> dict) --------------------------------


def _httpx():
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - exercised via error message
        raise ResolverError(
            "network resolution needs httpx; install with 'pip install chimeraforge[resolve]'."
        ) from exc
    return httpx


def fetch_ollama_show(tag: str, base_url: str = DEFAULT_OLLAMA_URL) -> dict:
    """Fetch raw ``/api/show`` JSON for an Ollama tag."""
    httpx = _httpx()
    url = base_url.rstrip("/") + "/api/show"
    try:
        resp = httpx.post(url, json={"name": tag}, timeout=_NETWORK_TIMEOUT_S)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise ResolverError(f"Ollama has no model '{tag}' (pull it first): {exc}") from exc
    except httpx.HTTPError as exc:
        raise ResolverError(f"could not reach Ollama at {base_url}: {exc}") from exc
    except ValueError as exc:  # non-JSON 200 body (captive portal / proxy)
        raise ResolverError(f"Ollama returned a non-JSON response at {base_url}: {exc}") from exc


def fetch_hf(repo: str, hf_token: str | None = None) -> tuple[dict, float | None]:
    """Fetch ``config.json`` and the safetensors param count for an HF repo."""
    httpx = _httpx()
    headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}
    cfg_url = f"https://huggingface.co/{repo}/resolve/main/config.json"
    info_url = f"https://huggingface.co/api/models/{repo}?expand[]=safetensors"
    try:
        cfg_resp = httpx.get(
            cfg_url, headers=headers, timeout=_NETWORK_TIMEOUT_S, follow_redirects=True
        )
        # HF returns 401 for BOTH gated and nonexistent repos (anti-enumeration);
        # the X-Error-Code header disambiguates (GatedRepo vs absent).
        if cfg_resp.status_code in (401, 403):
            if cfg_resp.headers.get("x-error-code") == "GatedRepo":
                raise ResolverError(
                    f"HF repo '{repo}' is gated; set HF_TOKEN (or pass --hf-token)."
                )
            raise ResolverError(
                f"HF repo '{repo}' not found or not accessible (check the org/name; "
                f"set HF_TOKEN if it is gated)."
            )
        if cfg_resp.status_code == 404:
            raise ResolverError(f"HF repo '{repo}' not found (check the org/name).")
        cfg_resp.raise_for_status()
        config = cfg_resp.json()

        params_b: float | None = None
        info_resp = httpx.get(
            info_url, headers=headers, timeout=_NETWORK_TIMEOUT_S, follow_redirects=True
        )
        if info_resp.status_code == 200:
            total = (info_resp.json().get("safetensors") or {}).get("total")
            if isinstance(total, (int, float)):
                params_b = float(total) / 1e9
        return config, params_b
    except httpx.HTTPError as exc:
        raise ResolverError(f"could not fetch HF metadata for '{repo}': {exc}") from exc
    except ValueError as exc:  # malformed JSON in config.json / model_info
        raise ResolverError(f"HF returned a non-JSON response for '{repo}': {exc}") from exc


# -- Top-level resolver ------------------------------------------------


def resolve_spec(
    identifier: str,
    *,
    ollama_url: str | None = None,
    hf_token: str | None = None,
    overrides: dict | None = None,
    use_cache: bool = True,
    allow_network: bool = True,
) -> ModelSpec:
    """Resolve *identifier* to a ModelSpec, trying sources in priority order.

    Args:
        identifier: Registry name, Ollama tag (``ollama:`` prefix optional), or
            HF repo (``org/name``).
        ollama_url: Ollama base URL; enables the Ollama path when set.
        hf_token: Token for gated HF repos (falls back to ``$HF_TOKEN``).
        overrides: Manual ``{params_b, n_layers, n_kv_heads, d_head, ...}``.
        use_cache: Read/write the on-disk spec cache.
        allow_network: If False, never touch the network (registry/cache only).

    Raises:
        ResolverError: If no source can produce a complete spec.
    """
    overrides = overrides or {}
    hf_token = hf_token or os.environ.get("HF_TOKEN")

    # 1. Manual overrides win outright.
    manual = spec_from_overrides(identifier, overrides)
    if manual is not None:
        return manual

    # 2. Exact registry hit.
    if identifier in MODEL_PARAMS_B:
        return ModelSpec.from_registry(identifier)

    # 3. Cache.
    if use_cache:
        cached = _cache_load(identifier)
        if cached is not None:
            return cached

    # Routing: an HF repo is ``org/name`` with no colon; an Ollama tag is
    # ``ollama:NAME``, anything with a colon, or (when a URL is given) a bare
    # name. HF is checked before the generic Ollama path so a slashed repo is
    # never sent to /api/show.
    explicit_ollama = identifier.startswith("ollama:")
    tag = identifier.split("ollama:", 1)[-1] if explicit_ollama else identifier
    is_hf = bool(_HF_REPO_RE.match(identifier)) and ":" not in identifier
    is_ollama = explicit_ollama or ":" in identifier or bool(ollama_url)

    def _approx_or_raise() -> ModelSpec:
        approx = resolve_model(identifier)
        if approx is None:
            raise ResolverError(
                f"could not resolve '{identifier}'. Pass an Ollama tag (ollama:NAME), an HF "
                f"repo (org/name), or manual overrides "
                f"(--params-b/--n-layers/--n-kv-heads/--d-head)."
            )
        base = ModelSpec.from_registry(approx)
        ident = parse_identity(identifier)
        log.warning("approximated '%s' -> registry model '%s'", identifier, approx)
        return ModelSpec(
            name=identifier,
            params_b=base.params_b,
            n_layers=base.n_layers,
            n_kv_heads=base.n_kv_heads,
            d_head=base.d_head,
            hidden_size=base.hidden_size,
            native_quant=ident.quant or base.native_quant,
            family=base.family,
            variant=ident.variant,
            source=SOURCE_REGISTRY_APPROX,
            registry_alias=approx,
        )

    # 4. Hugging Face (slashed repo).
    if allow_network and is_hf:
        config, params_b = fetch_hf(identifier, hf_token)
        spec = spec_from_hf(identifier, config, params_b)
        if use_cache:
            _cache_store(identifier, spec)
        return spec

    # 5. Ollama. On failure (unreachable / not pulled), fall back to an offline
    # registry approximation rather than giving up outright.
    if allow_network and is_ollama:
        try:
            spec = spec_from_ollama_show(
                tag, fetch_ollama_show(tag, ollama_url or DEFAULT_OLLAMA_URL)
            )
            if use_cache:
                _cache_store(identifier, spec)
            return spec
        except ResolverError as exc:
            log.warning(
                "Ollama resolve failed for '%s' (%s); trying approximation", identifier, exc
            )
            return _approx_or_raise()

    # 6. Family/size approximation against the registry (offline last resort).
    return _approx_or_raise()
