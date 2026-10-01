"""Tests for hyperscaler on-demand pricing (`plan --cloud aws|azure`).

The bundled datacenter prices are marketplace rates, roughly 4-5x below what AWS
and Azure bill on demand. `--cloud` prices a plan against a dated snapshot of each
cloud's public list prices (scripts/build_cloud_prices.py), instance by instance:
a fleet pays for whole instances, so idle GPUs in a partly-filled one are billed,
and a TP/PP group must fit inside one instance.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib
from dataclasses import asdict

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from chimeraforge.planner import cloudprice
from chimeraforge.planner.cloudprice import fleet_hourly_cost, load_cloud_prices, offers_for
from chimeraforge.planner.constants import HOURS_PER_MONTH
from chimeraforge.planner.service import run_plan

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_cloud_prices", ROOT / "scripts" / "build_cloud_prices.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BASE = dict(model_size="8b", hardware="H100 80GB", request_rate=2.0, budget=1e9, quality_target=0.0)


def _plan(**over):
    kw = dict(BASE)
    kw.update(over)
    return run_plan(**kw)


class TestSnapshot:
    def test_validates(self):
        _builder().validate(load_cloud_prices())

    def test_every_offer_matches_the_hardware_db(self):
        hw = json.loads((ROOT / "src/chimeraforge/planner/data/hardware.json").read_text())
        vram = {g["name"]: g["vram_gb"] for g in hw["gpus"]}
        for o in load_cloud_prices()["offers"]:
            assert o["gpu"] in vram
            assert abs(o["gpu_memory_gb"] - vram[o["gpu"]]) / vram[o["gpu"]] <= 0.06
            assert o["price_source"] and o["spec_source"].startswith("https://")

    def test_different_cards_are_excluded_with_a_reason(self):
        ex = load_cloud_prices()["excluded"]
        assert "H100 NVL" in ex["azure:ncadsh100v5-series"]
        assert "PCIe" in ex["azure:nca100v4-series"]


class TestFleetCost:
    def test_whole_instances_are_billed(self):
        offers = offers_for("aws", "H100 80GB")
        one = next(o for o in offers if o.gpus == 1)
        eight = next(o for o in offers if o.gpus == 8)
        # 3 single-GPU replicas: three 1-GPU instances beat one 8-GPU instance.
        cost, offer, count = fleet_hourly_cost(offers, n_groups=3, group=1)
        assert (offer, count) == (one, 3)
        assert cost == pytest.approx(min(3 * one.price_per_hour, eight.price_per_hour))
        # A TP=4 group fits only the 8-GPU instance, which bills all 8.
        cost, offer, count = fleet_hourly_cost(offers, n_groups=1, group=4)
        assert (offer, count, cost) == (eight, 1, eight.price_per_hour)
        # Two TP=4 groups share one 8-GPU instance.
        assert fleet_hourly_cost(offers, n_groups=2, group=4)[0] == eight.price_per_hour

    def test_no_instance_holds_the_group(self):
        offers = offers_for("aws", "L4 24GB")
        assert max(o.gpus for o in offers) == 8
        assert fleet_hourly_cost(offers, n_groups=1, group=16) is None

    def test_unknown_cloud(self):
        with pytest.raises(ValueError, match="cloud must be one of"):
            offers_for("gcp", "H100 80GB")


class TestPlan:
    def test_default_unchanged(self):
        a, b = _plan().candidates, _plan(cloud=None).candidates
        assert [asdict(c) for c in a] == [asdict(c) for c in b]

    def test_aws_bill_is_the_instance_bill(self):
        c = _plan(cloud="aws").candidates[0]
        offers = offers_for("aws", "H100 80GB")
        cost, offer, count = fleet_hourly_cost(offers, c.n_agents, c.tensor_parallel)
        assert c.monthly_cost == pytest.approx(cost * HOURS_PER_MONTH, rel=1e-6)
        assert offer.instance in c.cloud_offer and "us-east-1" in c.cloud_offer
        assert any("hyperscaler on-demand" in w and "aws" in w for w in c.warnings)

    def test_on_demand_costs_more_than_marketplace(self):
        market = _plan().candidates[0]
        aws = _plan(cloud="aws").candidates[0]
        assert aws.cost_per_1m_tok > market.cost_per_1m_tok

    def test_gpu_the_cloud_does_not_sell_is_refused_with_a_reason(self):
        res = _plan(cloud="aws", hardware="RTX 4090 24GB")
        assert not res.candidates
        assert any("no aws on-demand instance" in t[3] for t in res.trace)

    def test_conflicting_price_sources_refused(self):
        with pytest.raises(ValueError, match="--cloud"):
            _plan(
                cloud="aws",
                hardware="RTX 6090 48GB",
                gpu_overrides={"vram_gb": 48, "bandwidth_gbps": 1500, "cost_per_hour": 1.0},
            )

    def test_unknown_cloud_refused(self):
        with pytest.raises(ValueError, match="cloud must be one of"):
            _plan(cloud="gcp")

    def test_stale_snapshot_warns(self, monkeypatch):
        captured = dt.date.fromisoformat(load_cloud_prices()["captured_at"])
        monkeypatch.setattr(cloudprice, "_today", lambda: captured + dt.timedelta(days=200))
        c = _plan(cloud="aws").candidates[0]
        assert any("stale" in w for w in c.warnings)

    def test_tp_group_needs_one_instance(self):
        res = _plan(cloud="aws", hardware="L4 24GB", tensor_parallel=16, model_size="8b")
        assert not res.candidates
        assert any("holds a TP=16 group" in t[3] or "vram" == t[2] for t in res.trace)


runner = CliRunner()
CLI = ["plan", "--model-size", "8b", "--hardware", "H100 80GB", "--budget", "1000000"]


class TestSurfaces:
    def test_cli(self):
        r = runner.invoke(app, [*CLI, "--cloud", "azure", "--json"])
        assert r.exit_code == 0, r.output
        row = json.loads(r.output)[0]
        assert "Standard_ND96isr_H100_v5" in row["cloud_offer"]

    def test_cli_bad_cloud(self):
        r = runner.invoke(app, [*CLI, "--cloud", "gcp"])
        assert r.exit_code == 1 and "Traceback" not in r.output

    def test_mcp(self):
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(model_size="8b", hardware="H100 80GB", cloud="aws")
        assert out["ok"], out
        assert "p5" in out["recommended"]["cloud_offer"]

    def test_report_reproduces_the_flag(self, tmp_path):
        out = tmp_path / "b.md"
        r = runner.invoke(app, [*CLI, "--cloud", "aws", "--report", str(out)])
        assert r.exit_code == 0, r.output
        assert "--cloud aws" in out.read_text(encoding="utf-8")
