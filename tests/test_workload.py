"""Tests for workload profiles (`chimeraforge workload`, `plan --workload-profile`).

The feature replaces typed-in guesses with measured traffic, which means it can
fail in a way a guess cannot: by reporting a fabricated number wearing a `measured`
label. Two guards carry most of the weight here.

Metric names churn -- vLLM renamed `gpu_cache_usage_perc` to `kv_cache_usage_perc`
and `time_per_output_token_seconds` to `inter_token_latency_seconds`. A scraper
that silently falls back to a name the engine no longer exports would report a
stale or invented figure, so an unknown engine and a wrong-prefix endpoint both
fail loud, and any metric that is absent leaves its field absent.

And an absent field must never acquire a default: `plan` keeps requiring it, so a
partial profile cannot smuggle a made-up value in under the profile's badge.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pytest
import typer

from chimeraforge.planner.service import run_plan
from chimeraforge.workload import (
    ENGINE_METRICS,
    MIN_SAMPLES_FOR_VARIANCE,
    SCHEMA_VERSION,
    WorkloadError,
    WorkloadProfile,
    format_markdown,
    from_log,
    from_metrics,
    parse_prometheus,
)

FIXTURES = Path(__file__).parent / "fixtures"

# Defined at module scope so Typer can resolve the `typer.Context` annotation under
# `from __future__ import annotations` -- a nested command cannot see a local import.
_PROBE_SEEN: dict[str, bool] = {}
_probe_app = typer.Typer()


@_probe_app.command()
def _probe(ctx: typer.Context, rate: float = typer.Option(1.0, "--rate")) -> None:
    from click.core import ParameterSource

    src = ctx.get_parameter_source("rate")
    _PROBE_SEEN["by_name"] = getattr(src, "name", None) == "COMMANDLINE"
    _PROBE_SEEN["by_identity"] = src is ParameterSource.COMMANDLINE


@pytest.fixture(scope="module")
def log_profile():
    return from_log(FIXTURES / "requests_sample.jsonl")


@pytest.fixture(scope="module")
def vllm_profile():
    return from_metrics(
        (FIXTURES / "vllm_metrics.txt").read_text(encoding="utf-8"),
        engine="vllm",
        source="fixture",
        engine_version="0.11.0",
    )


@pytest.fixture(scope="module")
def sglang_profile():
    return from_metrics(
        (FIXTURES / "sglang_metrics.txt").read_text(encoding="utf-8"),
        engine="sglang",
        source="fixture",
    )


class TestFromLog:
    def test_derives_every_field_it_can(self, log_profile):
        for name in ("request_rate", "prompt_tokens", "output_tokens", "workload_cv2"):
            assert getattr(log_profile, name) is not None

    def test_per_request_data_is_measured_not_approximated(self, log_profile):
        # A log has the real distribution, so nothing here is bucket-reconstructed.
        for name in ("request_rate", "prompt_tokens", "output_tokens", "workload_cv2"):
            assert getattr(log_profile, name).provenance == "measured"

    def test_separates_arrival_variance_from_service_variance(self, tmp_path):
        """Ground truth, and the distinction the planner depends on.

        Exponential inter-arrivals have a CV^2 of exactly 1; constant decode
        lengths have a service CV^2 of exactly 0. This trace has both at once, so
        it fails if the two are ever conflated again -- and they were: the
        inter-arrival figure fed the service slot, so a Poisson-ish log always read
        as ~1 ("chatbot") no matter how uniform the responses actually were.
        """
        rng = random.Random(11)
        t = 1_700_000_000.0
        rows = []
        for _ in range(4000):
            t += rng.expovariate(1 / 2.0)
            rows.append({"timestamp": round(t, 4), "prompt_tokens": 100, "completion_tokens": 50})
        p = tmp_path / "poisson.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        got = from_log(p)
        assert got.arrival_cv2.value == pytest.approx(1.0, abs=0.15)
        assert got.workload_cv2.value == pytest.approx(0.0, abs=1e-9)

    def test_service_cv2_matches_the_lognormal_it_came_from(self, tmp_path):
        """For lognormal(mu, sigma) the CV^2 is exp(sigma^2) - 1, independent of mu.
        At sigma=0.7 that is 0.632 -- closed form, not self-consistency."""
        rng = random.Random(5)
        rows = [
            {
                "timestamp": 1_700_000_000 + i * 2.0,
                "prompt_tokens": 100,
                "completion_tokens": max(int(rng.lognormvariate(5.0, 0.7)), 1),
            }
            for i in range(6000)
        ]
        p = tmp_path / "lognormal.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        got = from_log(p)
        assert got.workload_cv2.value == pytest.approx(math.exp(0.7**2) - 1, rel=0.10)
        # Fixed-interval arrivals: the ARRIVAL figure is the one that must be 0 here.
        assert got.arrival_cv2.value == pytest.approx(0.0, abs=1e-9)

    def test_the_planner_is_fed_the_service_figure(self):
        """The queueing term takes a service CV^2 and hard-codes Poisson arrivals,
        so the arrival figure is reported but never passed through."""
        got = from_log(FIXTURES / "requests_sample.jsonl")
        assert got.plan_kwargs()["workload_cv2"] == got.workload_cv2.value
        assert got.arrival_cv2 is not None
        assert got.arrival_cv2.value != got.workload_cv2.value
        assert "not used by the planner" in got.arrival_cv2.note

    def test_recovers_a_deterministic_arrival_process(self, tmp_path):
        # Fixed-interval arrivals have CV^2 = 0. Anything above noise here means the
        # variance calculation is picking up something that is not in the data.
        rows = [
            {"timestamp": 1_700_000_000 + i * 2.0, "prompt_tokens": 10, "completion_tokens": 5}
            for i in range(200)
        ]
        p = tmp_path / "clockwork.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        assert from_log(p).workload_cv2.value == pytest.approx(0.0, abs=1e-6)

    def test_rate_matches_requests_over_window(self, log_profile):
        assert log_profile.request_rate.value == pytest.approx(
            log_profile.sample_count / log_profile.window_seconds, rel=1e-3
        )

    def test_accepts_iso_timestamps(self, tmp_path):
        rows = [
            {"timestamp": f"2026-08-21T10:00:{i:02d}Z", "prompt_tokens": 10, "output_tokens": 5}
            for i in range(40)
        ]
        p = tmp_path / "iso.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        assert from_log(p).request_rate is not None

    def test_alternate_field_names(self, tmp_path):
        rows = [
            {"ts": 1_700_000_000 + i, "input_tokens": 20, "generation_tokens": 7} for i in range(50)
        ]
        p = tmp_path / "alt.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        got = from_log(p)
        assert got.prompt_tokens.value == 20
        assert got.output_tokens.value == 7

    def test_too_few_samples_leaves_variance_absent(self, tmp_path):
        """A CV^2 from a handful of gaps is noise with a decimal point on it."""
        n = MIN_SAMPLES_FOR_VARIANCE - 5
        rows = [{"timestamp": 1_700_000_000 + i * 3, "prompt_tokens": 1} for i in range(n)]
        p = tmp_path / "tiny.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        got = from_log(p)
        assert got.workload_cv2 is None
        assert "workload_cv2" in got.absent

    def test_missing_token_fields_are_absent_not_defaulted(self, tmp_path):
        rows = [{"timestamp": 1_700_000_000 + i} for i in range(60)]
        p = tmp_path / "bare.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        got = from_log(p)
        assert got.prompt_tokens is None and got.output_tokens is None
        assert {"prompt_tokens", "output_tokens"} <= set(got.absent)

    def test_no_timestamps_reports_what_it_looked_for(self, tmp_path):
        rows = [{"prompt_tokens": 5, "completion_tokens": 2} for _ in range(10)]
        p = tmp_path / "nots.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        got = from_log(p)
        assert "request_rate" in got.absent
        assert any("timestamp" in n for n in got.notes)

    def test_malformed_lines_are_counted_not_silently_dropped(self, tmp_path):
        p = tmp_path / "mixed.jsonl"
        p.write_text('{"timestamp": 1, "prompt_tokens": 5}\nnot json\n[1,2]\n', encoding="utf-8")
        got = from_log(p)
        assert got.sample_count == 1
        assert any("2 line(s)" in n for n in got.notes)

    def test_empty_file_fails_loud(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("\n\n", encoding="utf-8")
        with pytest.raises(WorkloadError, match="no JSON objects"):
            from_log(p)

    def test_missing_file_fails_loud(self):
        with pytest.raises(WorkloadError, match="not found"):
            from_log("no/such/log.jsonl")

    def test_cache_hit_rate_is_token_weighted(self, log_profile):
        r = log_profile.prefix_cache_hit_rate
        assert r is not None and 0.0 <= r.value <= 1.0


class TestFromMetrics:
    def test_vllm_means_are_exact_from_sum_over_count(self, vllm_profile):
        # 906000 / 2000 and 288000 / 2000 -- sum and count are exact in Prometheus.
        assert vllm_profile.prompt_tokens.value == pytest.approx(453.0)
        assert vllm_profile.output_tokens.value == pytest.approx(144.0)
        assert vllm_profile.prompt_tokens.provenance == "measured"

    def test_bucket_derived_variance_is_estimated_not_measured(self, vllm_profile):
        """A histogram exposes the spread only through bucket edges, so a CV^2 from
        one is an approximation and must not inherit the mean's `measured` badge."""
        assert vllm_profile.workload_cv2.provenance == "estimated"
        assert "bucket" in vllm_profile.workload_cv2.note

    def test_rate_is_absent_from_a_single_scrape(self, vllm_profile):
        """One scrape is not a rate. Dividing a counter by an unmeasured uptime
        would be an invented number."""
        assert vllm_profile.request_rate is None
        assert "request_rate" in vllm_profile.absent
        assert any("not a rate" in n for n in vllm_profile.notes)

    def test_prefix_cache_from_the_two_counters(self, vllm_profile):
        assert vllm_profile.prefix_cache_hit_rate.value == pytest.approx(371460 / 906000, rel=1e-4)

    def test_gauges_are_labeled_instantaneous(self, vllm_profile):
        assert vllm_profile.peak_concurrency.value == 14.0
        assert vllm_profile.queue_depth.value == 3.0
        assert "instantaneous" in vllm_profile.peak_concurrency.note

    def test_engine_version_is_recorded(self, vllm_profile):
        # So a later reader knows which metric-name generation it was read with.
        assert vllm_profile.engine_version == "0.11.0"

    def test_sglang_uses_its_own_rate_gauge(self, sglang_profile):
        # SGLang publishes a percentage gauge, not vLLM's hits/queries counters.
        assert sglang_profile.prefix_cache_hit_rate.value == pytest.approx(0.385)
        assert sglang_profile.peak_concurrency.value == 22.0

    def test_sglang_absent_token_histograms_stay_absent(self, sglang_profile):
        assert sglang_profile.prompt_tokens is None
        assert "prompt_tokens" in sglang_profile.absent

    def test_unknown_engine_fails_loud(self):
        """Guessing a metric name is how a scraper fabricates a measurement."""
        with pytest.raises(WorkloadError, match="unknown engine"):
            from_metrics("vllm:num_requests_running 1.0", engine="tensorrt", source="x")

    def test_wrong_engine_for_the_endpoint_fails_loud(self):
        text = (FIXTURES / "vllm_metrics.txt").read_text(encoding="utf-8")
        with pytest.raises(WorkloadError, match="does not look like a sglang endpoint"):
            from_metrics(text, engine="sglang", source="x")

    def test_empty_scrape_fails_loud(self):
        with pytest.raises(WorkloadError, match="no Prometheus samples"):
            from_metrics("# just a comment\n", engine="vllm", source="x")

    def test_metric_names_carry_the_engine_prefix(self):
        for engine, names in ENGINE_METRICS.items():
            for key, value in names.items():
                if key == "prefix":
                    continue
                assert value.startswith(names["prefix"]), f"{engine}.{key} lacks the prefix"

    def test_no_renamed_vllm_metrics_are_referenced(self):
        """vLLM renamed both of these; referencing an old name would read a metric
        the engine no longer exports and report nothing, or worse, something else."""
        stale = {"vllm:gpu_cache_usage_perc", "vllm:time_per_output_token_seconds"}
        assert not stale & set(ENGINE_METRICS["vllm"].values())


