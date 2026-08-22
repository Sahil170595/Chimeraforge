"""Tests for heterogeneous fleets (`plan --fleet`).

The allocation itself is integer arithmetic with a provably optimal answer, so
it is tested against hand-computed optima rather than against itself: a solver
checked only for self-consistency will happily agree with its own bug.

The rest of the surface is honesty. A mixed fleet presumes a capability-aware
router that no serving engine ships -- Melange (arXiv:2404.14527), the study
this is built on, says so about itself -- and its per-GPU rates are throughput
predictions that a mix compounds across types rather than concentrating in one.
Both must be stated on every mixed plan, and the reported provenance must be the
worst of the types used, never the best.
"""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.fleet import (
    MAX_FLEET_TYPES,
    MAX_UNITS_PER_TYPE,
    FleetError,
    FleetPlan,
    GpuOption,
    parse_fleet,
    plan_fleet,
    single_gpu_capacity,
    solve_mix,
)
from chimeraforge.planner.service import run_plan

# Synthetic options with round numbers, so every expected allocation below can be
# worked out by hand and the solver has nothing to hide behind.
BIG = GpuOption(
    gpu="big",
    rate_per_gpu=100.0,
    cost_per_gpu_month=1000.0,
    quant="FP16",
    backend="vllm",
    quality=0.8,
    vram_gb=40.0,
    throughput_tps=1000.0,
    p95_latency_ms=500.0,
    provenance={"vram": "measured", "throughput": "measured", "quality": "measured"},
)
SMALL = GpuOption(
    gpu="small",
    rate_per_gpu=10.0,
    cost_per_gpu_month=200.0,
    quant="FP16",
    backend="vllm",
    quality=0.8,
    vram_gb=16.0,
    throughput_tps=100.0,
    p95_latency_ms=900.0,
    provenance={"vram": "measured", "throughput": "estimated", "quality": "unknown"},
)


def _plan_kwargs(**over) -> dict:
    kw = dict(
        model_size="8b",
        latency_slo=5000.0,
        quality_target=0.0,
        budget=1e9,
        avg_tokens=128,
        context_length=2048,
    )
    kw.update(over)
    return kw


class TestSolverOptimality:
    def test_single_type_when_it_is_cheapest(self):
        # 100 req/s: one BIG at $1000 beats ten SMALL at $2000.
        assert solve_mix([BIG, SMALL], 100.0) == {"big": 1, "small": 0}

    def test_mixes_when_the_remainder_is_cheaper_on_a_small_gpu(self):
        """The whole point of the feature. At 105 req/s a second BIG costs $1000
        for 100 unused req/s, while one SMALL covers the remainder for $200."""
        assert solve_mix([BIG, SMALL], 105.0) == {"big": 1, "small": 1}

    def test_beats_greedy_cost_per_rate(self):
        """BIG is better per req/s ($10 vs $20), so a greedy pass takes two BIG at
        $2000. The optimum is one BIG plus one SMALL at $1200."""
        units = solve_mix([BIG, SMALL], 101.0)
        cost = units["big"] * BIG.cost_per_gpu_month + units["small"] * SMALL.cost_per_gpu_month
        assert cost == pytest.approx(1200.0, rel=0.02)
        assert cost < 2 * BIG.cost_per_gpu_month

    def test_covers_the_demand(self):
        for demand in (5.0, 55.0, 100.0, 137.0, 260.0):
            units = solve_mix([BIG, SMALL], demand)
            served = units["big"] * BIG.rate_per_gpu + units["small"] * SMALL.rate_per_gpu
            assert served >= demand * 0.999, f"under-served at {demand}"

    def test_never_cheaper_than_the_true_optimum(self):
        """Brute-force the small search space and require the solver to match."""
        for demand in (17.0, 63.0, 128.0, 205.0):
            units = solve_mix([BIG, SMALL], demand)
            got = units["big"] * 1000.0 + units["small"] * 200.0
            best = min(
                b * 1000.0 + s * 200.0
                for b in range(0, 5)
                for s in range(0, 40)
                if b * 100.0 + s * 10.0 >= demand
            )
            assert got == pytest.approx(best, rel=0.05), f"suboptimal at {demand}"

    def test_zero_demand_has_no_solution(self):
        assert solve_mix([BIG, SMALL], 0.0) is None

    def test_no_usable_options(self):
        dead = GpuOption(
            gpu="dead",
            rate_per_gpu=0.0,
            cost_per_gpu_month=10.0,
            quant="FP16",
            backend="vllm",
            quality=0.5,
            vram_gb=1.0,
            throughput_tps=0.0,
            p95_latency_ms=1.0,
        )
        assert solve_mix([dead], 10.0) is None

    def test_capacity_is_not_shaved_by_float_division(self):
        """`100.0 // 0.05` is 1999, not 2000. Floor-dividing on floats loses a step
        of every GPU's capacity, which forces a spurious extra unit and quietly
        inflates the bill -- a wrong answer that looks entirely reasonable."""
        # Exactly one BIG covers exactly 100 req/s. Any capacity shaving shows up
        # here as a second GPU nobody needs.
        assert solve_mix([BIG, SMALL], 100.0) == {"big": 1, "small": 0}
        assert solve_mix([SMALL], 10.0) == {"small": 1}
        assert solve_mix([SMALL], 50.0) == {"small": 5}

    def test_refuses_rather_than_truncating_past_the_unit_cap(self):
        # A demand needing more than the cap must return None, not a short answer
        # that silently under-serves.
        assert solve_mix([SMALL], SMALL.rate_per_gpu * (MAX_UNITS_PER_TYPE + 5)) is None


