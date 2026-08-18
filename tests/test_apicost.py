"""Tests for self-host vs hosted-API cost comparison and break-even volume.

The arithmetic is pinned to hand-computed values rather than to whatever the code
happens to emit, so these are falsifiable. The rest of the file guards the honesty
properties: prices are a dated snapshot that goes stale, and a frontier API is
labeled as a different quality tier rather than passed off as like-for-like.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

import pytest

from chimeraforge.planner.apicost import (
    SECONDS_PER_MONTH,
    STALE_AFTER_DAYS,
    ApiComparison,
    PricingError,
    api_monthly_cost,
    breakeven_output_tokens,
    compare,
    load_pricing,
    snapshot_age_days,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

FAKE = {
    "schema_version": 1,
    "captured_at": "2026-08-18",
    "providers": {
        "acme": {
            "display_name": "Acme",
            "source_url": "https://example.com/pricing",
            "captured_at": "2026-08-18",
            "class": "open",
            "models": {"tiny": {"name": "Tiny", "input_per_1m": 1.0, "output_per_1m": 2.0}},
        }
    },
}


class TestArithmetic:
    def test_monthly_cost_is_hand_checkable(self):
        # 1M requests, 512 in @ $2/M, 128 out @ $10/M
        #   per request = (512*2 + 128*10)/1e6 = 2304/1e6 = $0.002304
        #   monthly     = 0.002304 * 1e6 = $2304
        got = api_monthly_cost(
            requests_per_month=1_000_000,
            prompt_tokens=512,
            output_tokens=128,
            input_per_1m=2.0,
            output_per_1m=10.0,
        )
        assert got == pytest.approx(2304.0)

    def test_breakeven_is_hand_checkable(self):
        # $1800/mo self-host vs $0.002304/request -> 781,250 requests
        #   -> 781,250 * 128 output tokens = 100,000,000 output tokens/month
        got = breakeven_output_tokens(
            self_host_monthly=1800.0,
            prompt_tokens=512,
            output_tokens=128,
            input_per_1m=2.0,
            output_per_1m=10.0,
        )
        assert got == pytest.approx(100_000_000.0)

    def test_at_breakeven_the_two_costs_are_equal(self):
        # The defining property: priced at exactly the break-even volume, API spend
        # equals the self-host bill.
        self_host, prompt, out = 1800.0, 512, 128
        be_tokens = breakeven_output_tokens(
            self_host_monthly=self_host,
            prompt_tokens=prompt,
            output_tokens=out,
            input_per_1m=2.0,
            output_per_1m=10.0,
        )
        requests = be_tokens / out
        api = api_monthly_cost(
            requests_per_month=requests,
            prompt_tokens=prompt,
            output_tokens=out,
            input_per_1m=2.0,
            output_per_1m=10.0,
        )
        assert api == pytest.approx(self_host)

    def test_requests_per_month_from_rate(self):
        c = compare(
            self_host_monthly=100.0,
            request_rate=1.0,
            prompt_tokens=10,
            output_tokens=10,
            pricing=FAKE,
        )
        assert c.requests_per_month == pytest.approx(SECONDS_PER_MONTH)

    def test_zero_output_has_no_breakeven(self):
        assert (
            breakeven_output_tokens(
                self_host_monthly=100.0,
                prompt_tokens=10,
                output_tokens=0,
                input_per_1m=1.0,
                output_per_1m=1.0,
            )
            is None
        )

    def test_free_api_has_no_breakeven(self):
        assert (
            breakeven_output_tokens(
                self_host_monthly=100.0,
                prompt_tokens=10,
                output_tokens=10,
                input_per_1m=0.0,
                output_per_1m=0.0,
            )
            is None
        )


class TestVerdict:
    def _cmp(self, self_host):
        return compare(
            self_host_monthly=self_host,
            request_rate=1.0,
            prompt_tokens=100,
            output_tokens=100,
            pricing=FAKE,
        )

    def test_expensive_self_host_loses(self):
        opt = self._cmp(10**9).options[0]
        assert opt.self_host_cheaper is False

    def test_cheap_self_host_wins(self):
        opt = self._cmp(0.01).options[0]
        assert opt.self_host_cheaper is True

    def test_options_sorted_cheapest_first(self):
        c = compare(
            self_host_monthly=1800.0,
            request_rate=2.0,
            prompt_tokens=512,
            output_tokens=128,
        )
        costs = [o.monthly_cost for o in c.options]
        assert costs == sorted(costs)


class TestStaleness:
    def test_age_in_days(self):
        assert snapshot_age_days("2026-08-01", today=dt.date(2026, 8, 18)) == 17

    def test_future_date_clamps_to_zero(self):
        assert snapshot_age_days("2027-01-01", today=dt.date(2026, 8, 18)) == 0

    def test_bad_date_raises(self):
        with pytest.raises(PricingError):
            snapshot_age_days("not-a-date")

    def test_fresh_snapshot_not_stale(self):
        c = compare(
            self_host_monthly=1.0,
            request_rate=1.0,
            prompt_tokens=1,
            output_tokens=1,
            pricing=FAKE,
            today=dt.date(2026, 8, 18),
        )
        assert c.age_days == 0 and c.stale is False

    def test_old_snapshot_is_flagged_stale(self):
        old = dt.date(2026, 8, 18) + dt.timedelta(days=STALE_AFTER_DAYS + 1)
        c = compare(
            self_host_monthly=1.0,
            request_rate=1.0,
            prompt_tokens=1,
            output_tokens=1,
            pricing=FAKE,
            today=old,
        )
        assert c.stale is True

    def test_missing_date_is_treated_as_stale(self):
        # Absent provenance must never read as "current".
        c = compare(
            self_host_monthly=1.0,
            request_rate=1.0,
            prompt_tokens=1,
            output_tokens=1,
            pricing={"schema_version": 1, "providers": FAKE["providers"]},
        )
        assert c.stale is True


class TestBundledSnapshot:
    def test_loads_from_package(self):
        assert load_pricing()["schema_version"] == 1

    def test_every_model_carries_both_prices(self):
        for pname, block in load_pricing()["providers"].items():
            for mkey, m in block["models"].items():
                assert m["input_per_1m"] > 0, f"{pname}:{mkey}"
                assert m["output_per_1m"] > 0, f"{pname}:{mkey}"

    def test_every_provider_cites_an_https_source(self):
        for pname, block in load_pricing()["providers"].items():
            assert block["source_url"].startswith("https://"), pname
            assert block["captured_at"], pname

    def test_frontier_models_are_labeled_not_passed_off_as_like_for_like(self):
        classes = {b["class"] for b in load_pricing()["providers"].values()}
        assert "frontier" in classes and "open" in classes

    def test_comparison_surfaces_source_urls(self):
        c = compare(
            self_host_monthly=1800.0,
            request_rate=2.0,
            prompt_tokens=512,
            output_tokens=128,
        )
        assert c.sources and all(u.startswith("https://") for u in c.sources.values())

    def test_snapshot_passes_the_build_script_validator(self):
        # The same validation that gates a rebuild also gates the committed file.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_cost_data", ROOT / "scripts" / "build_cost_data.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.validate(
            json.loads((ROOT / mod.SNAPSHOT.relative_to(ROOT)).read_text(encoding="utf-8"))
        )


class TestSerialization:
    def test_to_dict_shape(self):
        c = compare(
            self_host_monthly=1800.0,
            request_rate=2.0,
            prompt_tokens=512,
            output_tokens=128,
        )
        d = c.to_dict()
        assert {"self_host_monthly_usd", "prices_captured_at", "prices_stale", "options"} <= set(d)
        assert d["options"] and {"key", "class", "monthly_cost_usd"} <= set(d["options"][0])
        json.dumps(d)  # must be JSON-serializable

    def test_returns_comparison_type(self):
        assert isinstance(
            compare(
                self_host_monthly=1.0,
                request_rate=1.0,
                prompt_tokens=1,
                output_tokens=1,
                pricing=FAKE,
            ),
            ApiComparison,
        )


class TestCliSurface:
    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["plan", *args])

    def test_human_output_shows_table(self):
        r = self._run("--model-size", "3b", "--compare-api", "--budget", "5000")
        assert r.exit_code == 0
        assert "Self-host vs hosted API" in r.output

    def test_absent_without_flag(self):
        r = self._run("--model-size", "3b", "--budget", "5000")
        assert r.exit_code == 0
        assert "Self-host vs hosted API" not in r.output

    def test_json_contract_unchanged_without_flag(self):
        r = self._run("--model-size", "3b", "--json", "--budget", "5000")
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert isinstance(data, list)

    def test_json_wraps_when_requested(self):
        r = self._run("--model-size", "3b", "--json", "--compare-api", "--budget", "5000")
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("{") : r.output.rindex("}") + 1])
        assert set(data) == {"candidates", "api_comparison"}
        assert data["api_comparison"]["options"]
        assert data["api_comparison"]["prices_captured_at"]

    def test_launch_and_compare_api_coexist(self):
        r = self._run(
            "--model-size", "3b", "--json", "--compare-api", "--launch", "--budget", "5000"
        )
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("{") : r.output.rindex("}") + 1])
        assert set(data) == {"candidates", "launch", "api_comparison"}
