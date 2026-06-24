"""Seven predictive models for the capacity planner (predict-only).

Stripped of fit() methods and numpy/scipy dependencies. These models
load pre-fitted coefficients from fitted_models.json and predict only.

1. VRAMModel:       VRAM_GB = params_B * bpw/8 * overhead + KV_cache_GB
2. ThroughputModel: Lookup table + fallbacks (quant multiplier, size power law)
3. ScalingModel:    Amdahl's law: eta(N) = 1/(s + (1-s)*N)
4. QualityModel:    Lookup table + FP16 baseline + avg delta per quant
5. CostModel:       cost_per_token = hw_cost_per_hour / (tok/s * 3600)
6. LatencyModel:    M/D/1 approximation with 70% utilisation cap
7. SafetyModel:     Lookup of refusal rate + RTSI risk (TR134/TR142), no extrapolation
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from chimeraforge.planner.constants import (
    MBU_DEFAULT,
    MODEL_ARCH,
    MODEL_FAMILY,
    MODEL_PARAMS_B,
    QUANT_BPW,
)
from chimeraforge.planner.hardware import bandwidth_ratio, get_gpu

log = logging.getLogger("chimeraforge.planner.models")


# ── 1. VRAM Model ─────────────────────────────────────────────────────


@dataclass
class VRAMModel:
    """Predict GPU VRAM usage for a (model, quant, context_length) combo."""

    overhead_factor: float = 1.10
    act_coeff: float = 0.0
    fitted: bool = False

    def predict(
        self,
        model: str,
        quant: str,
        context_length: int = 2048,
        batch_size: int = 1,
        params_b: float | None = None,
        arch: dict[str, int] | None = None,
    ) -> float:
        """Predict VRAM in GB.

        ``params_b``/``arch`` override the bundled registry, letting a resolved
        off-registry ModelSpec drive an exact weight + KV-cache estimate.
        """
        params = params_b if params_b is not None else MODEL_PARAMS_B.get(model, 3.0)
        bpw = QUANT_BPW.get(quant, 16.0)
        weight_gb = params * bpw / 8

        arch = arch or MODEL_ARCH.get(model, {"n_layers": 32, "n_kv_heads": 8, "d_head": 128})

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

    def predict(
        self,
        model: str,
        backend: str,
        quant: str = "FP16",
        hardware: str | None = None,
    ) -> float:
        """Predict N=1 tok/s."""
        key = f"{model}|{backend}|{quant}"
        if key in self.lookup:
            tps = self.lookup[key]
        else:
            fp16_key = f"{model}|{backend}|FP16"
            fp16_tps = self.lookup.get(fp16_key)
            qm = self.quant_multipliers.get(quant, 1.0)

            if fp16_tps:
                tps = fp16_tps * qm
            else:
                params = MODEL_PARAMS_B.get(model, 3.0)
                tps = self.size_power_a * params ** (-self.size_power_b) * qm

        if hardware:
            tps *= bandwidth_ratio(hardware)

        return max(tps, 0.1)

    def roofline_tps(
        self,
        params_b: float,
        quant: str = "FP16",
        hardware: str | None = None,
        mbu: float = MBU_DEFAULT,
    ) -> float:
        """Memory-bandwidth-bound decode throughput for an off-registry model.

        Decode reads every weight once per token, so the FP16 ceiling is
        ``bandwidth / (2 * params_GB)``; ``mbu`` discounts it to realised
        utilisation (calibrated to 0.65 on the llama3.2-1b ollama datapoint).
        The empirical quant multiplier is then applied on top -- quant speedups
        are not purely bandwidth proportional (dequant overhead), so a pure
        smaller-weight roofline would over-state them. Used when no measured
        lookup exists for (model, backend).
        """
        if params_b <= 0:
            return 0.1
        gpu = get_gpu(hardware) if hardware else None
        bandwidth = gpu.bandwidth_gbps if gpu else 556.0  # RTX 4080 reference
        fp16_weight_gb = params_b * 16.0 / 8.0
        base_tps = mbu * bandwidth / fp16_weight_gb
        qm = self.quant_multipliers.get(quant, 1.0)
        return max(base_tps * qm, 0.1)

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
    """Predict efficiency eta(N) for multi-agent concurrency."""

    serial_fractions: dict[str, float] = field(default_factory=dict)
    defaults: dict[str, float] = field(
        default_factory=lambda: {
            "ollama": 0.45,
            "vllm": 0.15,
            "tgi": 0.20,
        }
    )
    fitted: bool = False

    def predict_eta(self, model: str, backend: str, n_agents: int) -> float:
        """Predict efficiency eta(N) = per-agent throughput / N=1 throughput."""
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

    TIERS = {
        "negligible": -3.0,
        "acceptable": -10.0,
        "concerning": -15.0,
    }

    def predict(self, model: str, quant: str) -> float:
        """Predict composite quality [0, 1]."""
        key = f"{model}|{quant}"
        if key in self.lookup:
            return self.lookup[key]
        fp16 = self.fp16_baselines.get(model)
        if fp16 is None:
            # Infer FP16 baseline from lookup if available
            fp16_key = f"{model}|FP16"
            if fp16_key in self.lookup:
                fp16 = self.lookup[fp16_key]
        if fp16 is not None:
            if quant == "FP16":
                return fp16
            delta = self.quant_deltas.get(quant, 0.0)
            return max(0.0, min(1.0, fp16 + delta))
        return 0.5

    def estimate(self, model: str, quant: str, family: str | None = None) -> tuple[float, str]:
        """Predict quality and report provenance: measured | estimated | unknown.

        - ``measured``: a direct (model, quant) lookup hit (TR-backed).
        - ``estimated``: derived from the model's own FP16 baseline + quant delta,
          or, for an off-registry model, the mean FP16 baseline of its family.
        - ``unknown``: no basis -- returns the neutral 0.5 prior, flagged so the
          caller never mistakes a guess for data.
        """
        if f"{model}|{quant}" in self.lookup:
            return self.lookup[f"{model}|{quant}"], "measured"

        fp16 = self.fp16_baselines.get(model)
        if fp16 is None and f"{model}|FP16" in self.lookup:
            fp16 = self.lookup[f"{model}|FP16"]
        if fp16 is None and family is not None:
            same_family = [
                v for m, v in self.fp16_baselines.items() if MODEL_FAMILY.get(m) == family
            ]
            if same_family:
                fp16 = sum(same_family) / len(same_family)

        if fp16 is None:
            return 0.5, "unknown"
        if quant == "FP16":
            return fp16, "estimated"
        delta = self.quant_deltas.get(quant, 0.0)
        return max(0.0, min(1.0, fp16 + delta)), "estimated"

    def quality_tier(self, model: str, quant: str) -> str:
        """Classify quality drop into a tier."""
        fp16 = self.fp16_baselines.get(model)
        if fp16 is None:
            fp16_key = f"{model}|FP16"
            if fp16_key in self.lookup:
                fp16 = self.lookup[fp16_key]
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

    hw_cost_per_hour: float = 0.035

    def predict_cost_per_1m(self, tok_per_s: float, hw_cost_hr: float | None = None) -> float:
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
        n1_tps: float | None = None,
    ) -> dict:
        """Predict p95 latency and utilisation.

        ``n1_tps`` lets the caller supply an already-computed N=1 throughput (e.g.
        a roofline estimate for an off-registry model) so the service time stays
        consistent with the engine's throughput choice instead of being
        recomputed from the lookup/power-law default.
        """
        service_ms = None

        if n1_tps is not None and n1_tps > 0:
            service_ms = avg_tokens / n1_tps * 1000
        elif throughput_model is not None:
            tps = throughput_model.predict(model, backend, quant, hardware)
            if tps > 0:
                service_ms = avg_tokens / tps * 1000

        if service_ms is None:
            key = f"{model}|{backend}"
            service_ms = self.service_times.get(key)

        if service_ms is None:
            service_ms = 5000.0

        service_s = service_ms / 1000.0
        mu = 1.0 / service_s if service_s > 0 else 1e6

        eta = 1.0
        if scaling_model and n_agents > 1:
            eta = scaling_model.predict_eta(model, backend, n_agents)
        total_capacity = n_agents * mu * eta

        rho = request_rate / total_capacity if total_capacity > 0 else 1.0
        saturated = rho > self.safety_factor

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


# ── 7. Safety Model ───────────────────────────────────────────────────


@dataclass
class SafetyModel:
    """Predict refusal rate + RTSI risk for a (model, quant) combo.

    Backed by TR134 (refusal rates) and TR142 (RTSI behavioural screen).
    Lookup-only: safety does not generalise across cells (TR142/TR146), so
    unknown (model, quant) pairs return None rather than an extrapolated guess.
    """

    lookup: dict[str, float] = field(default_factory=dict)
    fp16_baselines: dict[str, float] = field(default_factory=dict)
    rtsi: dict[str, dict] = field(default_factory=dict)
    fitted: bool = False

    def predict_refusal(self, model: str, quant: str) -> float | None:
        """Refusal rate in [0, 1], or None if the cell is unscreened."""
        return self.lookup.get(f"{model}|{quant}")

    def rtsi_risk(self, model: str, quant: str) -> str:
        """RTSI risk tier: HIGH, MODERATE, LOW, or UNKNOWN if unscreened."""
        entry = self.rtsi.get(f"{model}|{quant}")
        if entry is None:
            return "UNKNOWN"
        return entry.get("risk", "UNKNOWN")

    def refusal_drop_pp(self, model: str, quant: str) -> float | None:
        """Refusal change vs the model's FP16 baseline, in percentage points.

        Negative = safety regression. None if either value is unavailable.
        """
        refusal = self.predict_refusal(model, quant)
        fp16 = self.fp16_baselines.get(model)
        if refusal is None or fp16 is None:
            return None
        return (refusal - fp16) * 100

    def to_dict(self) -> dict:
        return {
            "lookup": self.lookup,
            "fp16_baselines": self.fp16_baselines,
            "rtsi": self.rtsi,
            "fitted": self.fitted,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SafetyModel:
        m = cls(
            lookup=d.get("lookup", {}),
            fp16_baselines=d.get("fp16_baselines", {}),
            rtsi=d.get("rtsi", {}),
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
    safety: SafetyModel = field(default_factory=SafetyModel)


def load_models(path: Path | str) -> PlannerModels:
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
        safety=SafetyModel.from_dict(data.get("safety", {})),
    )
    log.info("Models loaded from %s", path)
    return models


def load_bundled_models() -> PlannerModels:
    """Load the pre-fitted models bundled with the package."""
    import importlib.resources as pkg_resources

    data_dir = pkg_resources.files("chimeraforge.planner") / "data"
    models_file = data_dir / "fitted_models.json"
    with pkg_resources.as_file(models_file) as p:
        return load_models(p)