class TestParseFleet:
    def test_resolves_and_canonicalises(self):
        assert parse_fleet("4090, h100 80gb") == ["RTX 4090 24GB", "H100 80GB"]

    def test_deduplicates(self):
        assert parse_fleet("H100 80GB,H100 80GB") == ["H100 80GB"]

    def test_unknown_gpu_is_actionable(self):
        with pytest.raises(FleetError, match="unknown GPU"):
            parse_fleet("H100 80GB,RTX 9999")

    def test_empty_is_refused(self):
        with pytest.raises(FleetError, match="at least one"):
            parse_fleet("  , ")

    def test_too_many_types_is_refused(self):
        names = ",".join(
            [
                "H100 80GB",
                "A100 80GB",
                "A100 40GB",
                "L4 24GB",
                "T4 16GB",
                "RTX 4090 24GB",
                "RTX 3090 24GB",
            ]
        )
        with pytest.raises(FleetError, match=str(MAX_FLEET_TYPES)):
            parse_fleet(names)


class TestCapacityProbe:
    def test_finds_a_positive_rate_for_a_capable_gpu(self):
        opt = single_gpu_capacity("H100 80GB", plan_fn=run_plan, plan_kwargs=_plan_kwargs())
        assert opt is not None
        assert opt.rate_per_gpu > 0
        assert opt.cost_per_gpu_month > 0

    def test_capacity_is_a_single_gpu_not_a_fleet(self):
        """If the probe let a multi-GPU candidate through, every per-unit rate
        would be inflated and the whole allocation would under-provision."""
        opt = single_gpu_capacity("H100 80GB", plan_fn=run_plan, plan_kwargs=_plan_kwargs())
        one_gpu_cost = (
            run_plan(**_plan_kwargs(), hardware="H100 80GB", request_rate=0.1)
            .candidates[0]
            .monthly_cost
        )
        assert opt.cost_per_gpu_month == pytest.approx(one_gpu_cost, rel=1e-6)

    def test_bigger_gpu_sustains_more(self):
        big = single_gpu_capacity("H100 80GB", plan_fn=run_plan, plan_kwargs=_plan_kwargs())
        small = single_gpu_capacity("L4 24GB", plan_fn=run_plan, plan_kwargs=_plan_kwargs())
        assert big.rate_per_gpu > small.rate_per_gpu

    def test_infeasible_gpu_returns_none_rather_than_a_guess(self):
        # A 70B at FP16 does not fit an 8GB card at any rate.
        opt = single_gpu_capacity(
            "RTX 4060 8GB",
            plan_fn=run_plan,
            plan_kwargs=_plan_kwargs(
                models=["meta-llama/Llama-3.1-70B"],
                allow_network=False,
                overrides={
                    "params_b": 70.0,
                    "n_layers": 80,
                    "n_kv_heads": 8,
                    "d_head": 128,
                },
            ),
        )
        assert opt is None

    def test_tighter_slo_lowers_the_sustainable_rate(self):
        loose = single_gpu_capacity(
            "H100 80GB", plan_fn=run_plan, plan_kwargs=_plan_kwargs(latency_slo=10000.0)
        )
        tight = single_gpu_capacity(
            "H100 80GB", plan_fn=run_plan, plan_kwargs=_plan_kwargs(latency_slo=1500.0)
        )
        assert tight.rate_per_gpu < loose.rate_per_gpu


