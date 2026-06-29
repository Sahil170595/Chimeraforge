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
    DEFAULT_ARCH,
    FLOPS_PER_PARAM_PER_TOKEN,
    KV_CACHE_UTILISATION,
    KV_DTYPE_BYTES,
    MBU_DEFAULT,
    MODEL_ARCH,
    MODEL_FAMILY,
    MODEL_PARAMS_B,
    PREFILL_MFU,
    QUANT_BPW,
)
from chimeraforge.planner.hardware import bandwidth_ratio, get_gpu

log = logging.getLogger("chimeraforge.planner.models")


# -- 1. VRAM Model -----------------------------------------------------


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

        arch = arch or MODEL_ARCH.get(model, DEFAULT_ARCH)
        kv_gb = self.kv_cache_gb(arch, context_length, batch_size)
        # Linear in context: flash/paged attention never materialises the O(ctx^2)
        # attention matrix, so activation memory is O(ctx). (A quadratic term
        # diverges unphysically at long context -- 130 GB at 32k for a 3B model.)
        act_gb = self.act_coeff * arch["n_layers"] * (context_length / 1024)

        return weight_gb * self.overhead_factor + kv_gb + act_gb

    @staticmethod
    def kv_cache_gb(arch: dict[str, int], context_length: int, batch_size: int = 1) -> float:
        """KV-cache size in GB: ``2 (K+V) * layers * batch * ctx * kv_heads * d_head * dtype``."""
        kv_bytes = (
            2
            * arch["n_layers"]
            * batch_size
            * context_length
            * arch["n_kv_heads"]
            * arch["d_head"]
            * KV_DTYPE_BYTES
        )
        return kv_bytes / (1024**3)

    def max_concurrent_seqs(
        self,
        params_b: float,
        quant: str,
        arch: dict[str, int],
        context_length: int,
        hw_vram_gb: float,
        utilisation: float = KV_CACHE_UTILISATION,
    ) -> int:
        """Max concurrent sequences a single GPU can hold, KV-cache bound.

        This is the real concurrency limiter for batched backends (vLLM/TGI):
        after model weights + activations, the remaining VRAM divided by the
        per-sequence KV-cache caps how many requests can be in flight at once.
        First-principles memory arithmetic -- no fitting. Returns 0 if the weights
        alone don't fit.
        """
        weight_gb = params_b * QUANT_BPW.get(quant, 16.0) / 8 * self.overhead_factor
        act_gb = (
            self.act_coeff * arch["n_layers"] * (context_length / 1024)
        )  # O(ctx), see predict()
        free_gb = hw_vram_gb * utilisation - weight_gb - act_gb
        per_seq_gb = self.kv_cache_gb(arch, context_length, batch_size=1)
        if per_seq_gb <= 0 or free_gb <= 0:
            return 0
        return int(free_gb / per_seq_gb)

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


# -- 2. Throughput Model -----------------------------------------------


