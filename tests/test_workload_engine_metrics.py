"""Tests for the engine metrics `workload --from-metrics` now reads.

Fixtures are real prometheus_client output (scripts/make_engine_metrics_fixtures.py)
from the names, types and labels declared in vLLM v0.30.0 and SGLang v0.5.20
source, scraped 60 s apart with traffic chosen so every answer is exact.

What is under test:
- the Counter-name rule (prometheus_client exposes a Counter as ``<name>_total``),
  which the hand-typed fixture hid and which made the vLLM prefix-cache hit rate
  unreadable from every real endpoint;
- KV-cache pressure gauges (vLLM kv_cache_usage_perc, SGLang token_usage and its
  SWA/Mamba pools), which are fractions 0-1 whatever the "perc" in the name says;
- a two-scrape window: a measured request rate, window (not since-boot) means,
  and MFU/MBU from the engines' own FLOP/byte counters over the interval --
  labeled estimated, because those counts are the engine's analytical model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from chimeraforge.planner.hardware import get_gpu
from chimeraforge.workload import (
    ENGINE_METRICS,
    COUNTER_KEYS,
    WorkloadError,
    from_metrics,
    from_metrics_window,
)

FIXTURES = Path(__file__).parent / "fixtures"
H100 = get_gpu("H100 80GB")


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _window(engine: str, gpu=H100, seconds: float = 60.0):
    return from_metrics_window(
        _read(f"{engine}_window_t0.txt"),
        _read(f"{engine}_window_t1.txt"),
        seconds,
        engine=engine,
        source="fixture",
        gpu=gpu,
    )


class TestCounterNames:
    def test_every_counter_read_carries_the_total_suffix(self):
        """prometheus_client exposes Counter("x") as x_total. A counter read by its
        declared name matches nothing on a real endpoint."""
        for engine, names in ENGINE_METRICS.items():
            for key in COUNTER_KEYS:
                if key in names:
                    assert names[key].endswith("_total"), f"{engine}.{key}: {names[key]}"

    def test_vllm_prefix_cache_reads_a_real_scrape(self):
        p = from_metrics(_read("vllm_window_t1.txt"), engine="vllm", source="x")
        # Cumulative since boot: (100000 + 24576) / (400000 + 61440).
        # Reported to 4 decimal places.
        assert p.prefix_cache_hit_rate.value == pytest.approx(124576 / 461440, abs=5e-5)


class TestKvPressure:
    def test_vllm_kv_usage_is_the_fullest_engine(self):
        p = from_metrics(_read("vllm_window_t1.txt"), engine="vllm", source="x")
        assert p.kv_cache_usage.value == pytest.approx(0.52)
        assert p.kv_cache_usage.provenance == "measured"
        assert "instantaneous" in p.kv_cache_usage.note

    def test_sglang_token_usage(self):
        p = from_metrics(_read("sglang_window_t1.txt"), engine="sglang", source="x")
        assert p.kv_cache_usage.value == pytest.approx(0.62)

    def test_zero_hybrid_pools_are_not_reported_as_measurements(self):
        """SGLang registers the SWA and Mamba gauges for every model; 0 there is not
        evidence the pool exists."""
        p = from_metrics(_read("sglang_window_t1.txt"), engine="sglang", source="x")
        assert p.swa_kv_usage is None and p.mamba_state_usage is None
        assert any("swa_token_usage" in n for n in p.notes)

    def test_nonzero_hybrid_pool_is_reported(self):
        text = _read("sglang_window_t1.txt").replace(
            'sglang:swa_token_usage{model_name="Qwen/Qwen3-8B"} 0.0',
            'sglang:swa_token_usage{model_name="Qwen/Qwen3-8B"} 0.81',
        )
        p = from_metrics(text, engine="sglang", source="x")
        assert p.swa_kv_usage.value == pytest.approx(0.81)

    def test_sglang_token_histograms_now_read(self):
        p = from_metrics(_read("sglang_window_t1.txt"), engine="sglang", source="x")
        # (500*300 + 90*1024) / 590 and (500*80 + 90*256) / 590, since boot.
        assert p.prompt_tokens.value == pytest.approx((150000 + 92160) / 590, abs=0.01)
        assert p.output_tokens.value == pytest.approx((40000 + 23040) / 590, abs=0.01)


class TestWindow:
    def test_request_rate_is_measured(self):
        p = _window("vllm")
        assert p.request_rate.value == pytest.approx(2.0)
        assert p.request_rate.provenance == "measured"
        assert "request_rate" not in p.absent
        assert p.window_seconds == 60.0

    def test_sglang_rate_counts_a_series_that_appeared_mid_window(self):
        # is_streaming="false" first appears in the second scrape: 60 + 30 = 90.
        assert _window("sglang").request_rate.value == pytest.approx(1.5)

    def test_means_are_the_window_not_since_boot(self):
        p = _window("vllm")
        assert p.prompt_tokens.value == pytest.approx(512.0)
        assert p.output_tokens.value == pytest.approx(128.0)
        assert p.sample_count == 120
        assert p.prefix_cache_hit_rate.value == pytest.approx(0.4)

    def test_window_variance_from_window_buckets(self):
        # Half 1 s and half 3 s, in buckets (0.5,1.5] and (2.5,5]: midpoints 1.0 and
        # 3.75 -> an approximated CV^2 that is nonzero, and labeled estimated.
        cv2 = _window("vllm").workload_cv2
        assert cv2.value > 0 and cv2.provenance == "estimated"

    def test_plan_kwargs_now_carry_the_rate(self):
        assert _window("vllm").plan_kwargs()["request_rate"] == pytest.approx(2.0)

    def test_mfu_mbu_average_the_ranks(self):
        p = _window("vllm")
        assert p.mfu.value == pytest.approx(0.30, rel=1e-6)
        assert p.mbu.value == pytest.approx(0.60, rel=1e-6)
        assert p.mfu.provenance == "estimated" and "analytical" in p.mfu.note
        assert p.achieved_tflops.value == pytest.approx(0.30 * 989.0, rel=1e-6)

    def test_sglang_mfu_mbu(self):
        p = _window("sglang")
        assert p.mfu.value == pytest.approx(0.25, rel=1e-6)
        assert p.mbu.value == pytest.approx(0.72, rel=1e-6)

    def test_no_gpu_gives_throughput_but_no_utilisation(self):
        p = _window("vllm", gpu=None)
        assert p.mfu is None and p.mbu is None
        assert p.achieved_tflops.value == pytest.approx(0.30 * 989.0, rel=1e-6)
        assert any("--hardware" in n for n in p.notes)

    def test_counters_off_say_how_to_turn_them_on(self):
        strip = lambda t: "\n".join(l for l in t.splitlines() if "estimated_" not in l)  # noqa: E731,E741
        p = from_metrics_window(
            strip(_read("vllm_window_t0.txt")),
            strip(_read("vllm_window_t1.txt")),
            60.0,
            engine="vllm",
            source="x",
            gpu=H100,
        )
        assert p.mfu is None
        assert any("--enable-mfu-metrics" in n for n in p.notes)

    def test_counter_reset_fails_loud(self):
        with pytest.raises(WorkloadError, match="reset"):
            from_metrics_window(
                _read("vllm_window_t1.txt"),
                _read("vllm_window_t0.txt"),
                60.0,
                engine="vllm",
                source="x",
            )

    def test_nonpositive_interval_fails(self):
        with pytest.raises(WorkloadError, match="interval"):
            _window("vllm", seconds=0.0)

    def test_idle_window_leaves_fields_absent(self):
        t1 = _read("vllm_window_t1.txt")
        p = from_metrics_window(t1, t1, 60.0, engine="vllm", source="x")
        assert p.request_rate.value == 0.0
        assert p.prompt_tokens is None and "prompt_tokens" in p.absent

    def test_single_scrape_says_utilisation_needs_a_window(self):
        p = from_metrics(_read("vllm_window_t1.txt"), engine="vllm", source="x")
        assert p.mfu is None
        assert any("--interval" in n for n in p.notes)

    def test_roundtrips_through_the_profile_file(self, tmp_path):
        from chimeraforge.workload import WorkloadProfile

        p = _window("vllm")
        path = tmp_path / "w.json"
        path.write_text(json.dumps(p.to_dict()), encoding="utf-8")
        back = WorkloadProfile.load(path)
        assert back.mfu.value == pytest.approx(p.mfu.value)
        assert back.kv_cache_usage.value == pytest.approx(0.52)


runner = CliRunner()


class TestCli:
    def _run(self, *args):
        return runner.invoke(app, ["workload", *args], terminal_width=200)

    def test_two_saved_scrapes(self):
        r = self._run(
            "--from-metrics",
            str(FIXTURES / "vllm_window_t0.txt"),
            "--from-metrics",
            str(FIXTURES / "vllm_window_t1.txt"),
            "--interval",
            "60",
            "--engine",
            "vllm",
            "--hardware",
            "H100 80GB",
            "--json",
        )
        assert r.exit_code == 0, r.output
        fields = json.loads(r.output)["fields"]
        assert fields["request_rate"]["value"] == pytest.approx(2.0)
        assert fields["mfu"]["value"] == pytest.approx(0.30)
        assert "as stated" in fields["request_rate"]["note"]

    def test_human_output_shows_new_fields(self):
        r = self._run(
            "--from-metrics",
            str(FIXTURES / "sglang_window_t0.txt"),
            "--from-metrics",
            str(FIXTURES / "sglang_window_t1.txt"),
            "--interval",
            "60",
            "--engine",
            "sglang",
            "--hardware",
            "H100 80GB",
        )
        assert r.exit_code == 0, r.output
        assert "kv_cache_usage" in r.output and "mfu" in r.output

    @pytest.mark.parametrize(
        "args, msg",
        [
            (["--from-metrics", "a.txt", "--from-metrics", "b.txt"], "--interval"),
            (["--from-metrics", "a.txt", "--interval", "60"], "two saved scrapes"),
            (
                [
                    "--from-metrics",
                    "a.txt",
                    "--from-metrics",
                    "b.txt",
                    "--from-metrics",
                    "c.txt",
                    "--interval",
                    "5",
                ],
                "at most two",
            ),
            (["--from-metrics", "x.txt", "--hardware", "Nope 9000"], "not in the hardware DB"),
        ],
    )
    def test_bad_combinations_fail_clean(self, args, msg):
        r = self._run(*args, "--engine", "vllm")
        assert r.exit_code == 1
        assert msg in " ".join(r.output.split())  # Rich wraps stderr
        assert "Traceback" not in r.output

    def test_live_url_is_scraped_twice_and_timed(self, monkeypatch):
        import chimeraforge.workload as wl

        scrapes = iter([_read("vllm_window_t0.txt"), _read("vllm_window_t1.txt")])
        clock = iter([100.0, 160.0])
        monkeypatch.setattr(wl, "fetch_metrics", lambda url, timeout=10.0: next(scrapes))
        monkeypatch.setattr(wl, "_monotonic", lambda: next(clock))
        monkeypatch.setattr(wl, "_sleep", lambda s: None)
        r = self._run(
            "--from-metrics", "http://gpu:8000/metrics", "--interval", "60",
            "--engine", "vllm", "--json",
        )  # fmt: skip
        assert r.exit_code == 0, r.output
        f = json.loads(r.output)["fields"]["request_rate"]
        assert f["value"] == pytest.approx(2.0)
        assert "measured interval" in f["note"]
