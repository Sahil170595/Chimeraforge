"""TR133 — Unified data ingestion from TR123–TR132.

Loads CSV/JSON results from each prior TR and normalises them into
typed dataclass records for the predictive models.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
import logging
import re

import numpy as np

from research.tr133.shared.utils import repo_root

log = logging.getLogger("tr133.data_loader")

# ── Dataclasses ───────────────────────────────────────────────────────


@dataclass
class ThroughputRecord:
    model: str
    backend: str
    quant: str
    n_agents: int
    tok_per_s: float
    source_tr: str


@dataclass
class QualityRecord:
    model: str
    quant: str
    composite_quality: float
    source_tr: str


@dataclass
class VRAMRecord:
    model: str
    backend: str
    context_length: int
    vram_peak_mb: float
    source_tr: str


@dataclass
class LatencyRecord:
    model: str
    backend: str
    n_parallel: int
    wall_ms: float
    ttft_ms: float
    tokens_per_s: float
    source_tr: str


@dataclass
class CostRecord:
    model: str
    backend: str
    decode_tok_per_s: float
    decode_cost_per_1m: float
    source_tr: str


@dataclass
class ScalingRecord:
    model: str
    backend: str
    serial_fraction: float
    r_squared: float
    source_tr: str


@dataclass
class PlannerDataset:
    throughput: list[ThroughputRecord] = field(default_factory=list)
    quality: list[QualityRecord] = field(default_factory=list)
    vram: list[VRAMRecord] = field(default_factory=list)
    latency: list[LatencyRecord] = field(default_factory=list)
    cost: list[CostRecord] = field(default_factory=list)
    scaling: list[ScalingRecord] = field(default_factory=list)


# ── Model name normalisation ─────────────────────────────────────────

_QUANT_SUFFIX_RE = re.compile(
    r"[-:](?:q\d+_K(?:_[SM])?|q\d+_\d+|fp16|fp32)$", re.IGNORECASE
)


def _strip_quant(name: str) -> str:
    """'llama3.2:1b-instruct-q4_K_M' -> 'llama3.2:1b-instruct'."""
    m = _QUANT_SUFFIX_RE.search(name)
    return name[: m.start()] if m else name


def _extract_quant(name: str) -> str:
    """'llama3.2:1b-instruct-q4_K_M' -> 'Q4_K_M'."""
    m = _QUANT_SUFFIX_RE.search(name)
    return m.group(0).lstrip("-:").upper() if m else "FP16"


_NORMALISE_MAP = {
    "gpt2": "gpt2",
    "qwen2.5-0.5b": "qwen2.5-0.5b",
    "llama-3.2-1b": "llama3.2-1b",
    "llama3.2:1b-instruct": "llama3.2-1b",
    "llama3.2-1b": "llama3.2-1b",
    "qwen2.5-1.5b": "qwen2.5-1.5b",
    "qwen2.5:1.5b-instruct": "qwen2.5-1.5b",
    "phi-2": "phi-2",
    "phi:2.7b-chat-v2": "phi-2",
    "qwen2.5-3b": "qwen2.5-3b",
    "llama-3.2-3b": "llama3.2-3b",
    "llama3.2:3b-instruct": "llama3.2-3b",
    "llama3.2-3b": "llama3.2-3b",
    "llama3.1-8b": "llama3.1-8b",
    "llama3.1:8b-instruct": "llama3.1-8b",
}


def normalise_model(raw: str) -> str:
    """Normalise variant model names to canonical form."""
    base = _strip_quant(raw)
    # Try exact match
    if base in _NORMALISE_MAP:
        return _NORMALISE_MAP[base]
    # Case-insensitive, strip separators
    key = base.replace("-", "").replace(".", "").replace(":", "").lower()
    for src, dst in _NORMALISE_MAP.items():
        if src.replace("-", "").replace(".", "").replace(":", "").lower() == key:
            return dst
    return base


# ── Per-TR loaders ────────────────────────────────────────────────────


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default: int = 0) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def load_tr123(cfg: dict) -> tuple[list[ThroughputRecord], list[CostRecord]]:
    """TR123: KV-cache cost economics — throughput + cost records."""
    path = repo_root() / cfg["data_sources"]["tr123"]["cost_csv"]
    throughput: list[ThroughputRecord] = []
    cost: list[CostRecord] = []
    if not path.exists():
        log.warning("TR123 data not found: %s", path)
        return throughput, cost

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = normalise_model(row.get("model", ""))
            backend = row.get("backend", "").lower()
            tok_s = _safe_float(row.get("decode_tok_per_s"))
            cost_1m = _safe_float(row.get("decode_cost_per_1m"))

            if tok_s > 0:
                throughput.append(
                    ThroughputRecord(
                        model=model,
                        backend=backend,
                        quant="FP16",
                        n_agents=1,
                        tok_per_s=tok_s,
                        source_tr="tr123",
                    )
                )
            if tok_s > 0 and cost_1m > 0:
                cost.append(
                    CostRecord(
                        model=model,
                        backend=backend,
                        decode_tok_per_s=tok_s,
                        decode_cost_per_1m=cost_1m,
                        source_tr="tr123",
                    )
                )

    log.info("TR123: loaded %d throughput, %d cost records", len(throughput), len(cost))
    return throughput, cost


def load_tr124(cfg: dict) -> list[QualityRecord]:
    """TR124: FP16 quality baselines."""
    path = repo_root() / cfg["data_sources"]["tr124"]["quality_csv"]
    records: list[QualityRecord] = []
    if not path.exists():
        log.warning("TR124 data not found: %s", path)
        return records

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = normalise_model(row.get("model", ""))
            cq = _safe_float(row.get("composite_quality"))
            if cq > 0:
                records.append(
                    QualityRecord(
                        model=model,
                        quant="FP16",
                        composite_quality=cq,
                        source_tr="tr124",
                    )
                )

    log.info("TR124: loaded %d quality records", len(records))
    return records


def load_tr125(cfg: dict) -> list[QualityRecord]:
    """TR125: Quality across quantization levels."""
    path = repo_root() / cfg["data_sources"]["tr125"]["quality_csv"]
    records: list[QualityRecord] = []
    if not path.exists():
        log.warning("TR125 data not found: %s", path)
        return records

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_model = row.get("model", "")
            model = normalise_model(raw_model)
            quant = _extract_quant(raw_model)
            cq = _safe_float(row.get("composite_quality"))
            if cq > 0:
                records.append(
                    QualityRecord(
                        model=model,
                        quant=quant,
                        composite_quality=cq,
                        source_tr="tr125",
                    )
                )

    log.info("TR125: loaded %d quality records", len(records))
    return records


def load_tr127(cfg: dict) -> tuple[list[VRAMRecord], list[ThroughputRecord]]:
    """TR127: VRAM and throughput vs context length."""
    path = repo_root() / cfg["data_sources"]["tr127"]["metrics_csv"]
    vram: list[VRAMRecord] = []
    throughput: list[ThroughputRecord] = []
    if not path.exists():
        log.warning("TR127 data not found: %s", path)
        return vram, throughput

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status", "") != "ok":
                continue
            model = normalise_model(row.get("model", ""))
            backend = row.get("backend", "").lower()
            ctx = _safe_int(row.get("context_length"))
            vram_mb = _safe_float(row.get("vram_peak_mb"))
            tok_s = _safe_float(row.get("tokens_per_s"))

            if vram_mb > 0:
                vram.append(
                    VRAMRecord(
                        model=model,
                        backend=backend,
                        context_length=ctx,
                        vram_peak_mb=vram_mb,
                        source_tr="tr127",
                    )
                )
            if tok_s > 0 and row.get("mode") == "decode":
                throughput.append(
                    ThroughputRecord(
                        model=model,
                        backend=backend,
                        quant="FP16",
                        n_agents=1,
                        tok_per_s=tok_s,
                        source_tr="tr127",
                    )
                )

    log.info("TR127: loaded %d VRAM, %d throughput records", len(vram), len(throughput))
    return vram, throughput


def load_tr128(cfg: dict) -> list[LatencyRecord]:
    """TR128: Latency under concurrent load."""
    path = repo_root() / cfg["data_sources"]["tr128"]["metrics_csv"]
    records: list[LatencyRecord] = []
    if not path.exists():
        log.warning("TR128 data not found: %s", path)
        return records

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status", "") != "ok":
                continue
            model = normalise_model(row.get("model", ""))
            n_par = _safe_int(row.get("num_parallel", 1))
            wall = _safe_float(row.get("wall_ms"))
            ttft = _safe_float(row.get("ttft_ms"))
            tok_s = _safe_float(row.get("tokens_per_s"))

            if wall > 0:
                records.append(
                    LatencyRecord(
                        model=model,
                        backend="ollama",
                        n_parallel=n_par,
                        wall_ms=wall,
                        ttft_ms=ttft,
                        tokens_per_s=tok_s,
                        source_tr="tr128",
                    )
                )

    log.info("TR128: loaded %d latency records", len(records))
    return records


def load_tr129(cfg: dict) -> tuple[list[ThroughputRecord], list[ScalingRecord]]:
    """TR129: Amdahl scaling for Ollama."""
    src = cfg["data_sources"]["tr129"]
    csv_path = repo_root() / src["metrics_csv"]
    json_path = repo_root() / src["analysis_json"]

    throughput: list[ThroughputRecord] = []
    scaling: list[ScalingRecord] = []

    # CSV: per-request throughput
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("status", "") != "ok":
                    continue
                model = normalise_model(row.get("model", ""))
                n = _safe_int(row.get("n_agents", 1))
                tok_s = _safe_float(row.get("effective_tps"))
                if tok_s > 0:
                    throughput.append(
                        ThroughputRecord(
                            model=model,
                            backend="ollama",
                            quant="FP16",
                            n_agents=n,
                            tok_per_s=tok_s,
                            source_tr="tr129",
                        )
                    )

    # JSON: fitted Amdahl serial fractions
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            analysis = json.load(f)
        sc = analysis.get("scaling_laws", {})
        for model_key, model_data in sc.items():
            amdahl = model_data.get("amdahl", {})
            s = amdahl.get("serial_fraction")
            r2 = amdahl.get("r_squared")
            if s is not None:
                scaling.append(
                    ScalingRecord(
                        model=normalise_model(model_key),
                        backend="ollama",
                        serial_fraction=s,
                        r_squared=r2 or 0.0,
                        source_tr="tr129",
                    )
                )

    log.info(
        "TR129: loaded %d throughput, %d scaling records", len(throughput), len(scaling)
    )
    return throughput, scaling


def load_tr130(
    cfg: dict,
) -> tuple[list[ThroughputRecord], list[LatencyRecord], list[ScalingRecord]]:
    """TR130: Multi-backend throughput and scaling."""
    src = cfg["data_sources"]["tr130"]
    csv_path = repo_root() / src["metrics_csv"]
    json_path = repo_root() / src["analysis_json"]

    throughput: list[ThroughputRecord] = []
    latency: list[LatencyRecord] = []
    scaling: list[ScalingRecord] = []

    # CSV: per-request data
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("status", "") != "ok":
                    continue
                model = normalise_model(row.get("model", ""))
                backend = row.get("backend", "").lower()
                n = _safe_int(row.get("n_agents", 1))
                tok_s = _safe_float(row.get("effective_tps"))
                wall = _safe_float(row.get("wall_ms"))
                ttft = _safe_float(row.get("ttft_ms"))

                if tok_s > 0:
                    throughput.append(
                        ThroughputRecord(
                            model=model,
                            backend=backend,
                            quant="FP16",
                            n_agents=n,
                            tok_per_s=tok_s,
                            source_tr="tr130",
                        )
                    )
                if wall > 0:
                    latency.append(
                        LatencyRecord(
                            model=model,
                            backend=backend,
                            n_parallel=n,
                            wall_ms=wall,
                            ttft_ms=ttft,
                            tokens_per_s=tok_s,
                            source_tr="tr130",
                        )
                    )

    # JSON: fitted scaling laws
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            analysis = json.load(f)
        sl = analysis.get("scaling_laws", {})
        for backend_key, models in sl.items():
            for model_key, model_data in models.items():
                amdahl = model_data.get("amdahl", {})
                s = amdahl.get("serial_fraction")
                r2 = amdahl.get("r_squared")
                if s is not None:
                    scaling.append(
                        ScalingRecord(
                            model=normalise_model(model_key),
                            backend=backend_key,
                            serial_fraction=s,
                            r_squared=r2 or 0.0,
                            source_tr="tr130",
                        )
                    )

    log.info(
        "TR130: loaded %d throughput, %d latency, %d scaling records",
        len(throughput),
        len(latency),
        len(scaling),
    )
    return throughput, latency, scaling


# ── Unified loader ────────────────────────────────────────────────────


def load_all(cfg: dict) -> PlannerDataset:
    """Load data from all TRs into a unified PlannerDataset."""
    ds = PlannerDataset()

    # TR123
    t123, c123 = load_tr123(cfg)
    ds.throughput.extend(t123)
    ds.cost.extend(c123)

    # TR124
    ds.quality.extend(load_tr124(cfg))

    # TR125
    ds.quality.extend(load_tr125(cfg))

    # TR127
    v127, t127 = load_tr127(cfg)
    ds.vram.extend(v127)
    ds.throughput.extend(t127)

    # TR128
    ds.latency.extend(load_tr128(cfg))

    # TR129
    t129, s129 = load_tr129(cfg)
    ds.throughput.extend(t129)
    ds.scaling.extend(s129)

    # TR130
    t130, l130, s130 = load_tr130(cfg)
    ds.throughput.extend(t130)
    ds.latency.extend(l130)
    ds.scaling.extend(s130)

    log.info(
        "Total dataset: %d throughput, %d quality, %d VRAM, "
        "%d latency, %d cost, %d scaling",
        len(ds.throughput),
        len(ds.quality),
        len(ds.vram),
        len(ds.latency),
        len(ds.cost),
        len(ds.scaling),
    )
    return ds


# ── Train/val split ───────────────────────────────────────────────────


def train_val_split(
    records: list,
    train_frac: float = 0.80,
    seed: int = 42,
) -> tuple[list, list]:
    """Stratified 80/20 split by (model, backend) where available."""
    rng = np.random.default_rng(seed)
    # Group by stratification key
    groups: dict[str, list] = {}
    for r in records:
        model = getattr(r, "model", "")
        backend = getattr(r, "backend", getattr(r, "quant", ""))
        key = f"{model}|{backend}"
        groups.setdefault(key, []).append(r)

    train, val = [], []
    for key, group in groups.items():
        n = len(group)
        n_train = max(1, int(n * train_frac))
        indices = rng.permutation(n)
        for i, idx in enumerate(indices):
            if i < n_train:
                train.append(group[idx])
            else:
                val.append(group[idx])

    return train, val
