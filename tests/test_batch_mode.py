"""Tests for `plan --mode batch`: offline throughput jobs with no latency gate.

A batch job (nightly summarisation, embedding backfill, eval sweeps) has a
backlog, not users waiting on a response. Nothing queues against a latency SLO,
so the p95 gate and the 70% utilisation headroom that online serving needs are
the wrong constraints: they force small batches and extra replicas, and the job
pays for latency nobody reads. Batch mode drops them, runs each GPU at the batch
size that maximises its throughput, sizes the fleet to the drain rate at full
utilisation, and ranks by $/1M tokens.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from chimeraforge.planner.engine import pareto_frontier
from chimeraforge.planner.service import run_plan

BASE = dict(
    model_size="8b",
    hardware="H100 80GB",
    request_rate=2.0,
    budget=1e9,
    quality_target=0.0,
)


def _plan(**over):
    kw = dict(BASE)
    kw.update(over)
    return run_plan(**kw)


def _by_cell(cands):
    return {(c.model, c.quant, c.backend): c for c in cands}


class TestOnlineUnchanged:
    def test_default_mode_is_online(self):
        a, b = _plan().candidates, _plan(mode="online").candidates
        assert [asdict(c) for c in a] == [asdict(c) for c in b]
        assert all(c.mode == "online" for c in a)

    def test_online_has_no_batch_warning(self):
        assert not any("batch mode" in w for c in _plan().candidates for w in c.warnings)


class TestNoLatencyGate:
    def test_batch_plans_where_online_latency_rejects_everything(self):
        # A 50ms end-to-end SLO cannot be met by any 8B config decoding 128 tokens.
        assert not _plan(latency_slo=50.0).candidates
        assert _plan(mode="batch").candidates

    @pytest.mark.parametrize(
        "flag", [{"latency_slo": 1000.0}, {"ttft_slo": 500.0}, {"tpot_slo": 50.0}]
    )
    def test_latency_targets_are_refused_not_ignored(self, flag):
        with pytest.raises(ValueError, match="batch mode has no latency gate"):
            _plan(mode="batch", **flag)

    def test_unknown_mode_is_refused(self):
        with pytest.raises(ValueError, match="mode must be one of"):
            _plan(mode="offline")

    def test_p95_is_service_time_without_queue(self):
        for c in _plan(mode="batch").candidates:
            service = c.ttft_ms + c.decode_tokens_per_req * c.tpot_ms
            # tpot_ms and ttft_ms are reported to 0.1 ms, so the recomposed sum
            # carries up to 0.05 ms of rounding per decoded token.
            slack = 0.05 * (c.decode_tokens_per_req + 1) + 0.1
            assert c.p95_latency_ms == pytest.approx(service, abs=slack)

    def test_warning_discloses_what_was_dropped(self):
        c = _plan(mode="batch").candidates[0]
        assert any("batch mode" in w and "queue" in w for w in c.warnings)


class TestThroughputSizing:
    def test_batching_backend_runs_bigger_batch_and_cheaper_tokens(self):
        online = _by_cell(_plan().candidates)
        batch = _by_cell(_plan(mode="batch").candidates)
        shared = [k for k in online if k in batch and k[2] == "vllm"]
        assert shared, "expected a vllm cell in both plans"
        for k in shared:
            assert batch[k].effective_batch >= online[k].effective_batch
            assert batch[k].cost_per_1m_tok <= online[k].cost_per_1m_tok
            per_gpu_b = batch[k].total_throughput_tps / batch[k].gpus_total
            per_gpu_o = online[k].total_throughput_tps / online[k].gpus_total
            assert per_gpu_b >= per_gpu_o
        assert any(batch[k].effective_batch > online[k].effective_batch for k in shared)

    def test_fleet_is_the_smallest_that_drains_the_rate(self):
        for c in _plan(mode="batch").candidates:
            required = BASE["request_rate"] * c.decode_tokens_per_req
            per_unit = c.total_throughput_tps / c.n_agents
            assert c.total_throughput_tps >= required * (1 - 1e-3)
            assert (c.n_agents - 1) * per_unit < required
            assert c.utilisation <= 1.0 + 1e-3

    def test_ranked_by_cost_per_token(self):
        costs = [c.cost_per_1m_tok for c in _plan(mode="batch").candidates]
        assert costs == sorted(costs)


class TestPareto:
    def test_batch_frontier_trades_token_cost_against_quality(self):
        res = _plan(mode="batch", pareto=True)
        front = res.frontier
        assert front
        for a in front:
            for b in res.candidates:
                dominated = (
                    b.cost_per_1m_tok <= a.cost_per_1m_tok
                    and b.quality >= a.quality
                    and (b.cost_per_1m_tok < a.cost_per_1m_tok or b.quality > a.quality)
                )
                assert not dominated
        assert pareto_frontier(res.candidates) == front


runner = CliRunner()
CLI_BASE = ["plan", "--model-size", "8b", "--hardware", "H100 80GB", "--budget", "1000000"]


class TestCli:
    def test_batch_json(self):
        r = runner.invoke(app, [*CLI_BASE, "--mode", "batch", "--json"])
        assert r.exit_code == 0, r.output
        rows = json.loads(r.output)
        assert rows and all(row["mode"] == "batch" for row in rows)

    @pytest.mark.parametrize(
        "extra", [["--latency-slo", "900"], ["--ttft-slo", "200"], ["--tpot-slo", "40"]]
    )
    def test_latency_flags_refused(self, extra):
        r = runner.invoke(app, [*CLI_BASE, "--mode", "batch", *extra])
        assert r.exit_code == 1
        assert "batch mode has no latency gate" in r.output

    def test_bad_mode(self):
        r = runner.invoke(app, [*CLI_BASE, "--mode", "fast"])
        assert r.exit_code == 1
        assert "--mode must be one of" in r.output

    def test_human_output_names_the_mode(self):
        r = runner.invoke(app, [*CLI_BASE, "--mode", "batch"])
        assert r.exit_code == 0, r.output
        assert "batch" in r.output.lower()
        assert "Latency SLO" not in r.output

    def test_fleet_forwards_mode(self):
        # The fleet path re-plans each GPU type through its own kwargs; a dropped
        # knob there would size the mix online while the user asked for batch.
        def rates(*extra):
            r = runner.invoke(
                app,
                [
                    "plan",
                    "--model-size",
                    "8b",
                    "--fleet",
                    "H100 80GB,A100 80GB",
                    "--budget",
                    "1000000",
                    "--json",
                    *extra,
                ],
            )
            assert r.exit_code == 0, r.output
            return {g["gpu"]: g["rate_per_gpu"] for g in json.loads(r.output)["fleet"]["per_gpu"]}

        online, batch = rates(), rates("--mode", "batch")
        assert online.keys() == batch.keys()
        assert all(batch[g] > online[g] for g in online)


class TestMcp:
    def test_mcp_batch(self):
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(
            model_size="8b", hardware="H100 80GB", budget_usd_month=1e9, mode="batch"
        )
        assert out["ok"], out
        rows = [out["recommended"], *out["alternatives"]]
        assert all(c["mode"] == "batch" for c in rows)

    def test_mcp_refuses_latency_in_batch(self):
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(
            model_size="8b",
            hardware="H100 80GB",
            budget_usd_month=1e9,
            mode="batch",
            latency_slo_ms=900.0,
        )
        assert not out["ok"]
        assert "batch mode has no latency gate" in out["error"]


class TestReport:
    def test_brief_states_batch_mode_and_reproduces_it(self, tmp_path):
        out = tmp_path / "brief.md"
        r = runner.invoke(app, [*CLI_BASE, "--mode", "batch", "--report", str(out)])
        assert r.exit_code == 0, r.output
        text = out.read_text(encoding="utf-8")
        assert "| Mode | batch" in text
        assert "Latency SLO" not in text
        assert "--mode batch" in text
        assert "--latency-slo" not in text