class TestPlanFleet:
    @pytest.fixture(scope="class")
    def mixed(self):
        return plan_fleet(
            ["H100 80GB", "A100 80GB", "L4 24GB"],
            demand_rate=64.0,
            plan_fn=run_plan,
            plan_kwargs=_plan_kwargs(),
        )

    def test_produces_a_mix_at_the_boundary(self, mixed):
        assert mixed.is_mixed
        assert mixed.gpus_total >= 2

    def test_beats_the_best_single_type(self, mixed):
        assert mixed.best_homogeneous is not None
        assert mixed.monthly_cost < mixed.best_homogeneous[2]
        assert mixed.savings_vs_best_homogeneous > 0

    def test_savings_are_measured_against_the_BEST_single_type(self):
        """Quoting savings against a badly-chosen baseline inflates the number the
        same way a vendor benchmark does."""
        p = plan_fleet(
            ["H100 80GB", "A100 80GB", "L4 24GB"],
            demand_rate=64.0,
            plan_fn=run_plan,
            plan_kwargs=_plan_kwargs(),
        )
        cheapest_single = min(
            o.cost_per_gpu_month * int(-(-p.demand_rate // o.rate_per_gpu))
            for o in p.options.values()
        )
        assert p.best_homogeneous[2] == pytest.approx(cheapest_single, rel=1e-6)

    def test_covers_demand(self, mixed):
        assert mixed.served_rate >= mixed.demand_rate

    def test_homogeneous_when_that_is_optimal(self):
        # Low demand: one big GPU covers it, and the plan must say so rather than
        # manufacturing a mix to justify the flag.
        p = plan_fleet(
            ["H100 80GB", "A100 80GB", "L4 24GB"],
            demand_rate=5.0,
            plan_fn=run_plan,
            plan_kwargs=_plan_kwargs(),
        )
        assert not p.is_mixed
        assert p.savings_vs_best_homogeneous == 0.0

    def test_router_warning_on_every_mixed_plan(self, mixed):
        joined = " ".join(mixed.warnings)
        assert "router" in joined
        assert "2404.14527" in joined, "the warning must cite the study it comes from"

    def test_no_router_warning_when_not_mixed(self):
        p = plan_fleet(["H100 80GB"], demand_rate=5.0, plan_fn=run_plan, plan_kwargs=_plan_kwargs())
        assert not any("router" in w for w in p.warnings)

    def test_provenance_is_the_worst_across_types_used(self):
        p = FleetPlan(
            units={"big": 1, "small": 1},
            options={"big": BIG, "small": SMALL},
            demand_rate=110.0,
            monthly_cost=1200.0,
            served_rate=110.0,
        )
        prov = p.provenance()
        # BIG is measured throughout; SMALL is estimated/unknown. The mix inherits
        # SMALL's, so one measured GPU cannot launder the others.
        assert prov["throughput"] == "estimated"
        assert prov["quality"] == "unknown"
        assert prov["vram"] == "measured"

    def test_provenance_ignores_types_not_used(self):
        p = FleetPlan(
            units={"big": 1, "small": 0},
            options={"big": BIG, "small": SMALL},
            demand_rate=100.0,
            monthly_cost=1000.0,
            served_rate=100.0,
        )
        assert p.provenance()["quality"] == "measured"

    def test_estimated_rates_are_warned_about(self, mixed):
        assert any("not\nmeasured" in w or "not measured" in w for w in mixed.warnings)

    def test_overshoot_is_disclosed(self):
        # GPUs are indivisible, so a small demand against a big GPU overpays. The
        # user is paying for that headroom and should be told.
        p = plan_fleet(["H100 80GB"], demand_rate=1.0, plan_fn=run_plan, plan_kwargs=_plan_kwargs())
        assert any("overshoot" in w for w in p.warnings)

    def test_zero_rate_is_refused(self):
        with pytest.raises(FleetError, match="greater than zero"):
            plan_fleet(["H100 80GB"], demand_rate=0.0, plan_fn=run_plan, plan_kwargs=_plan_kwargs())

    def test_all_infeasible_is_actionable(self):
        with pytest.raises(FleetError, match="can serve this workload at all"):
            plan_fleet(
                ["RTX 4060 8GB"],
                demand_rate=5.0,
                plan_fn=run_plan,
                plan_kwargs=_plan_kwargs(
                    models=["big/model"],
                    allow_network=False,
                    overrides={
                        "params_b": 405.0,
                        "n_layers": 126,
                        "n_kv_heads": 8,
                        "d_head": 128,
                    },
                ),
            )

    def test_partially_infeasible_types_are_excluded_and_named(self):
        p = plan_fleet(
            ["H100 80GB", "RTX 4060 8GB"],
            demand_rate=5.0,
            plan_fn=run_plan,
            plan_kwargs=_plan_kwargs(
                models=["mid/model"],
                allow_network=False,
                overrides={
                    "params_b": 32.0,
                    "n_layers": 64,
                    "n_kv_heads": 8,
                    "d_head": 128,
                    "hidden_size": 5120,
                },
            ),
        )
        assert "RTX 4060 8GB" not in [g for g, n in p.units.items() if n]
        assert any("excluded" in w and "RTX 4060 8GB" in w for w in p.warnings)

    def test_to_dict_is_serializable_and_complete(self, mixed):
        d = mixed.to_dict()
        assert json.loads(json.dumps(d))
        assert set(d) >= {
            "units",
            "gpus_total",
            "monthly_cost_usd",
            "mixed",
            "best_homogeneous",
            "savings_vs_best_homogeneous",
            "per_gpu",
            "provenance",
            "warnings",
        }
        assert all(n > 0 for n in d["units"].values()), "zero-count types must not be listed"


class TestPlanCliFleet:
    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["plan", "--model-size", "8b", *args])

    def test_human_output(self):
        r = self._run(
            "--fleet",
            "H100 80GB,A100 80GB,L4 24GB",
            "--request-rate",
            "64",
            "--budget",
            "1e9",
            "--quality-target",
            "0",
        )
        assert r.exit_code == 0, r.output
        assert "Heterogeneous fleet" in r.output

    def test_json_contract_unchanged_without_the_flag(self):
        r = self._run("--json")
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert isinstance(data, list)

    def test_json_wraps_only_under_the_flag(self):
        r = self._run(
            "--fleet",
            "H100 80GB,L4 24GB",
            "--request-rate",
            "64",
            "--budget",
            "1e9",
            "--quality-target",
            "0",
            "--json",
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output[r.output.index("{") : r.output.rindex("}") + 1])
        assert set(data) == {"candidates", "fleet"}
        assert data["fleet"]["units"]

    def test_unknown_gpu_exits_cleanly(self):
        r = self._run("--fleet", "H100 80GB,RTX 9999", "--request-rate", "10")
        assert r.exit_code == 1
        assert "Traceback" not in r.output
        assert "unknown GPU" in r.output

    def test_no_flag_does_not_run_the_fleet_search(self):
        r = self._run("--request-rate", "2", "--budget", "5000")
        assert r.exit_code == 0
        assert "Heterogeneous fleet" not in r.output