@dataclass
class ThroughputModel:
    """Predict tokens/s for a (model, backend, quant) at N=1."""

    lookup: dict[str, float] = field(default_factory=dict)
    quant_multipliers: dict[str, float] = field(default_factory=dict)
    size_power_a: float = 100.0
    size_power_b: float = 0.5
    fitted: bool = False

    def quant_multiplier(self, quant: str) -> float:
        """Throughput multiplier for a quant vs FP16.

        Exact lookup when fitted; otherwise the nearest known quant by effective
        bpw (so legacy/i-quants like ``Q4_0``/``IQ4_XS`` get a sane speed instead
        of being treated as FP16). Falls back to 1.0 when nothing is known.
        """
        if quant in self.quant_multipliers:
            return self.quant_multipliers[quant]
        bpw = QUANT_BPW.get(quant)
        if bpw is None:
            return 1.0
        if bpw > 16.0:
            # Above FP16 (e.g. FP32): no dequant speedup, pure bandwidth penalty
            # (decode streams 2x the weight bytes). Nearest-bpw would wrongly pick
            # FP16=1.0 and predict the full FP16 rate.
            return 16.0 / bpw
        known = [
            (QUANT_BPW[q], mult) for q, mult in self.quant_multipliers.items() if q in QUANT_BPW
        ]
        if not known:
            return 1.0
        return min(known, key=lambda x: abs(x[0] - bpw))[1]

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
            qm = self.quant_multiplier(quant)

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

        Decode reads every weight once per token. Written as an FP16 bandwidth
        roofline times the empirical quant speedup:

            tps = (MBU * bw / fp16_weight_gb) * quant_multiplier(quant)

        This is algebraically identical to a *quantized*-weight roofline scaled by
        a dequant-efficiency factor: ``MBU*bw/quant_weight_gb * (qm * bpw/16)``.
        Using the measured multiplier (Q4_K_M ~= 1.9x) is deliberate -- a pure
        quantized roofline assumes decode is purely bandwidth-bound and predicts
        ~3.6x for Q4, ~2x higher than measured (dequant is not free). MBU=0.65 is
        calibrated on the llama3.2-1b ollama FP16 datapoint. Used when no measured
        lookup exists for (model, backend); the `measure` path supersedes it.
        """
        if params_b <= 0:
            return 0.1
        gpu = get_gpu(hardware) if hardware else None
        bandwidth = gpu.bandwidth_gbps if gpu else 556.0  # RTX 4080 reference
        fp16_weight_gb = params_b * 16.0 / 8.0
        base_tps = mbu * bandwidth / fp16_weight_gb
        return max(base_tps * self.quant_multiplier(quant), 0.1)

    def batched_decode_tps(
        self,
        n1_tps: float,
        kv_per_seq_gb: float,
        batch: int,
        hardware: str | None = None,
        params_b: float | None = None,
        mbu: float = MBU_DEFAULT,
    ) -> float:
        """Aggregate decode tok/s for a continuous-batching backend at batch B.

        Anchored to the single-stream ``n1_tps`` (measured or roofline, so it stays
        quant-correct), then adds KV-amortization physics: at batch B the weights
        are read once per step but each of the B sequences reads its own KV, so

            aggregate(B) = B * bw*MBU / (weight_eff + B * kv_per_seq)

        where ``weight_eff = bw*MBU / n1_tps`` backs the effective weight bytes out
        of the calibrated single-stream rate. Rises ~linearly with B while weights
        dominate, then saturates at ``bw*MBU / kv_per_seq`` (KV-bandwidth bound).
        Capped by the decode compute ceiling. Returns ``n1_tps`` for batch <= 1.
        """
        if batch <= 1 or n1_tps <= 0:
            return max(n1_tps, 0.1)
        gpu = get_gpu(hardware) if hardware else None
        bandwidth = gpu.bandwidth_gbps if gpu else 556.0
        denom = bandwidth * mbu  # effective GB/s
        weight_eff_gb = denom / n1_tps
        agg = batch * denom / (weight_eff_gb + batch * kv_per_seq_gb)
        if params_b and gpu and gpu.fp16_tflops > 0:
            from chimeraforge.planner.constants import DECODE_COMPUTE_MFU

            compute_ceiling = gpu.fp16_tflops * 1e12 * DECODE_COMPUTE_MFU / (2 * params_b * 1e9)
            agg = min(agg, compute_ceiling)
        return max(agg, n1_tps)

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


# -- 3. Scaling Model --------------------------------------------------


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


# -- 4. Quality Model --------------------------------------------------


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

    def quality_tier(self, model: str, quant: str, family: str | None = None) -> str:
        """Classify quality drop into a tier.

        Family-aware, mirroring :meth:`estimate`: an off-registry model whose
        family matches the registry derives its FP16 baseline (and predicted
        quality) from the family mean, so the tier is consistent with the
        reported quality instead of silently collapsing to ``unknown``.
        """
        fp16 = self.fp16_baselines.get(model)
        if fp16 is None and f"{model}|FP16" in self.lookup:
            fp16 = self.lookup[f"{model}|FP16"]
        if fp16 is None and family is not None:
            same_family = [
                v for m, v in self.fp16_baselines.items() if MODEL_FAMILY.get(m) == family
            ]
            if same_family:
                fp16 = sum(same_family) / len(same_family)
        if fp16 is None or fp16 <= 0:
            return "unknown"
        # Predicted quality consistent with estimate(): direct lookup, else the
        # FP16 baseline (+ quant delta) -- not predict(), which is not family-aware.
        key = f"{model}|{quant}"
        if key in self.lookup:
            predicted = self.lookup[key]
        elif quant == "FP16":
            predicted = fp16
        else:
            predicted = max(0.0, min(1.0, fp16 + self.quant_deltas.get(quant, 0.0)))
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


# -- 5. Cost Model -----------------------------------------------------


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


# -- 6. Latency Model -------------------------------------------------


@dataclass
class LatencyModel:
    """Latency: prefill (TTFT) + decode (TPOT), with M/D/1 queueing on top."""

    service_times: dict[str, float] = field(default_factory=dict)
    safety_factor: float = 0.70
    fitted: bool = False

    @staticmethod
    def predict_ttft_ms(
        params_b: float,
        prompt_tokens: int,
        hardware: str | None = None,
        mfu: float = PREFILL_MFU,
    ) -> float:
        """Time-to-first-token = prefill compute time (compute-bound, ms).

        Prefill does ~2 FLOPs/param/token over the prompt; time = FLOPs /
        (peak_TFLOPS * MFU). Returns 0.0 when the GPU's compute is unknown (so the
        caller omits a prefill term rather than guessing). Decode/TPOT is modelled
        separately via throughput (bandwidth-bound).
        """
        gpu = get_gpu(hardware) if hardware else None
        tflops = gpu.fp16_tflops if gpu else 0.0
        if tflops <= 0 or params_b <= 0 or prompt_tokens <= 0:
            return 0.0
        flops = FLOPS_PER_PARAM_PER_TOKEN * params_b * 1e9 * prompt_tokens
        return flops / (tflops * 1e12 * mfu) * 1000.0

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
        ttft_ms: float = 0.0,
        concurrent_per_agent: int = 1,
        service_cv2: float = 0.0,
    ) -> dict:
        """Predict p95 latency and utilisation.

        ``n1_tps`` is the rate a *single request* decodes at (slower at high batch
        under contention), driving the in-service latency. ``concurrent_per_agent``
        is how many requests one GPU serves at once (the batch size for a
        continuous-batching backend; 1 for replicas), so system capacity is
        ``n_agents * concurrent_per_agent / service_time`` -- this decouples
        per-request latency from aggregate capacity. ``ttft_ms`` adds prefill, so
        service time is the full request: TTFT + avg_tokens * decode-per-token.
        """
        service_ms = None

        if n1_tps is not None and n1_tps > 0:
            service_ms = ttft_ms + avg_tokens / n1_tps * 1000
        elif throughput_model is not None:
            tps = throughput_model.predict(model, backend, quant, hardware)
            if tps > 0:
                service_ms = ttft_ms + avg_tokens / tps * 1000

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
        total_capacity = n_agents * concurrent_per_agent * mu * eta

        rho = request_rate / total_capacity if total_capacity > 0 else 1.0
        saturated = rho > self.safety_factor

        if rho < 1.0:
            # Two-moment (Allen-Cunneen) wait: (Ca^2 + Cs^2)/2 x M/M/1 wait, with
            # Poisson arrivals (Ca^2=1). Cs^2=0 -> (1+0)/2 = M/D/1 (the prior
            # behaviour); higher Cs^2 (agent/bursty) inflates the tail.
            mm1_wait_s = rho / (total_capacity * (1 - rho))
            mean_wait_s = (1.0 + service_cv2) / 2.0 * mm1_wait_s
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


# -- 7. Safety Model ---------------------------------------------------


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


# -- Aggregate model container -----------------------------------------


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


def load_effective_models(models_path: str | Path | None = None) -> PlannerModels:
    """Load the planner models, preferring measured data when available.

    Priority: an explicit ``models_path`` > the on-demand measured corpus
    (written by ``measure``) > the bundled data. This closes the empirical loop
    so a model benchmarked once is planned on real numbers thereafter, without
    re-passing ``--models-path``.
    """
    if models_path:
        return load_models(models_path)
    from chimeraforge.planner.resolver import measured_corpus_path

    corpus = measured_corpus_path()
    if corpus.is_file():
        try:
            with open(corpus, encoding="utf-8") as f:
                raw = json.load(f)
            # The corpus embeds a snapshot of the bundled coefficients it was
            # built on. Warn (don't silently shadow) if it predates the installed
            # package, so an upgrade's improved coefficients aren't masked for
            # models the user never re-measured. Re-run `measure` to refresh.
            from chimeraforge import __version__

            stamp = raw.get("_chimeraforge_version")
            if stamp and stamp != __version__:
                log.warning(
                    "measured corpus %s was written by chimeraforge %s (installed: %s); "
                    "re-run `measure` to pick up updated bundled coefficients",
                    corpus,
                    stamp,
                    __version__,
                )
            return load_models(corpus)
        except (ValueError, OSError) as exc:
            log.warning("ignoring unreadable measured corpus %s: %s", corpus, exc)
    return load_bundled_models()