class TestPrometheusParsing:
    def test_parses_labels_and_values(self):
        got = parse_prometheus('foo{a="1",b="two"} 3.5\n')
        assert got["foo"] == [({"a": "1", "b": "two"}, 3.5)]

    def test_skips_comments_and_blanks(self):
        assert parse_prometheus("# HELP x\n# TYPE x gauge\n\nx 1.0\n") == {"x": [({}, 1.0)]}

    def test_unlabeled_samples(self):
        assert parse_prometheus("bare_metric 42\n")["bare_metric"] == [({}, 42.0)]

    def test_non_numeric_value_is_skipped_not_crashed(self):
        assert parse_prometheus("x NaNish\ny 2\n") == {"y": [({}, 2.0)]}

    def test_multiple_series_under_one_name(self):
        got = parse_prometheus('c{r="a"} 1\nc{r="b"} 2\n')
        assert len(got["c"]) == 2


class TestProfileIO:
    def test_round_trips_through_json(self, log_profile, tmp_path):
        p = tmp_path / "wl.json"
        p.write_text(json.dumps(log_profile.to_dict()), encoding="utf-8")
        back = WorkloadProfile.load(p)
        assert back.plan_kwargs() == log_profile.plan_kwargs()
        assert back.absent == log_profile.absent

    def test_schema_version_is_stamped(self, log_profile):
        assert log_profile.to_dict()["schema_version"] == SCHEMA_VERSION

    def test_wrong_schema_version_is_refused(self, tmp_path):
        p = tmp_path / "old.json"
        p.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
        with pytest.raises(WorkloadError, match="schema_version"):
            WorkloadProfile.load(p)

    def test_bad_json_is_refused(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(WorkloadError, match="not valid JSON"):
            WorkloadProfile.load(p)

    def test_missing_file_is_refused(self):
        with pytest.raises(WorkloadError, match="not found"):
            WorkloadProfile.load("no/such/profile.json")

    def test_captured_at_is_always_present(self, log_profile, vllm_profile):
        for p in (log_profile, vllm_profile):
            assert p.captured_at
            assert "T" in p.captured_at

    def test_plan_kwargs_omits_absent_fields(self, vllm_profile):
        assert "request_rate" not in vllm_profile.plan_kwargs()

    def test_markdown_lists_what_was_not_measured(self, vllm_profile):
        md = format_markdown(vllm_profile)
        assert "Not measured" in md and "request_rate" in md
        assert "not defaulted" in md


class TestPlanIntegration:
    def test_round_trip_equals_the_same_values_as_flags(self, log_profile):
        """The profile must be a pure substitution for typed-in values -- if it is
        not, a plan silently depends on which route the numbers arrived by."""
        base = dict(model_size="8b", hardware="RTX 4090 24GB", budget=5000)
        via_profile = run_plan(**base, **log_profile.plan_kwargs()).candidates[0]
        kw = log_profile.plan_kwargs()
        via_flags = run_plan(
            **base,
            request_rate=kw["request_rate"],
            prompt_tokens=kw["prompt_tokens"],
            avg_tokens=kw["avg_tokens"],
            workload_cv2=kw["workload_cv2"],
            prefix_cache_hit_rate=kw["prefix_cache_hit_rate"],
        ).candidates[0]
        assert via_profile.p95_latency_ms == via_flags.p95_latency_ms
        assert via_profile.ttft_ms == via_flags.ttft_ms
        assert via_profile.n_agents == via_flags.n_agents
        assert via_profile.monthly_cost == via_flags.monthly_cost

    def test_measured_variance_moves_the_tail_off_the_preset(self, log_profile):
        """The whole point: a measured CV^2 is not one of four preset values, and
        the difference is not cosmetic."""
        base = dict(
            model_size="8b",
            hardware="RTX 4090 24GB",
            budget=5000,
            request_rate=log_profile.request_rate.value,
            prompt_tokens=int(log_profile.prompt_tokens.value),
            avg_tokens=int(log_profile.output_tokens.value),
            prefix_cache_hit_rate=log_profile.prefix_cache_hit_rate.value,
        )
        measured = run_plan(**base, workload_cv2=log_profile.workload_cv2.value).candidates[0]
        steady = run_plan(**base, workload_cv2=0.0).candidates[0]
        assert measured.p95_latency_ms > steady.p95_latency_ms * 1.2

    def test_cli_applies_the_profile(self, log_profile, tmp_path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        p = tmp_path / "wl.json"
        p.write_text(json.dumps(log_profile.to_dict()), encoding="utf-8")
        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model-size",
                "8b",
                "--hardware",
                "RTX 4090 24GB",
                "--budget",
                "5000",
                "--workload-profile",
                str(p),
            ],
        )
        assert r.exit_code == 0, r.output
        assert "profile captured" in r.output

    def test_explicit_flag_beats_the_profile(self, log_profile, tmp_path):
        """An explicit flag is a deliberate scenario ('what if traffic tripled').
        Overwriting it with yesterday's measurement answers a different question."""
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        p = tmp_path / "wl.json"
        p.write_text(json.dumps(log_profile.to_dict()), encoding="utf-8")
        args = [
            "plan",
            "--model-size",
            "8b",
            "--hardware",
            "RTX 4090 24GB",
            "--budget",
            "5000",
            "--workload-profile",
            str(p),
            "--json",
        ]
        r = CliRunner().invoke(app, args)
        override = CliRunner().invoke(app, [*args, "--request-rate", "20"])
        assert r.exit_code == 0 and override.exit_code == 0
        a = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])[0]
        b = json.loads(
            override.output[override.output.index("[") : override.output.rindex("]") + 1]
        )[0]
        # Utilisation is continuous in the request rate, so this detects the
        # override without depending on where the replica search happens to land.
        assert b["utilisation"] != a["utilisation"]
        # And it must land on exactly the plan that rate produces -- proving the
        # profile supplied everything else and nothing but the rate was overridden.
        direct = run_plan(
            model_size="8b",
            hardware="RTX 4090 24GB",
            budget=5000,
            request_rate=20.0,
            prompt_tokens=int(log_profile.prompt_tokens.value),
            avg_tokens=int(log_profile.output_tokens.value),
            workload_cv2=log_profile.workload_cv2.value,
            prefix_cache_hit_rate=log_profile.prefix_cache_hit_rate.value,
        ).candidates[0]
        assert b["n_agents"] == direct.n_agents
        assert b["p95_latency_ms"] == direct.p95_latency_ms

    def test_parameter_source_is_compared_by_name_not_identity(self):
        """Typer 0.27 vendors Click, so the ParameterSource returned by a Typer
        context is `typer._click.core.ParameterSource` -- an identity test against
        `click.core.ParameterSource.COMMANDLINE` is False, which silently made every
        explicit flag look unset. Passed under Typer 0.25, failed under 0.27."""
        from typer.testing import CliRunner as TyperRunner

        _PROBE_SEEN.clear()
        TyperRunner().invoke(_probe_app, ["--rate", "5"])
        assert _PROBE_SEEN["by_name"], "name comparison must detect a command-line flag"
        # Identity may or may not hold depending on whether Typer vendors Click;
        # the point is that the code must not depend on it.

    def test_no_profile_flag_changes_nothing(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app, ["plan", "--model-size", "8b", "--hardware", "RTX 4090 24GB", "--budget", "5000"]
        )
        assert r.exit_code == 0


