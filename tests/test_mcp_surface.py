"""Tests for the widened MCP surface: compare-api, suggest, and plan flag parity.

Two failure modes are guarded here. First, an assistant asking "self-host or API"
gets a *dated* price snapshot, so the tool must report the age and flag staleness
rather than let a model quote a nine-month-old price as current. Second, the MCP
plan tool must not silently expose a narrower model than the CLI -- a flag missing
here is a question an assistant simply cannot ask, with no error to reveal it.
"""

from __future__ import annotations

import inspect

import pytest

from chimeraforge.mcp_server import (
    _SUGGEST_SOURCES,
    compare_self_host_vs_api,
    plan_deployment,
    suggest_models,
)
from chimeraforge.planner.constants import WORKLOAD_CV2
from chimeraforge.planner.resolver import ModelSpec
from chimeraforge.planner.service import run_plan


@pytest.fixture
def fake_catalog(monkeypatch):
    """Two real-shaped specs, so suggest tests never depend on a built local cache."""
    specs = {
        "Qwen/Qwen2.5-1.5B-Instruct": ModelSpec(
            name="Qwen/Qwen2.5-1.5B-Instruct",
            params_b=1.54,
            n_layers=28,
            n_kv_heads=2,
            d_head=128,
            source="hf",
        ),
        "Qwen/Qwen2.5-7B-Instruct": ModelSpec(
            name="Qwen/Qwen2.5-7B-Instruct",
            params_b=7.62,
            n_layers=28,
            n_kv_heads=4,
            d_head=128,
            source="hf",
        ),
    }
    monkeypatch.setattr("chimeraforge.planner.discovery.load_catalog", lambda: dict(specs))
    return specs


class TestCompareApi:
    def test_prices_a_feasible_plan(self):
        r = compare_self_host_vs_api(hardware="RTX 4090 24GB", model_size="8b", request_rate=5.0)
        assert r["ok"] and r["comparable"]
        assert r["self_host"]["monthly_cost_usd"] > 0
        assert r["api_comparison"]["options"]

    def test_break_even_direction_is_right(self):
        """Low volume favours the API; high volume favours the GPU.

        If this inverts, the tool is confidently recommending the wrong side of a
        spend decision.
        """
        low = compare_self_host_vs_api(hardware="RTX 4090 24GB", model_size="8b", request_rate=0.01)
        high = compare_self_host_vs_api(hardware="RTX 4090 24GB", model_size="8b", request_rate=5.0)
        assert low["api_options_cheaper_than_self_host"] > 0
        assert high["api_options_cheaper_than_self_host"] == 0

    def test_self_host_cost_is_volume_independent(self):
        # A rented GPU costs the same whether it is busy or idle; only the API bill
        # scales with traffic. If the self-host figure moved with request_rate the
        # break-even point would be meaningless.
        a = compare_self_host_vs_api(hardware="RTX 4090 24GB", model_size="8b", request_rate=0.1)
        b = compare_self_host_vs_api(hardware="RTX 4090 24GB", model_size="8b", request_rate=0.5)
        assert (
            a["api_comparison"]["self_host_monthly_usd"]
            == b["api_comparison"]["self_host_monthly_usd"]
        )
        assert (
            b["api_comparison"]["options"][0]["monthly_cost_usd"]
            > a["api_comparison"]["options"][0]["monthly_cost_usd"]
        )

    def test_snapshot_age_is_always_reported(self):
        r = compare_self_host_vs_api(hardware="RTX 4090 24GB", model_size="8b")
        cmp_block = r["api_comparison"]
        assert "prices_captured_at" in cmp_block and "prices_age_days" in cmp_block
        assert isinstance(cmp_block["prices_stale"], bool)
        assert "days old" in r["note"]

    def test_stale_snapshot_says_so_in_the_note(self, monkeypatch):
        # The note is what an assistant reads back to a user, so staleness has to be
        # in the prose, not only in a boolean the model may ignore.
        import chimeraforge.planner.apicost as apicost

        pricing = dict(apicost.load_pricing())
        pricing["captured_at"] = "2020-01-01"
        monkeypatch.setattr(apicost, "load_pricing", lambda: pricing)
        r = compare_self_host_vs_api(hardware="RTX 4090 24GB", model_size="8b")
        assert r["api_comparison"]["prices_stale"] is True
        assert "STALE" in r["note"]

    def test_duty_cycle_scales_the_api_bill(self):
        full = compare_self_host_vs_api(
            hardware="RTX 4090 24GB", model_size="8b", request_rate=1.0, duty_cycle=1.0
        )
        half = compare_self_host_vs_api(
            hardware="RTX 4090 24GB", model_size="8b", request_rate=1.0, duty_cycle=0.5
        )
        assert half["api_comparison"]["requests_per_month"] == pytest.approx(
            full["api_comparison"]["requests_per_month"] / 2, rel=1e-6
        )

    def test_reasoning_tokens_are_billed_as_output(self):
        # Hidden reasoning tokens are billed at the output rate; omitting them
        # understates the API side and makes self-hosting look worse than it is.
        plain = compare_self_host_vs_api(
            hardware="RTX 4090 24GB", model_size="8b", avg_output_tokens=128
        )
        thinking = compare_self_host_vs_api(
            hardware="RTX 4090 24GB",
            model_size="8b",
            avg_output_tokens=128,
            reasoning_tokens=512,
        )
        assert thinking["api_comparison"]["output_tokens"] == 640
        assert (
            thinking["api_comparison"]["options"][0]["monthly_cost_usd"]
            > plain["api_comparison"]["options"][0]["monthly_cost_usd"]
        )

    def test_infeasible_plan_is_not_reported_as_an_api_win(self):
        # If nothing fits, there is no self-host cost. Returning "the API is cheaper"
        # would answer a question nobody asked.
        r = compare_self_host_vs_api(hardware="T4 16GB", model_size="8b", request_rate=1e6)
        assert r["ok"] and r["comparable"] is False
        assert r["why_nothing_fit"]

    def test_unknown_gpu_propagates_the_plan_error(self):
        r = compare_self_host_vs_api(hardware="RTX 9999 imaginary")
        assert r["ok"] is False and "unknown GPU" in r["error"]


