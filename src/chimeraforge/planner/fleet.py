"""Heterogeneous fleets: serve one workload on a mix of GPU types.

The planner has always sized N identical replicas of one GPU. That is a real
constraint on the answer, not just on the search: a cheap GPU can be the better
buy at loose SLOs and small requests while an expensive one wins at tight SLOs
and long requests, so the cheapest fleet for a given workload is often a *mix*
of both. Melange (arXiv:2404.14527) measured this across L4 / A10G / A100-80G /
H100 and reports up to 77% saved in conversational settings against the best
single GPU type, driven by three workload properties -- request size, request
rate, and SLO.

Two design choices here are deliberate.

**This sits on top of the gate search, not inside it.** Each GPU type is priced
by running the existing, validated `enumerate_candidates` pipeline against that
GPU alone. Every gate (VRAM, quality, safety, TTFT/TPOT, budget) and every piece
of serving physics (batching, KV ceiling, parallelism) therefore applies
unchanged, and a mixed fleet cannot become a back door around a check the
homogeneous path enforces.

**The allocation is exact; the inputs to it are not.** Given a per-GPU-type
sustainable rate, choosing the cheapest set of counts is integer arithmetic with
a provably optimal answer. But those rates are throughput predictions, and for
most GPUs in the database they are bandwidth-roofline *estimates* rather than
measured -- the bundled corpus is fit on one rig. Mixing multiplies that
exposure across types instead of concentrating it in one, so the reported
provenance is the WORST across the chosen types, never the best.

And the honest caveat that the source paper states about itself: it "leaves it
as future work to develop load balancers for serving LLMs on heterogeneous
GPUs". A mixed allocation presumes a router that splits traffic by GPU
capability. vLLM and SGLang do not ship one. That is an operational
prerequisite, not a detail, so every mixed plan says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.hardware import GPU_DB, get_gpu

# Ceiling on GPUs of a single type in one mix. Not a physical limit -- a guard so
# a badly-posed demand cannot spin the solver into an enormous allocation nobody
# would deploy. Reported when it binds rather than silently truncating.
MAX_UNITS_PER_TYPE = 64
# Ceiling on distinct GPU types in one mix. Every additional type is another
# distinct machine image, driver stack and routing tier to operate.
MAX_FLEET_TYPES = 6
# The rate search is a bisection on "does one GPU of this type still meet the
# SLO", which is monotone. This many steps resolves the rate to ~0.1% of range.
_BISECT_STEPS = 24
# Upper bound for that bisection, in requests/second on a single GPU. Far above
# any single-GPU rate the corpus supports; only there to bracket the search.
_MAX_SINGLE_GPU_RATE = 4096.0

PROVENANCE_ORDER = ("measured", "estimated", "unknown")


class FleetError(ValueError):
    """The requested fleet cannot be planned as specified."""


@dataclass(frozen=True)
class GpuOption:
    """What one GPU of a given type can sustain for this workload, and at what cost."""

    gpu: str
    # Requests/second a SINGLE GPU of this type sustains inside the latency SLO.
    rate_per_gpu: float
    cost_per_gpu_month: float
    quant: str
    backend: str
    quality: float
    vram_gb: float
    throughput_tps: float
    p95_latency_ms: float
    provenance: dict[str, str] = field(default_factory=dict)

    @property
    def cost_per_rate(self) -> float:
        """Monthly cost per sustained request/second -- the cost-efficiency metric."""
        if self.rate_per_gpu <= 0:
            return float("inf")
        return self.cost_per_gpu_month / self.rate_per_gpu

    def to_dict(self) -> dict:
        return {
            "gpu": self.gpu,
            "rate_per_gpu": round(self.rate_per_gpu, 4),
            "cost_per_gpu_month_usd": round(self.cost_per_gpu_month, 2),
            "cost_per_req_per_sec_usd": round(self.cost_per_rate, 2),
            "quant": self.quant,
            "backend": self.backend,
            "quality": self.quality,
            "vram_gb_per_gpu": self.vram_gb,
            "throughput_tps_per_gpu": round(self.throughput_tps, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "provenance": dict(self.provenance),
        }


@dataclass
class FleetPlan:
    """A chosen allocation of GPU counts across types."""

    units: dict[str, int]
    options: dict[str, GpuOption]
    demand_rate: float
    monthly_cost: float
    served_rate: float
    best_homogeneous: tuple[str, int, float] | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def gpus_total(self) -> int:
        return sum(self.units.values())

    @property
    def savings_vs_best_homogeneous(self) -> float:
        """Fraction saved against the cheapest single-type fleet, 0.0 if none/worse."""
        if not self.best_homogeneous:
            return 0.0
        best_cost = self.best_homogeneous[2]
        if best_cost <= 0:
            return 0.0
        return max((best_cost - self.monthly_cost) / best_cost, 0.0)

    @property
    def is_mixed(self) -> bool:
        return len([n for n in self.units.values() if n > 0]) > 1

    def provenance(self) -> dict[str, str]:
        """Worst provenance across the GPU types actually used.

        A mix is only as trustworthy as its least-grounded member, and reporting
        the best would let one measured GPU launder several estimated ones.
        """
        used = [self.options[g] for g, n in self.units.items() if n > 0]
        out: dict[str, str] = {}
        for key in ("vram", "throughput", "quality"):
            ranks = [PROVENANCE_ORDER.index(o.provenance.get(key, "unknown")) for o in used]
            out[key] = PROVENANCE_ORDER[max(ranks)] if ranks else "unknown"
        return out

    def to_dict(self) -> dict:
        return {
            "units": {g: n for g, n in self.units.items() if n > 0},
            "gpus_total": self.gpus_total,
            "demand_rate": round(self.demand_rate, 4),
            "served_rate": round(self.served_rate, 4),
            "monthly_cost_usd": round(self.monthly_cost, 2),
            "mixed": self.is_mixed,
            "best_homogeneous": (
                {
                    "gpu": self.best_homogeneous[0],
                    "units": self.best_homogeneous[1],
                    "monthly_cost_usd": round(self.best_homogeneous[2], 2),
                }
                if self.best_homogeneous
                else None
            ),
            "savings_vs_best_homogeneous": round(self.savings_vs_best_homogeneous, 4),
            "per_gpu": [self.options[g].to_dict() for g, n in self.units.items() if n > 0],
            "provenance": self.provenance(),
            "warnings": list(self.warnings),
        }


def parse_fleet(spec: str) -> list[str]:
    """Resolve a comma-separated GPU list to canonical database names."""
    raw = [s.strip() for s in spec.split(",") if s.strip()]
    if not raw:
        raise FleetError("--fleet needs at least one GPU name")
    resolved: list[str] = []
    for name in raw:
        gpu = get_gpu(name)
        if gpu is None:
            known = ", ".join(list(GPU_DB)[:6])
            raise FleetError(f"unknown GPU {name!r} in --fleet (known GPUs include: {known}, ...)")
        if gpu.name not in resolved:
            resolved.append(gpu.name)
    if len(resolved) > MAX_FLEET_TYPES:
        raise FleetError(
            f"--fleet lists {len(resolved)} GPU types; the cap is {MAX_FLEET_TYPES}. "
            "Each additional type is another image, driver stack and routing tier."
        )
    return resolved


def single_gpu_capacity(
    gpu: str,
    *,
    plan_fn,
    plan_kwargs: dict,
) -> GpuOption | None:
    """Highest request rate ONE GPU of this type sustains inside the SLO.

    Bisects on the request rate, asking the ordinary planner each time whether a
    single-GPU config still clears every gate. Feasibility is monotone in the
    rate -- a GPU that fails at r fails at every rate above it -- so bisection
    finds the exact boundary rather than sampling near it.

    Returns None when even a vanishingly small rate cannot be served, which is
    the honest answer for a GPU the model does not fit on.
    """

    def feasible(rate: float) -> Candidate | None:
        kwargs = dict(plan_kwargs, hardware=gpu, request_rate=rate)
        try:
            result = plan_fn(**kwargs)
        except (ValueError, RuntimeError):
            return None
        for cand in result.candidates:
            # One GPU only: the mix supplies scale-out, so a candidate that
            # already needs replicas is not a per-unit capacity measurement.
            if (cand.gpus_total or cand.n_agents) == 1:
                return cand
        return None

    # A rate of zero is meaningless, so probe the smallest rate the planner will
    # take. If nothing is feasible there, nothing is feasible at all.
    lo_rate = 1e-3
    base = feasible(lo_rate)
    if base is None:
        return None

    hi = _MAX_SINGLE_GPU_RATE
    if feasible(hi) is not None:
        # Saturates the bracket: report the bracket rather than extrapolating past
        # a rate the search never actually tested.
        best_rate, best = hi, feasible(hi)
    else:
        lo = lo_rate
        best, best_rate = base, lo_rate
        for _ in range(_BISECT_STEPS):
            mid = (lo + hi) / 2.0
            cand = feasible(mid)
            if cand is not None:
                lo, best, best_rate = mid, cand, mid
            else:
                hi = mid

    assert best is not None
    return GpuOption(
        gpu=gpu,
        rate_per_gpu=best_rate,
        cost_per_gpu_month=best.monthly_cost,
        quant=best.quant,
        backend=best.backend,
        quality=best.quality,
        vram_gb=best.vram_gb,
        throughput_tps=best.throughput_tps,
        p95_latency_ms=best.p95_latency_ms,
        provenance=dict(best.provenance or {}),
    )


def solve_mix(options: list[GpuOption], demand_rate: float) -> dict[str, int] | None:
    """Cheapest GPU counts whose combined rate covers the demand.

    This is the Melange bin-packing objective -- minimise sum(count * cost)
    subject to sum(count * rate) >= demand -- solved exactly rather than
    greedily. A greedy pass on cost-per-rate is wrong at the boundary: the last
    increment of demand is often cheaper to cover with one small GPU than with
    another large one, which is precisely where a mix beats a single type.

    Discretising demand into fixed steps makes this an integer cover problem
    solvable by dynamic programming, and the step is chosen from the smallest
    per-GPU rate so no option is rounded out of existence.
    """
    usable = [o for o in options if o.rate_per_gpu > 0 and o.cost_per_gpu_month >= 0]
    if not usable or demand_rate <= 0:
        return None

    # Resolution: 1/200th of the smallest unit of capacity, so the cheapest GPU
    # is never quantised away, bounded so the table stays small.
    smallest = min(o.rate_per_gpu for o in usable)
    step = max(smallest / 200.0, demand_rate / 20000.0)
    # Float floor-division under-counts: 100.0 // 0.05 is 1999, not 2000, because
    # 0.05 has no exact binary representation. Left alone that shaves a step off
    # every GPU's capacity, which forces a spurious extra unit and quietly inflates
    # the bill. The epsilon absorbs representation error without over-claiming any
    # capacity that is actually there.
    eps = 1e-9
    need = int(math.ceil(demand_rate / step - eps))

    # Unbounded-knapsack cover: cheapest cost to cover >= k steps.
    inf = float("inf")
    cost = [inf] * (need + 1)
    choice: list[tuple[str, int] | None] = [None] * (need + 1)
    cost[0] = 0.0
    for k in range(1, need + 1):
        for opt in usable:
            units = int(opt.rate_per_gpu / step + eps)
            if units <= 0:
                continue
            prev = max(k - units, 0)
            cand = cost[prev] + opt.cost_per_gpu_month
            if cand < cost[k]:
                cost[k] = cand
                choice[k] = (opt.gpu, prev)
    if cost[need] == inf:
        return None

    units: dict[str, int] = {o.gpu: 0 for o in usable}
    k = need
    guard = 0
    while k > 0 and choice[k] is not None:
        gpu, prev = choice[k]
        units[gpu] += 1
        k = prev
        guard += 1
        if guard > MAX_UNITS_PER_TYPE * len(usable):
            return None
    if any(n > MAX_UNITS_PER_TYPE for n in units.values()):
        return None
    return units


def plan_fleet(
    gpus: list[str],
    *,
    demand_rate: float,
    plan_fn,
    plan_kwargs: dict,
) -> FleetPlan:
    """Price each GPU type, then choose the cheapest mix that covers the demand."""
    if demand_rate <= 0:
        raise FleetError("request rate must be greater than zero to size a fleet")

    options: dict[str, GpuOption] = {}
    infeasible: list[str] = []
    for gpu in gpus:
        opt = single_gpu_capacity(gpu, plan_fn=plan_fn, plan_kwargs=plan_kwargs)
        if opt is None:
            infeasible.append(gpu)
        else:
            options[gpu] = opt
    if not options:
        raise FleetError(
            "no GPU in the fleet can serve this workload at all: "
            f"{', '.join(infeasible)}. Run `chimeraforge plan` against one of them "
            "to see which gate rejects it."
        )

    units = solve_mix(list(options.values()), demand_rate)
    if units is None:
        raise FleetError(
            f"no allocation within {MAX_UNITS_PER_TYPE} GPUs per type covers "
            f"{demand_rate} req/s. Raise the latency SLO, lower the rate, or add a "
            "larger GPU to the fleet."
        )

    monthly = sum(options[g].cost_per_gpu_month * n for g, n in units.items())
    served = sum(options[g].rate_per_gpu * n for g, n in units.items())

    # The comparison that matters is against the best SINGLE type, not an
    # arbitrary one -- quoting savings against a badly-chosen baseline would
    # inflate the number the same way a vendor benchmark does.
    best_homo: tuple[str, int, float] | None = None
    for gpu, opt in options.items():
        n = int(math.ceil(demand_rate / opt.rate_per_gpu - 1e-9))
        if n > MAX_UNITS_PER_TYPE:
            continue
        total = opt.cost_per_gpu_month * n
        if best_homo is None or total < best_homo[2]:
            best_homo = (gpu, n, total)

    plan = FleetPlan(
        units=units,
        options=options,
        demand_rate=demand_rate,
        monthly_cost=monthly,
        served_rate=served,
        best_homogeneous=best_homo,
    )

    if plan.is_mixed:
        plan.warnings.append(
            "a mixed fleet needs a router that splits traffic by GPU capability. "
            "vLLM and SGLang do not ship one, and the source study "
            "(Melange, arXiv:2404.14527) explicitly leaves heterogeneous load "
            "balancing as future work -- treat this as an operational prerequisite, "
            "not a detail"
        )
    prov = plan.provenance()
    if prov.get("throughput") != "measured":
        used = [g for g, n in units.items() if n > 0]
        plan.warnings.append(
            f"per-GPU rates for {', '.join(used)} are {prov['throughput']}, not "
            "measured: a mix compounds throughput error across types instead of "
            "concentrating it in one. Run `chimeraforge measure` on each before "
            "committing spend"
        )
    if infeasible:
        plan.warnings.append(
            f"excluded from the mix (cannot serve this workload at all): {', '.join(infeasible)}"
        )
    if served > demand_rate * 1.5:
        plan.warnings.append(
            f"the cheapest covering mix overshoots demand ({served:.2f} vs "
            f"{demand_rate:.2f} req/s) because GPUs are indivisible; you are paying "
            "for that headroom whether or not you use it"
        )
    return plan
