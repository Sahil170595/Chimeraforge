"""Admit a standard PEFT linear LoRA adapter against pinned local SafeTensors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path
import re

from .manifest import DTYPE_BYTES, ManifestError, _digest, _load_json, _object


@dataclass(frozen=True)
class AdapterAdmission:
    base_sha256: str
    adapter_sha256: str
    config_sha256: str
    base_repo: str
    base_revision: str
    targets: tuple[str, ...]
    rank: int
    scale: float
    tensor_bytes: int

    def to_dict(self) -> dict:
        return {**asdict(self), "targets": list(self.targets)}


def _headers(path: Path) -> tuple[str, dict[str, tuple[str, tuple[int, ...]]]]:
    try:
        from safetensors import SafetensorError, safe_open
        import numpy  # noqa: F401 -- required by the native NumPy framework selector
    except ImportError as exc:
        raise ManifestError("install chimeraforge[weightspace] to inspect SafeTensors") from exc
    try:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        with safe_open(str(path), framework="numpy") as f:
            headers = {}
            for name in f.keys():
                header = f.get_slice(name)
                headers[name] = header.get_dtype(), tuple(header.get_shape())
        return digest, headers
    except (OSError, SafetensorError, ValueError) as exc:
        raise ManifestError(f"cannot read SafeTensors checkpoint: {path.name}") from exc


def admit_adapter(
    base: str | Path,
    adapter_dir: str | Path,
    *,
    base_repo: str,
    base_revision: str,
    base_sha256: str,
) -> AdapterAdmission:
    """Check one dense linear LoRA adapter's pinned base, target coverage, shapes and bytes."""
    digest = _digest(base_sha256, "base")
    if not isinstance(base_repo, str) or not base_repo:
        raise ManifestError("base_repo is required")
    if not isinstance(base_revision, str) or not re.fullmatch(
        r"(?:[a-f0-9]{40}|[a-f0-9]{64})", base_revision
    ):
        raise ManifestError("base_revision must be an immutable commit digest")
    directory = Path(adapter_dir)
    try:
        config_bytes = (directory / "adapter_config.json").read_bytes()
    except OSError as exc:
        raise ManifestError("cannot read adapter_config.json") from exc
    config = _object(_load_json(config_bytes), "adapter_config")
    if (config.get("base_model_name_or_path"), config.get("revision")) != (
        base_repo,
        base_revision,
    ):
        raise ManifestError("adapter declares a different base repository or immutable revision")
    if config.get("peft_type") != "LORA" or config.get("bias", "none") != "none":
        raise ManifestError("expected ordinary bias-free PEFT LoRA")
    for setting in (
        "fan_in_fan_out",
        "use_rslora",
        "use_dora",
        "rank_pattern",
        "alpha_pattern",
        "modules_to_save",
        "lora_bias",
        "target_parameters",
        "layer_replication",
        "layers_to_transform",
        "layers_pattern",
        "exclude_modules",
        "alora_invocation_tokens",
        "megatron_config",
        "trainable_token_indices",
        "use_qalora",
        "use_bdlora",
    ):
        value = config.get(setting)
        if value is not None and value is not False and value != {} and value != []:
            raise ManifestError(f"unsupported LoRA configuration: {setting}")
    rank, alpha = config.get("r"), config.get("lora_alpha")
    if type(rank) is not int or rank <= 0 or type(alpha) not in (int, float):
        raise ManifestError("invalid LoRA rank or scale")
    try:
        scale = alpha / rank
        if not math.isfinite(scale):
            raise ManifestError("invalid LoRA scale")
    except OverflowError as exc:
        raise ManifestError("invalid LoRA scale") from exc
    targets = config.get("target_modules")
    if (
        not isinstance(targets, list)
        or not targets
        or not all(isinstance(t, str) and t for t in targets)
    ):
        raise ManifestError("expected a nonempty list of literal target modules")
    base_hash, base_headers = _headers(Path(base))
    if base_hash != digest:
        raise ManifestError("base SHA-256 mismatch")
    adapter_hash, adapter = _headers(directory / "adapter_model.safetensors")
    modules = {
        key.removesuffix(".weight"): header
        for key, header in base_headers.items()
        if key.endswith(".weight")
    }
    selected = set()
    for target in targets:
        matches = {m for m in modules if m == target or m.endswith("." + target)}
        if not matches:
            raise ManifestError(f"target missing from base: {target}")
        selected.update(matches)
    expected_keys = set()
    tensor_bytes = 0
    for name in sorted(selected):
        base_dtype, base_shape = modules[name]
        if (
            len(base_shape) != 2
            or not all(base_shape)
            or base_dtype not in {"F16", "BF16", "F32", "F64"}
        ):
            raise ManifestError(f"expected a floating-point matrix for {name}")
        rows, cols = base_shape
        for kind, shape in (("A", (rank, cols)), ("B", (rows, rank))):
            key = f"base_model.model.{name}.lora_{kind}.weight"
            expected_keys.add(key)
            header = adapter.get(key)
            if (
                header is None
                or header[1] != shape
                or header[0] not in {"F16", "BF16", "F32", "F64"}
            ):
                raise ManifestError(f"missing or incompatible adapter tensor: {key}")
            tensor_bytes += DTYPE_BYTES[header[0]] * math.prod(shape)
    if set(adapter) != expected_keys:
        raise ManifestError("adapter contains undeclared target or unsupported tensor keys")
    return AdapterAdmission(
        digest,
        adapter_hash,
        hashlib.sha256(config_bytes).hexdigest(),
        base_repo,
        base_revision,
        tuple(sorted(selected)),
        rank,
        scale,
        tensor_bytes,
    )
