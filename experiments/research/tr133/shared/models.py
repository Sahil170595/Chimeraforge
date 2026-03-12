"""TR133 — Six predictive models for the capacity planner.

1. VRAMModel:       VRAM_GB = params_B * bpw/8 * overhead + KV_cache_GB
2. ThroughputModel: Lookup table + fallbacks (quant multiplier, size power law)
3. ScalingModel:    Amdahl (Ollama) or power law (vLLM/TGI)
4. QualityModel:    Lookup table + FP16 baseline + avg delta per quant
5. CostModel:       cost_per_token = hw_cost_per_hour / (tok/s * 3600)
6. LatencyModel:    M/D/1 approximation with 70% utilisation cap
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

from research.tr133.shared.data_loader import (
    LatencyRecord,
    PlannerDataset,
    QualityRecord,
    ScalingRecord,
    ThroughputRecord,
    VRAMRecord,
)
from research.tr133.shared.hardware_db import bandwidth_ratio
from research.tr133.shared.utils import (
    MODEL_ARCH,
    MODEL_PARAMS_B,
    QUANT_BPW,
)

log = logging.getLogger("tr133.models")


# ── 1. VRAM Model ─────────────────────────────────────────────────────


@dataclass
class VRAMModel:
    """Predict GPU VRAM usage for a (model, quant, context_length) combo.

    Formula: VRAM = weight_gb * overhead + kv_cache_gb + activation_gb
    - activation_gb captures quadratic attention memory at high context
    - act_coeff fitted from residuals after weight + KV subtraction
    """

    overhead_factor: float = 1.10
    act_coeff: float = 0.0  # GB per (seq_len/1024)^2 per layer
    fitted: bool = False

    def fit(self, records: list[VRAMRecord]) -> None:
        """Two-pass fit: overhead from low-ctx data, act_coeff from residuals."""
        if not records:
            log.warning("VRAMModel: no records to fit")
            return

        # Pass 1: Fit overhead from ctx <= 2048 (activation memory negligible)
        ratios = []
        for r in records:
            if r.context_length > 2048:
                continue
            params = MODEL_PARAMS_B.get(r.model)
            arch = MODEL_ARCH.get(r.model)
            if params is None or arch is None:
                continue
            weight_gb = params * 16 / 8
            kv_bytes = (
                2
                * arch["n_layers"]
                * 1
                * r.context_length
                * arch["n_kv_heads"]
                * arch["d_head"]
                * 2
            )
            kv_gb = kv_bytes / (1024**3)
            measured_gb = r.vram_peak_mb / 1024
            net_gb = measured_gb - kv_gb
            if weight_gb > 0 and net_gb > 0:
                ratios.append(net_gb / weight_gb)

        if ratios:
            self.overhead_factor = float(np.median(ratios))

        # Pass 2: Fit activation coefficient from ALL data
        # residual = measured - (weight*overhead + kv_cache)
        # Model: residual ≈ act_coeff * n_layers * (seq_len/1024)^2
        residuals_x = []  # n_layers * (seq_len/1024)^2
        residuals_y = []  # measured - predicted
        for r in records:
            params = MODEL_PARAMS_B.get(r.model)
            arch = MODEL_ARCH.get(r.model)
            if params is None or arch is None:
                continue
            weight_gb = params * 16 / 8
            kv_bytes = (
                2
                * arch["n_layers"]
                * 1
                * r.context_length
                * arch["n_kv_heads"]
                * arch["d_head"]
                * 2
            )
            kv_gb = kv_bytes / (1024**3)
            pred_no_act = weight_gb * self.overhead_factor + kv_gb
            measured_gb = r.vram_peak_mb / 1024
            residual = measured_gb - pred_no_act
            x = arch["n_layers"] * (r.context_length / 1024) ** 2
            residuals_x.append(x)
            residuals_y.append(max(0, residual))

        if residuals_x:
            x_arr = np.array(residuals_x)
            y_arr = np.array(residuals_y)
            # Least-squares fit: y = coeff * x
            denom = float(np.sum(x_arr**2))
            if denom > 0:
                self.act_coeff = float(np.sum(x_arr * y_arr) / denom)

        log.info(
            "VRAMModel: overhead=%.3f, act_coeff=%.6f (from %d measurements)",
            self.overhead_factor,
            self.act_coeff,
            len(records),
        )
        self.fitted = True

    def predict(
        self,
        model: str,
        quant: str,
        context_length: int = 2048,
        batch_size: int = 1,
    ) -> float:
        """Predict VRAM in GB."""
        params = MODEL_PARAMS_B.get(model, 3.0)
        bpw = QUANT_BPW.get(quant, 16.0)
        weight_gb = params * bpw / 8

        arch = MODEL_ARCH.get(model, {"n_layers": 32, "n_kv_heads": 8, "d_head": 128})

        # KV cache: 2 * n_layers * batch * seq_len * n_kv_heads * d_head * 2 bytes
        kv_bytes = (
            2
            * arch["n_layers"]
            * batch_size
            * context_length
            * arch["n_kv_heads"]
            * arch["d_head"]
            * 2
        )
        kv_gb = kv_bytes / (1024**3)

        # Activation memory (quadratic in context length)
        act_gb = self.act_coeff * arch["n_layers"] * (context_length / 1024) ** 2

        return weight_gb * self.overhead_factor + kv_gb + act_gb

    def to_dict(self) -> dict:
        return {
            "overhead_factor": self.overhead_factor,
            "act_coeff": self.act_coeff,
            "fitted": self.fitted,
        }

    @classmethod
    def from_dict(cls, d: dict) -> VRAMModel:
        m = cls(
            overhead_factor=d.get("overhead_factor", 1.10),
            act_coeff=d.get("act_coeff", 0.0),
        )
        m.fitted = d.get("fitted", False)
        return m


# ── 2. Throughput Model ───────────────────────────────────────────────


@dataclass
class ThroughputModel:
    """Predict tokens/s for a (model, backend, quant) at N=1."""

    lookup: dict[str, float] = field(default_factory=dict)
    quant_multipliers: dict[str, float] = field(default_factory=dict)
    size_power_a: float = 100.0
    size_power_b: float = 0.5
    fitted: bool = False

    def fit(self, records: list[ThroughputRecord]) -> None:
        """Build lookup table from N=1 throughput records, fit fallbacks."""
        # 1. Build (model, backend, quant) -> [tok/s] lookup
        groups: dict[str, list[float]] = {}
        for r in records:
            if r.n_agents != 1:
                continue
            key = f"{r.model}|{r.backend}|{r.quant}"
            groups.setdefault(key, []).append(r.tok_per_s)

        for key, vals in groups.items():
            self.lookup[key] = float(np.mean(vals))

        # 2. Quant multipliers: ratio of Q_X mean to FP16 mean per model
        model_fp16: dict[str, list[float]] = {}
        model_quant: dict[str, dict[str, list[float]]] = {}
        for r in records:
            if r.n_agents != 1:
                continue
            if r.quant == "FP16":
                model_fp16.setdefault(r.model, []).append(r.tok_per_s)
            else:
                model_quant.setdefault(r.model, {}).setdefault(r.quant, []).append(
                    r.tok_per_s
                )

        # Average multiplier across models per quant level
        quant_ratios: dict[str, list[float]] = {}
        for model, quants in model_quant.items():
            fp16_mean = np.mean(model_fp16.get(model, [1.0]))
            if fp16_mean <= 0:
                continue
            for q, vals in quants.items():
                ratio = np.mean(vals) / fp16_mean
                quant_ratios.setdefault(q, []).append(ratio)

        for q, ratios in quant_ratios.items():
            self.quant_multipliers[q] = float(np.mean(ratios))
        self.quant_multipliers["FP16"] = 1.0

        # Apply default multipliers for quant levels with no empirical data.
        # Lower-precision quants decode faster (less memory bandwidth needed).
        _DEFAULT_QUANT_MULTIPLIERS = {
            "FP16": 1.0,
            "Q8_0": 1.3,
            "Q6_K": 1.5,
            "Q5_K_M": 1.7,
            "Q4_K_M": 1.9,
            "Q3_K_S": 2.1,
            "Q2_K": 2.3,
        }
        for q, default in _DEFAULT_QUANT_MULTIPLIERS.items():
            if q not in self.quant_multipliers:
                self.quant_multipliers[q] = default

        # 3. Size power law: tps = a * params_B^(-b)
        fp16_by_size: list[tuple[float, float]] = []
        for model, vals in model_fp16.items():
            params = MODEL_PARAMS_B.get(model)
            if params and len(vals) > 0:
                fp16_by_size.append((params, float(np.mean(vals))))

        if len(fp16_by_size) >= 2:
            sizes = np.array([s for s, _ in fp16_by_size])
            tps_vals = np.array([t for _, t in fp16_by_size])
            try:
                popt, _ = curve_fit(
                    lambda x, a, b: a * np.power(x, -b),
                    sizes,
                    tps_vals,
                    p0=[100.0, 0.5],
                    maxfev=5000,
                    bounds=([0, 0], [10000, 5]),
                )
                self.size_power_a = float(popt[0])
                self.size_power_b = float(popt[1])
            except Exception as exc:
                log.warning("ThroughputModel: power law fit failed: %s", exc)

        log.info(
            "ThroughputModel: %d lookup entries, %d quant multipliers, "
            "power law a=%.1f b=%.3f",
            len(self.lookup),
            len(self.quant_multipliers),
            self.size_power_a,
            self.size_power_b,
        )
        self.fitted = True

    def predict(
        self,
        model: str,
        backend: str,
        quant: str = "FP16",
        hardware: str | None = None,
    ) -> float:
        """Predict N=1 tok/s."""
        # Exact lookup
        key = f"{model}|{backend}|{quant}"
        if key in self.lookup:
            tps = self.lookup[key]
        else:
            # Fallback 1: FP16 baseline × quant multiplier
            fp16_key = f"{model}|{backend}|FP16"
            fp16_tps = self.lookup.get(fp16_key)
            qm = self.quant_multipliers.get(quant, 1.0)

            if fp16_tps:
                tps = fp16_tps * qm
            else:
                # Fallback 2: Size power law
                params = MODEL_PARAMS_B.get(model, 3.0)
                tps = self.size_power_a * params ** (-self.size_power_b) * qm

        # Hardware bandwidth scaling
        if hardware:
            tps *= bandwidth_ratio(hardware)

        return max(tps, 0.1)

    def to_dict(self) -> dict:
        return {
            "lookup": self.lookup,
            "quant_multipliers": self.quant_multipliers,
            "size_power_a": self.size_power_a,
            "size_power_b": self.size_power_b,
            "fitted": self.fitted,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ThroughputModel:
        m = cls(
            lookup=d.get("lookup", {}),
            quant_multipliers=d.get("quant_multipliers", {}),
            size_power_a=d.get("size_power_a", 100.0),
            size_power_b=d.get("size_power_b", 0.5),
        )
        m.fitted = d.get("fitted", False)
        return m


# ── 3. Scaling Model ──────────────────────────────────────────────────


@dataclass
class ScalingModel:
    """Predict efficiency η(N) for multi-agent concurrency."""

    serial_fractions: dict[str, float] = field(default_factory=dict)
    defaults: dict[str, float] = field(
        default_factory=lambda: {
            "ollama": 0.45,
            "vllm": 0.15,
            "tgi": 0.20,
        }
    )
    fitted: bool = False

    def fit(self, records: list[ScalingRecord]) -> None:
        """Store per-(model, backend) serial fractions, keeping best R²."""
        r2_tracker: dict[str, float] = {}
        for r in records:
            key = f"{r.model}|{r.backend}"
            existing_r2 = r2_tracker.get(key, -1.0)
            if r.r_squared > existing_r2:
                self.serial_fractions[key] = r.serial_fraction
                r2_tracker[key] = r.r_squared

        log.info("ScalingModel: %d serial fractions stored", len(self.serial_fractions))
        self.fitted = True

    def predict_eta(self, model: str, backend: str, n_agents: int) -> float:
        """Predict efficiency η(N) = per-agent throughput / N=1 throughput."""
        key = f"{model}|{backend}"
        s = self.serial_fractions.get(key, self.defaults.get(backend, 0.30))
        if n_agents <= 1:
            return 1.0
        return 1.0 / (s + (1.0 - s) * n_agents)

    def to_dict(self) -> dict:
        return {
            "serial_fractions": self.serial_fractions,
            "defaults": self.defaults,
            "fitted": self.fitted,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ScalingModel:
        m = cls(
            serial_fractions=d.get("serial_fractions", {}),
            defaults=d.get("defaults", {"ollama": 0.45, "vllm": 0.15, "tgi": 0.20}),
        )
        m.fitted = d.get("fitted", False)
        return m


# ── 4. Quality Model ──────────────────────────────────────────────────


@dataclass
class QualityModel:
    """Predict composite quality for a (model, quant) combo."""

    lookup: dict[str, float] = field(default_factory=dict)
    fp16_baselines: dict[str, float] = field(default_factory=dict)
    quant_deltas: dict[str, float] = field(default_factory=dict)
    fitted: bool = False

    # Tier boundaries (percentage-point drop from FP16)
    TIERS = {
        "negligible": -3.0,
        "acceptable": -10.0,
        "concerning": -15.0,
        # below -15pp: "unacceptable"
    }

    def fit(self, records: list[QualityRecord]) -> None:
        """Build lookup from TR124/TR125 quality records."""
        groups: dict[str, list[float]] = {}
        for r in records:
            key = f"{r.model}|{r.quant}"
            groups.setdefault(key, []).append(r.composite_quality)

        for key, vals in groups.items():
            self.lookup[key] = float(np.mean(vals))

        # FP16 baselines
        for key, val in self.lookup.items():
            model, quant = key.split("|")
            if quant == "FP16":
                self.fp16_baselines[model] = val

        # Average delta per quant level across models
        deltas: dict[str, list[float]] = {}
        for key, val in self.lookup.items():
            model, quant = key.split("|")
            if quant != "FP16" and model in self.fp16_baselines:
                delta = val - self.fp16_baselines[model]
                deltas.setdefault(quant, []).append(delta)

        for q, ds in deltas.items():
            self.quant_deltas[q] = float(np.mean(ds))

        log.info(
            "QualityModel: %d lookup entries, %d FP16 baselines, %d quant deltas",
            len(self.lookup),
            len(self.fp16_baselines),
            len(self.quant_deltas),
        )
        self.fitted = True

    def predict(self, model: str, quant: str) -> float:
        """Predict composite quality [0, 1]."""
        key = f"{model}|{quant}"
        if key in self.lookup:
            return self.lookup[key]
        # Fallback: FP16 baseline + average quant delta
        fp16 = self.fp16_baselines.get(model)
        if fp16 is not None:
            delta = self.quant_deltas.get(quant, 0.0)
            return max(0.0, min(1.0, fp16 + delta))
        # No data — return conservative estimate
        return 0.5

    def quality_tier(self, model: str, quant: str) -> str:
        """Classify quality drop into a tier."""
        fp16 = self.fp16_baselines.get(model)
        predicted = self.predict(model, quant)
        if fp16 is None or fp16 <= 0:
            return "unknown"
        drop_pp = (predicted - fp16) * 100
        if drop_pp >= self.TIERS["negligible"]:
            return "negligible"
        if drop_pp >= self.TIERS["acceptable"]:
            return "acceptable"
        if drop_pp >= self.TIERS["concerning"]:
            return "concerning"
        return "unacceptable"

    def to_dict(self) -> dict:
        return {
            "lookup": self.lookup,
            "fp16_baselines": self.fp16_baselines,
            "quant_deltas": self.quant_deltas,
            "fitted": self.fitted,
        }

    @classmethod
    def from_dict(cls, d: dict) -> QualityModel:
        m = cls(
            lookup=d.get("lookup", {}),
            fp16_baselines=d.get("fp16_baselines", {}),
            quant_deltas=d.get("quant_deltas", {}),
        )
        m.fitted = d.get("fitted", False)
        return m


# ── 5. Cost Model ─────────────────────────────────────────────────────


@dataclass
class CostModel:
    """Predict $/token and monthly cost from throughput + hardware cost."""

    hw_cost_per_hour: float = 0.035  # Default: RTX 4080 tier

    def predict_cost_per_1m(
        self, tok_per_s: float, hw_cost_hr: float | None = None
    ) -> float:
        """$/1M tokens = hw_cost_per_hour / (tok/s * 3600) * 1e6."""
        rate = hw_cost_hr if hw_cost_hr is not None else self.hw_cost_per_hour
        if tok_per_s <= 0:
            return float("inf")
        cost_per_tok = rate / (tok_per_s * 3600)
        return cost_per_tok * 1_000_000

    def predict_monthly(self, hw_cost_hr: float | None = None) -> float:
        """Monthly hardware cost = hw_cost_per_hour * 24 * 30."""
        rate = hw_cost_hr if hw_cost_hr is not None else self.hw_cost_per_hour
        return rate * 24 * 30

    def to_dict(self) -> dict:
        return {"hw_cost_per_hour": self.hw_cost_per_hour}

    @classmethod
    def from_dict(cls, d: dict) -> CostModel:
        return cls(hw_cost_per_hour=d.get("hw_cost_per_hour", 0.035))


# ── 6. Latency Model ─────────────────────────────────────────────────


@dataclass
class LatencyModel:
    """M/D/1 queueing approximation with 70% utilisation safety cap."""

    service_times: dict[str, float] = field(default_factory=dict)
    safety_factor: float = 0.70
    fitted: bool = False

    def fit(self, records: list[LatencyRecord]) -> None:
        """Derive N=1 service times from latency records.

        Uses median wall_ms per (model, backend) for robustness against outliers.
        """
        groups: dict[str, list[float]] = {}
        for r in records:
            if r.n_parallel != 1:
                continue
            key = f"{r.model}|{r.backend}"
            groups.setdefault(key, []).append(r.wall_ms)

        for key, vals in groups.items():
            self.service_times[key] = float(np.median(vals))

        log.info("LatencyModel: %d service time entries", len(self.service_times))
        self.fitted = True

    def predict_p95(
        self,
        model: str,
        backend: str,
        request_rate: float,
        n_agents: int = 1,
        avg_tokens: int = 128,
        quant: str = "FP16",
        throughput_model: ThroughputModel | None = None,
        scaling_model: ScalingModel | None = None,
        hardware: str | None = None,
    ) -> dict:
        """Predict p95 latency and utilisation.

        Uses M/D/1 approximation:
          - mean_wait = ρ / (2μ(1-ρ))  where ρ = λ/μ
          - p95 ≈ service_time + mean_wait * 3 (empirical tail factor)

        When throughput_model is provided, service time is derived from
        throughput at the given quant level (more accurate than raw wall_ms
        which only covers FP16).
        """
        service_ms = None

        # Prefer throughput-derived service time (quant-aware)
        if throughput_model is not None:
            tps = throughput_model.predict(model, backend, quant, hardware)
            if tps > 0:
                service_ms = avg_tokens / tps * 1000

        # Fallback: measured N=1 wall_ms (FP16 only)
        if service_ms is None:
            key = f"{model}|{backend}"
            service_ms = self.service_times.get(key)

        if service_ms is None:
            service_ms = 5000.0  # conservative default

        # Effective service rate per agent
        service_s = service_ms / 1000.0
        mu = 1.0 / service_s if service_s > 0 else 0.001

        # Scale for N agents (total capacity = N * mu * eta(N))
        eta = 1.0
        if scaling_model and n_agents > 1:
            eta = scaling_model.predict_eta(model, backend, n_agents)
        total_capacity = n_agents * mu * eta

        # Utilisation
        rho = request_rate / total_capacity if total_capacity > 0 else 1.0
        saturated = rho > self.safety_factor

        # M/D/1 mean waiting time
        if rho < 1.0:
            mean_wait_s = rho / (2 * total_capacity * (1 - rho))
            p95_ms = service_ms + mean_wait_s * 1000 * 3
        else:
            p95_ms = float("inf")

        return {
            "service_ms": round(service_ms, 1),
            "utilisation": round(rho, 3),
            "saturated": saturated,
            "p95_ms": round(p95_ms, 1) if p95_ms < 1e6 else float("inf"),
            "total_capacity_rps": round(total_capacity, 3),
        }

    def to_dict(self) -> dict:
        return {
            "service_times": self.service_times,
            "safety_factor": self.safety_factor,
            "fitted": self.fitted,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LatencyModel:
        m = cls(
            service_times=d.get("service_times", {}),
            safety_factor=d.get("safety_factor", 0.70),
        )
        m.fitted = d.get("fitted", False)
        return m


# ── Aggregate model container ─────────────────────────────────────────


@dataclass
class PlannerModels:
    vram: VRAMModel = field(default_factory=VRAMModel)
    throughput: ThroughputModel = field(default_factory=ThroughputModel)
    scaling: ScalingModel = field(default_factory=ScalingModel)
    quality: QualityModel = field(default_factory=QualityModel)
    cost: CostModel = field(default_factory=CostModel)
    latency: LatencyModel = field(default_factory=LatencyModel)


def fit_all_models(dataset: PlannerDataset) -> PlannerModels:
    """Fit all 6 models from the unified dataset."""
    models = PlannerModels()

    log.info("Fitting VRAMModel...")
    models.vram.fit(dataset.vram)

    log.info("Fitting ThroughputModel...")
    models.throughput.fit(dataset.throughput)

    log.info("Fitting ScalingModel...")
    models.scaling.fit(dataset.scaling)

    log.info("Fitting QualityModel...")
    models.quality.fit(dataset.quality)

    log.info("Fitting LatencyModel...")
    models.latency.fit(dataset.latency)

    return models


def serialize_models(models: PlannerModels, path: Path) -> None:
    """Save fitted models to JSON."""
    data = {
        "vram": models.vram.to_dict(),
        "throughput": models.throughput.to_dict(),
        "scaling": models.scaling.to_dict(),
        "quality": models.quality.to_dict(),
        "cost": models.cost.to_dict(),
        "latency": models.latency.to_dict(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log.info("Models serialized to %s", path)


def load_models(path: Path) -> PlannerModels:
    """Load fitted models from JSON."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    models = PlannerModels(
        vram=VRAMModel.from_dict(data.get("vram", {})),
        throughput=ThroughputModel.from_dict(data.get("throughput", {})),
        scaling=ScalingModel.from_dict(data.get("scaling", {})),
        quality=QualityModel.from_dict(data.get("quality", {})),
        cost=CostModel.from_dict(data.get("cost", {})),
        latency=LatencyModel.from_dict(data.get("latency", {})),
    )
    log.info("Models loaded from %s", path)
    return models
