"""Tests for what a provenance label is allowed to claim.

An adversarial review found the same defect in four places: **a label chosen
from something other than the value it describes.** The throughput lookup key is
`model|backend|quant` and carries no hardware, so a lookup hit was stamped
`measured` and the value was then multiplied by `bandwidth_ratio(hardware)` --
reporting a 13.8x extrapolation of a 95.9 tok/s RTX 4080 measurement as 1327.5
tok/s "measured" on a B200, with no warning.

That is the worst failure this codebase can have. A crash is visible; a
confidently-wrong `measured` badge is not, and it is the field the MCP server
hands an assistant and the brief renders as prose.

Two downstream honesty checks were keyed off the same field and so were silently
disabled by it: the fleet's "a mix compounds throughput error" warning, and
`validate.classify()`, which filed bandwidth-extrapolated cells under
`measured-lookup` -- the bucket meaning "not an out-of-sample test". The audit
harness could not have detected the bug it was pointed at.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.brief import PROVENANCE_MARK, PROVENANCE_PHRASE, PROV_DERIVED
from chimeraforge.planner.fleet import PROVENANCE_ORDER
from chimeraforge.planner.hardware import REFERENCE_GPU, bandwidth_ratio, is_reference_hardware
from chimeraforge.planner.service import run_plan
from chimeraforge.validate import CLASS_LOOKUP, CLASS_ROOFLINE, classify

# Non-reference GPUs whose corpus rows do not exist, spanning a wide bandwidth
# range so the extrapolation factor is unmistakable.
FAR_GPUS = ["B200 180GB", "MI300X 192GB", "H100 80GB", "A100 80GB"]


def _ollama_fp16(gpu: str):
    r = run_plan(
        models=["llama3.2-3b"],
        hardware=gpu,
        budget=1e9,
        quality_target=0.0,
        allow_network=False,
    )
    return next(c for c in r.candidates if c.backend == "ollama" and c.quant == "FP16")


class TestReferenceHardware:
    def test_reference_gpu_is_itself(self):
        assert is_reference_hardware(REFERENCE_GPU)

    def test_substring_match_still_resolves(self):
        # get_gpu is substring-based, so the short form must not read as a
        # different card and silently downgrade a genuine measurement.
        assert is_reference_hardware("4080 12GB")

    @pytest.mark.parametrize("gpu", FAR_GPUS)
    def test_other_gpus_are_not_reference(self, gpu):
        assert not is_reference_hardware(gpu)

    def test_none_counts_as_reference(self):
        # No hardware means no scaling was applied, so the raw measurement stands.
        assert is_reference_hardware(None)

    def test_unknown_gpu_is_not_reference(self):
        """An unresolvable GPU must not inherit the reference badge -- failing open
        here is how the bug reached production in the first place."""
        assert not is_reference_hardware("RTX 9999 imaginary")


class TestThroughputLabel:
    def test_reference_gpu_keeps_measured(self):
        c = _ollama_fp16(REFERENCE_GPU)
        assert c.provenance["throughput"] == "measured"

    @pytest.mark.parametrize("gpu", FAR_GPUS)
    def test_other_gpus_are_extrapolated_not_measured(self, gpu):
        c = _ollama_fp16(gpu)
        assert c.provenance["throughput"] == "extrapolated", (
            f"{gpu} reports {c.provenance['throughput']!r}; the corpus has no row for "
            "this GPU, only a bandwidth-scaled reference measurement"
        )

    @pytest.mark.parametrize("gpu", FAR_GPUS)
    def test_the_extrapolation_is_disclosed_with_its_factor(self, gpu):
        c = _ollama_fp16(gpu)
        hits = [w for w in c.warnings if "extrapolation" in w]
        assert hits, f"{gpu} extrapolates silently"
        assert f"{bandwidth_ratio(gpu):.1f}x" in hits[0]
        assert REFERENCE_GPU in hits[0]

    def test_reference_gpu_does_not_warn(self):
        c = _ollama_fp16(REFERENCE_GPU)
        assert not any("extrapolation" in w for w in c.warnings)

    def test_the_scaled_value_really_does_differ(self):
        """Guards against the label being fixed while the value silently stops
        scaling -- then the label would be right for the wrong reason."""
        ref = _ollama_fp16(REFERENCE_GPU)
        far = _ollama_fp16("B200 180GB")
        assert far.throughput_tps > ref.throughput_tps * 5
        assert far.throughput_tps == pytest.approx(
            ref.throughput_tps * bandwidth_ratio("B200 180GB"), rel=0.02
        )


class TestDownstreamGuardsReArm:
    """Both were keyed off `== "measured"`, so the bug disabled them exactly where
    they mattered: on datacenter GPUs, which are never the reference rig."""

    def test_validate_does_not_file_extrapolated_as_in_sample(self):
        assert classify({"throughput": "measured"}) == CLASS_LOOKUP
        assert classify({"throughput": "extrapolated"}) == CLASS_ROOFLINE

    def test_fleet_reports_the_weaker_label_and_warns(self):
        from chimeraforge.planner.fleet import parse_fleet, plan_fleet

        plan = plan_fleet(
            parse_fleet("H100 80GB,A100 80GB,L4 24GB"),
            demand_rate=64.0,
            plan_fn=run_plan,
            plan_kwargs=dict(
                model_size="8b",
                latency_slo=5000.0,
                quality_target=0.0,
                budget=1e9,
                avg_tokens=128,
                context_length=2048,
            ),
        )
        assert plan.provenance()["throughput"] != "measured"
        assert any("compounds throughput error" in w for w in plan.warnings)

    def test_extrapolated_ranks_between_measured_and_estimated(self):
        # A real measurement scaled off the reference rig is better grounded than a
        # pure roofline, but it is not measurement of the card in hand.
        assert PROVENANCE_ORDER.index("measured") < PROVENANCE_ORDER.index("extrapolated")
        assert PROVENANCE_ORDER.index("extrapolated") < PROVENANCE_ORDER.index("estimated")

    def test_unrecognised_label_sorts_worst_rather_than_raising(self):
        """`.index()` on an unknown label used to raise ValueError, so any new
        provenance value would crash the fleet path instead of degrading."""
        from chimeraforge.planner.fleet import FleetPlan, GpuOption

        odd = GpuOption(
            gpu="odd",
            rate_per_gpu=1.0,
            cost_per_gpu_month=1.0,
            quant="FP16",
            backend="vllm",
            quality=0.5,
            vram_gb=1.0,
            throughput_tps=1.0,
            p95_latency_ms=1.0,
            provenance={"throughput": "brand-new-label"},
        )
        plan = FleetPlan(
            units={"odd": 1},
            options={"odd": odd},
            demand_rate=1.0,
            monthly_cost=1.0,
            served_rate=1.0,
        )
        assert plan.provenance()["throughput"] == PROVENANCE_ORDER[-1]


class TestBriefLabels:
    """The brief gave pure models and pure arithmetic the throughput label, so four
    rows read 'measured on the TR benchmark corpus' -- including a TTFT that is a
    FLOPs estimate nobody ever measured."""

    @pytest.fixture(scope="class")
    def rows(self):
        from chimeraforge.planner.brief import BriefInputs, build_brief

        r = run_plan(
            models=["llama3.2-3b"],
            hardware="H100 80GB",
            budget=1e9,
            quality_target=0.0,
            allow_network=False,
        )
        brief = build_brief(
            inputs=BriefInputs(hardware="H100 80GB", model="llama3.2-3b"),
            candidates=r.candidates,
        )
        return {m.label: m for m in brief.metrics}

    def test_vram_is_derived_not_measured(self, rows):
        # Weights + KV + activations is arithmetic over the architecture.
        assert rows["VRAM per GPU"].provenance == PROV_DERIVED

    @pytest.mark.parametrize("label", ["TTFT", "TPOT", "p95 latency"])
    def test_latency_rows_never_claim_measurement(self, rows, label):
        assert rows[label].provenance == "estimated"

    def test_no_row_claims_measurement_on_a_non_reference_gpu(self, rows):
        # Quality is a genuine corpus lookup and is hardware-independent, so it may
        # stay measured. Nothing derived from throughput may.
        for label in ("Throughput (fleet)", "p95 latency", "TTFT", "TPOT"):
            assert rows[label].provenance != "measured"

    def test_extrapolated_has_prose_and_a_marker(self):
        # A label with no phrase renders as the unknown fallback, which would
        # understate a real measurement; one with no marker reads as measured.
        assert "extrapolated" in PROVENANCE_PHRASE
        assert "bandwidth" in PROVENANCE_PHRASE["extrapolated"]
        assert PROVENANCE_MARK["extrapolated"] == "~"


class TestFormatterFailsClosed:
    """`provenance.get(key, "measured")` failed OPEN to the strongest claim, so a
    Candidate built without provenance rendered as '(measured)'."""

    def _bare_candidate(self):
        from chimeraforge.planner.engine import Candidate

        return Candidate(
            model="x",
            quant="FP16",
            backend="vllm",
            n_agents=1,
            vram_gb=8.0,
            quality=0.7,
            quality_tier="negligible",
            throughput_tps=100.0,
            total_throughput_tps=100.0,
            eta=1.0,
            p95_latency_ms=500.0,
            utilisation=0.5,
            monthly_cost=10.0,
            cost_per_1m_tok=0.1,
            safety_refusal=None,
            rtsi_risk="UNKNOWN",
            warnings=[],
        )

    def test_absent_provenance_renders_as_unknown_not_measured(self):
        import re

        from rich.console import Console

        from chimeraforge.planner import formatter

        cand = self._bare_candidate()
        assert cand.provenance == {}, "fixture must have no provenance at all"

        buf = Console(record=True, width=200, file=open(__import__("os").devnull, "w"))
        original = formatter.console
        formatter.console = buf
        try:
            formatter.format_recommendation(
                [cand],
                "RTX 4090 24GB",
                request_rate=1.0,
                latency_slo=5000.0,
                quality_target=0.5,
                budget=1000.0,
            )
        finally:
            formatter.console = original
        text = re.sub(r"\s+", " ", buf.export_text())
        assert "(measured)" not in text, "an absent label was rendered as measured"
        assert "(unknown)" in text