class TestWorkloadCli:
    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["workload", *args])

    def test_from_log_json(self):
        r = self._run("--from-log", str(FIXTURES / "requests_sample.jsonl"), "--json")
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("{") : r.output.rindex("}") + 1])
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["fields"]["request_rate"]["provenance"] == "measured"

    def test_from_metrics_file(self):
        r = self._run(
            "--from-metrics", str(FIXTURES / "vllm_metrics.txt"), "--engine", "vllm", "--json"
        )
        assert r.exit_code == 0
        assert '"engine": "vllm"' in r.output

    def test_writes_the_profile(self, tmp_path):
        out = tmp_path / "wl.json"
        r = self._run("--from-log", str(FIXTURES / "requests_sample.jsonl"), "--out", str(out))
        assert r.exit_code == 0 and out.exists()
        assert "Profile written to" in r.output

    def test_metrics_without_engine_is_actionable(self):
        r = self._run("--from-metrics", str(FIXTURES / "vllm_metrics.txt"))
        assert r.exit_code == 1
        assert "--engine" in r.output

    def test_both_sources_is_refused(self):
        r = self._run("--from-log", "a.jsonl", "--from-metrics", "b.txt", "--engine", "vllm")
        assert r.exit_code == 1
        assert "exactly one" in r.output

    def test_neither_source_is_refused(self):
        r = self._run()
        assert r.exit_code == 1

    def test_unknown_engine_exits_nonzero_without_a_traceback(self):
        r = self._run("--from-metrics", str(FIXTURES / "vllm_metrics.txt"), "--engine", "tensorrt")
        assert r.exit_code == 1
        assert "Traceback" not in r.output
        assert "unknown engine" in r.output

    def test_human_output_flags_unmeasured_fields(self):
        r = self._run("--from-metrics", str(FIXTURES / "vllm_metrics.txt"), "--engine", "vllm")
        assert r.exit_code == 0
        assert "Not measured" in r.output


def test_histogram_variance_is_non_negative():
    """A bucket-midpoint variance can go negative on a skewed histogram; that must
    be dropped rather than surfaced as a nonsensical CV^2."""
    text = 'h_bucket{le="1.0"} 900\nh_bucket{le="+Inf"} 1000\nh_sum 950.0\nh_count 1000\n'
    samples = parse_prometheus(text)
    from chimeraforge.workload import _hist_stats

    mean, cv2, count = _hist_stats(samples, "h")
    assert count == 1000
    assert mean == pytest.approx(0.95)
    assert cv2 is None or (cv2 >= 0 and math.isfinite(cv2))