class TestSuggest:
    def test_ranks_catalog_models(self, fake_catalog):
        r = suggest_models(hardware="RTX 4090 24GB", source="catalog", budget_usd_month=1e9)
        assert r["ok"]
        assert r["considered"] == len(fake_catalog)
        assert r["models"]
        assert {m["model"] for m in r["models"]} <= set(fake_catalog)

    def test_one_config_per_model(self, fake_catalog):
        r = suggest_models(hardware="RTX 4090 24GB", source="catalog", budget_usd_month=1e9)
        names = [m["model"] for m in r["models"]]
        assert len(names) == len(set(names))

    def test_limit_is_honoured(self, fake_catalog):
        r = suggest_models(
            hardware="RTX 4090 24GB", source="catalog", budget_usd_month=1e9, limit=1
        )
        assert len(r["models"]) == 1

    def test_smaller_gpu_fits_no_more_models(self, fake_catalog):
        big = suggest_models(hardware="RTX 4090 24GB", source="catalog", budget_usd_month=1e9)
        small = suggest_models(hardware="RTX 4060 8GB", source="catalog", budget_usd_month=1e9)
        assert small["fitting"] <= big["fitting"]

    def test_provenance_travels_with_each_suggestion(self, fake_catalog):
        r = suggest_models(hardware="RTX 4090 24GB", source="catalog", budget_usd_month=1e9)
        for m in r["models"]:
            assert set(m["provenance"]) >= {"vram", "throughput", "quality"}

    def test_empty_catalog_explains_the_fix(self, monkeypatch):
        monkeypatch.setattr("chimeraforge.planner.discovery.load_catalog", dict)
        r = suggest_models(hardware="RTX 4090 24GB", source="catalog")
        assert r["ok"] and r["models"] == []
        # `chimeraforge catalog build` exits 2 -- the flag is `--build`. This
        # string is handed to an LLM through the MCP tool description, and is the
        # only recovery instruction given when the catalog is empty.
        assert "catalog --build" in r["hint"]

    def test_unknown_source_is_actionable(self):
        r = suggest_models(hardware="RTX 4090 24GB", source="pypi")
        assert r["ok"] is False
        assert "pypi" in r["error"] and "hint" in r

    def test_unknown_gpu_is_actionable(self):
        r = suggest_models(hardware="RTX 9999 imaginary", source="catalog")
        assert r["ok"] is False and "list_hardware" in r["hint"]

    def test_source_set_matches_the_cli(self):
        assert _SUGGEST_SOURCES == {"ollama", "hf", "catalog"}

    def test_offline_source_makes_no_network_call(self, fake_catalog, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("catalog source must not hit the network")

        monkeypatch.setattr("chimeraforge.planner.discovery.discover_identifiers", boom)
        assert suggest_models(hardware="RTX 4090 24GB", source="catalog")["ok"]


class TestPlanFlagParity:
    """The MCP plan tool should not expose a narrower model than the CLI does."""

    @pytest.mark.parametrize(
        "flag",
        [
            "workload",
            "safety_target",
            "gpu_price_multiplier",
            "allow_offload",
            "host_bandwidth_gbps",
            "reasoning_tokens",
            "prefix_cache_hit_rate",
            "duty_cycle",
            "ttft_slo_ms",
            "tpot_slo_ms",
            "kv_quant",
            "tensor_parallel",
            "pipeline_parallel",
        ],
    )
    def test_modelling_knob_is_reachable(self, flag):
        assert flag in inspect.signature(plan_deployment).parameters

    def test_no_run_plan_knob_is_silently_unreachable(self):
        """A knob run_plan models but the tool cannot pass is invisible to an
        assistant -- it fails as a missing capability, never as an error."""
        exposed = set(inspect.signature(plan_deployment).parameters)
        # Renamed at the boundary (units in the name) or deliberately CLI-only.
        aliased = {
            "latency_slo": "latency_slo_ms",
            "avg_tokens": "avg_output_tokens",
            "budget": "budget_usd_month",
            "ttft_slo": "ttft_slo_ms",
            "tpot_slo": "tpot_slo_ms",
            "models": "model",
            "workload_cv2": "workload",
        }
        cli_only = {
            "models_path",  # local corpus override: a server-side file path
            "overrides",  # manual arch overrides: better served by resolve_model
            "pareto",  # a presentation mode; the tool always returns alternatives
            "electricity_rate",
            "hf_token",  # a secret does not belong in a tool argument
            "ollama_url",
        }
        missing = {
            p
            for p in inspect.signature(run_plan).parameters
            if p not in exposed and aliased.get(p) not in exposed and p not in cli_only
        }
        assert not missing, f"run_plan knobs unreachable from the MCP tool: {sorted(missing)}"

    @pytest.mark.parametrize("workload", sorted(WORKLOAD_CV2))
    def test_every_workload_is_accepted(self, workload):
        r = plan_deployment(
            hardware="RTX 4090 24GB",
            model_size="8b",
            request_rate=2.0,
            budget_usd_month=5000,
            workload=workload,
        )
        assert r["ok"]

    def test_variance_widens_the_tail(self):
        """Not just accepted -- actually wired through. A flag that parses and does
        nothing is worse than a missing one, because it reads as answered."""
        steady = plan_deployment(
            hardware="RTX 4090 24GB",
            model_size="8b",
            request_rate=2.0,
            budget_usd_month=5000,
            workload="steady",
        )
        agent = plan_deployment(
            hardware="RTX 4090 24GB",
            model_size="8b",
            request_rate=2.0,
            budget_usd_month=5000,
            workload="agent",
        )
        assert agent["recommended"]["p95_latency_ms"] > steady["recommended"]["p95_latency_ms"]

    def test_unknown_workload_is_actionable(self):
        r = plan_deployment(hardware="RTX 4090 24GB", workload="whatever")
        assert r["ok"] is False
        assert "whatever" in r["error"] and "steady" in r["hint"]

    def test_price_multiplier_scales_the_bill(self):
        base = plan_deployment(
            hardware="RTX 4090 24GB", model_size="8b", request_rate=2.0, budget_usd_month=1e9
        )
        dearer = plan_deployment(
            hardware="RTX 4090 24GB",
            model_size="8b",
            request_rate=2.0,
            budget_usd_month=1e9,
            gpu_price_multiplier=2.0,
        )
        assert dearer["recommended"]["monthly_cost_usd"] == pytest.approx(
            base["recommended"]["monthly_cost_usd"] * 2, rel=1e-6
        )


def test_build_server_registers_the_new_tools():
    pytest.importorskip("mcp", reason="optional [mcp] extra not installed")
    import importlib.util

    assert importlib.util.find_spec("mcp.server.fastmcp") is not None
    import asyncio

    from chimeraforge.mcp_server import build_server

    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert names == {
        "chimeraforge_plan",
        "chimeraforge_resolve_model",
        "chimeraforge_list_hardware",
        "chimeraforge_compare_api",
        "chimeraforge_suggest",
    }
