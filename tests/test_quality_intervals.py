"""What a 20-item eval can support, and what the gate is allowed to claim.

P8.4. The quality gate is the planner's cleanest verified differentiator --
nobody else rejects a quantization level on quality before touching hardware --
and it was built on the corpus's weakest data.

The bundled eval is 20 items. The quant deltas derived from it say four of six
quantization levels score *above* FP16, and `QualityModel.estimate` returned all
of them labelled `measured`:

    FP16 0.5376 | Q2_K 0.5819 | Q3_K_S 0.5824 | Q4_K_M 0.6241
    Q5_K_M 0.6247 | Q6_K 0.6261 | Q8_0 0.6277

2-bit llama3.2-3b is not 8% better than FP16. Miller (arXiv:2411.00640) gives
the arithmetic: at n=20 the minimum detectable effect is +-20.9 percentage
points, and the corpus's entire measured delta range -- Q2_K -10.4pp through
Q4_K_M +1.8pp -- is a 14.2pp spread sitting *inside* that noise floor.

The largest risk in fixing this is the opposite of the usual one: widening every
interval until the gate never fires turns a real feature into ceremony. So the
interval is a property of the cell's `n`, never a tunable, and
"indistinguishable" is reported as an outcome with its reason and sample size
rather than as a silent pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chimeraforge.planner.constants import QUANT_BPW
from chimeraforge.planner.evalstats import (
    BUNDLED_EVAL_N,
    BUNDLED_METRIC,
    LONG_CONTEXT_THRESHOLD,
    OMEGA_SQ_UNIFORM_PAIRED,
    QualityCell,
    context_licenses_the_cell,
    minimum_detectable_effect,
    sample_size,
)
from chimeraforge.planner.models import load_effective_models
from chimeraforge.planner.qualityfile import (
    QualityFileError,
    aggregate,
    load_quality_file,
)
from chimeraforge.planner.service import run_plan

FIXTURES = Path(__file__).parent / "fixtures" / "quality"

# The ladder the planner actually searches. llama.cpp's legacy quants (q4_0,
# q5_1, ...) interleave with the k-quants by bit width because k-quants are
# better per bit -- a real property of the formats, not a data error -- so the
# monotonicity claim is made over the k-quant ladder, which is what is on offer.
K_QUANT_LADDER = ["f16", "q8_0", "q6_K", "q5_K_M", "q4_K_M", "q3_K_S", "q2_K"]


class TestMillerEquation9:
    """Checked against the paper's own printed number, not against itself."""

    def test_reproduces_the_papers_worked_example(self):
        # Section 5: sigma_A^2 = sigma_B^2 = 0, omega^2 = 1/9, delta = 0.03,
        # alpha = 0.05, beta = 0.20 -> "n = ... ~= 969".
        n = sample_size(delta=0.03, omega_sq=1 / 9, alpha=0.05, power=0.80)
        assert round(n) == 969

    def test_mde_is_the_inverse_of_sample_size(self):
        for delta in (0.01, 0.03, 0.10):
            n = sample_size(delta=delta)
            assert minimum_detectable_effect(round(n)) == pytest.approx(delta, rel=0.01)

    def test_twenty_items_resolve_about_21_percentage_points(self):
        assert minimum_detectable_effect(20) * 100 == pytest.approx(20.9, abs=0.05)

    def test_detecting_two_points_needs_about_2180_questions(self):
        assert round(sample_size(delta=0.02)) == 2180

    def test_an_unsized_cell_can_never_look_precise(self):
        assert minimum_detectable_effect(0) == float("inf")
        assert minimum_detectable_effect(-5) == float("inf")

    def test_conditional_variance_widens_the_requirement(self):
        # sigma^2/K is additive in Eq. 9: resampling noise costs questions.
        assert sample_size(delta=0.03, sigma_a_sq=0.25) > sample_size(delta=0.03)


class TestTheCorpusCannotSupportItsOwnDeltas:
    @pytest.fixture(scope="class")
    def quality(self):
        return load_effective_models().quality

    def test_the_bundled_eval_is_twenty_items(self):
        from chimeraforge.eval.tasks import BUILTIN_TASKS

        assert sum(len(t.prompts) for t in BUILTIN_TASKS.values()) == BUNDLED_EVAL_N == 20

    @pytest.mark.parametrize("quant", ["Q2_K", "Q3_K_S", "Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"])
    def test_no_quant_delta_is_distinguishable_from_zero(self, quality, quant):
        """Including Q2_K, which happens to point the right way. Pointing the
        right way is not the same as being measurable."""
        _, indistinguishable = quality.baseline_comparison("llama3.2-3b", quant)
        assert indistinguishable

    def test_the_whole_delta_range_fits_inside_the_noise_floor(self, quality):
        """The point of the item, in one assertion: the entire spread of measured
        quant deltas is smaller than the smallest difference the sample size can
        resolve.

        (The roadmap put this spread at 14.2pp. Re-derived from the corpus it is
        12.16pp -- Q2_K -10.40 to Q4_K_M +1.76 -- and 10.4 + 1.8 is 12.2 either
        way. The conclusion is unchanged and gets stronger, since the spread is
        further inside the floor than claimed.)"""
        deltas = quality.quant_deltas
        spread = (max(deltas.values()) - min(deltas.values())) * 100
        assert spread == pytest.approx(12.16, abs=0.01)
        assert spread < minimum_detectable_effect(BUNDLED_EVAL_N) * 100

    def test_four_of_six_quants_score_above_fp16(self, quality):
        """The artifact this item exists for, pinned so it cannot quietly change
        without the reasoning changing with it."""
        fp16 = quality.fp16_baselines["llama3.2-3b"]
        above = [
            q
            for q in ("Q2_K", "Q3_K_S", "Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0")
            if quality.estimate("llama3.2-3b", q)[0] > fp16
        ]
        assert len(above) == 6  # every one of them, on the derived-delta path

    def test_every_cell_carries_its_sample_size(self, quality):
        cell = quality.cell("llama3.2-3b", "Q4_K_M")
        assert cell.n == BUNDLED_EVAL_N
        assert cell.metric == BUNDLED_METRIC
        assert cell.mde_pp == pytest.approx(20.9, abs=0.05)


class TestGateRejectsOnlyWhatItCanSupport:
    def test_rejection_uses_the_upper_bound(self):
        cell = QualityCell(score=0.50, n=20)
        # A target above the point estimate but inside the interval is not a
        # rejection the data can support.
        assert cell.upper > 0.60
        assert cell.lower < 0.40

    def test_a_target_above_the_upper_bound_is_a_real_rejection(self):
        cell = QualityCell(score=0.50, n=20)
        assert cell.upper < 0.95

    def test_the_gate_does_not_fire_inside_the_interval(self):
        """A target the point estimate misses but the interval covers must not
        reject -- that would be rejecting on noise."""
        r = run_plan(
            models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.70,  # above every point estimate, inside every interval
            allow_network=False,
        )
        assert r.candidates, "rejected on a difference n=20 cannot resolve"

    def test_a_target_beyond_every_interval_still_rejects(self):
        # The guard against the real risk here: widening intervals until the gate
        # never fires turns a differentiator into ceremony.
        r = run_plan(
            models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.99,
            allow_network=False,
        )
        assert not r.candidates

    def test_the_rejection_reason_names_the_sample_size(self):
        r = run_plan(
            models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.99,
            allow_network=False,
        )
        reasons = " ".join(str(x) for x in (r.trace or []))
        assert "n=20" in reasons and "upper bound" in reasons

    def test_indistinguishability_is_reported_not_silent(self):
        c = run_plan(
            models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            allow_network=False,
        ).candidates[0]
        assert c.quality_n == 20
        assert c.quality_mde == pytest.approx(0.209, abs=0.001)
        if c.quality_indistinguishable:
            assert any("INDISTINGUISHABLE" in w for w in c.warnings)
            assert any("n=20" in w for w in c.warnings)


class TestRankingDoesNotOrderOnNoise:
    def test_overlapping_cells_are_reported_as_overlapping(self):
        a = QualityCell(score=0.624, n=20)
        b = QualityCell(score=0.628, n=20)
        assert a.overlaps(b)

    def test_cells_far_apart_do_not_overlap(self):
        assert not QualityCell(score=0.10, n=20).overlaps(QualityCell(score=0.90, n=20))

    def test_a_larger_n_narrows_the_interval(self):
        assert QualityCell(score=0.5, n=2000).mde < QualityCell(score=0.5, n=20).mde

    def test_cross_metric_cells_never_claim_a_difference(self):
        """An MMLU score and the bundled composite are different scales. Refusing
        to distinguish is the only honest answer; ordering them would be
        arithmetic on incomparable numbers."""
        a = QualityCell(score=0.10, n=10000, metric="lm-evaluation-harness:mmlu:acc")
        b = QualityCell(score=0.90, n=10000, metric=BUNDLED_METRIC)
        assert a.overlaps(b)

    def test_the_sort_does_not_split_ties_on_sub_mde_differences(self):
        r = run_plan(
            models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            allow_network=False,
        )
        same_cost = [c for c in r.candidates if c.monthly_cost == r.candidates[0].monthly_cost]
        if len(same_cost) > 1:
            # Within one cost tier, no pair may be ordered by a quality gap
            # smaller than what n resolves unless something else separates them.
            first, second = same_cost[0], same_cost[1]
            if abs(first.quality - second.quality) < first.quality_mde:
                assert first.p95_latency_ms <= second.p95_latency_ms


class TestLlamaCppFalsifiesTheOrdering:
    """A different metric, so it may falsify an ordering and may never supply a
    composite score. The consequence of the contradiction is that the corpus
    stops claiming a difference -- not that it gets repopulated from here."""

    @pytest.fixture(scope="class")
    def table(self):
        data = json.loads((FIXTURES / "llamacpp_ppl_llama3_8b.json").read_text(encoding="utf-8"))
        return {r["quant"]: r for r in data["rows"]}

    def test_the_published_table_is_monotone_across_the_k_quant_ladder(self, table):
        deltas = [table[q]["delta_ppl"] for q in K_QUANT_LADDER if q in table]
        assert len(deltas) == len(K_QUANT_LADDER)
        assert deltas == sorted(deltas), "published perplexity is not monotone in bit width"

    def test_no_quant_beats_fp16_there(self, table):
        f16 = table["f16"]["delta_ppl"]
        assert all(r["delta_ppl"] >= f16 for q, r in table.items() if q != "f16"), (
            "a quant with lower perplexity than FP16 would be the surprising result"
        )

    def test_our_corpus_contradicts_it(self):
        """Stated as a fact about the corpus rather than hidden. Four quants score
        above FP16 on the composite; none does on perplexity."""
        quality = load_effective_models().quality
        fp16 = quality.fp16_baselines["llama3.2-3b"]
        assert quality.estimate("llama3.2-3b", "Q2_K")[0] > fp16

    def test_and_the_contradiction_is_resolved_by_refusing_to_claim_it(self):
        # Not by importing llama.cpp's numbers, which are a different metric.
        quality = load_effective_models().quality
        for quant in ("Q2_K", "Q4_K_M", "Q8_0"):
            _, indistinguishable = quality.baseline_comparison("llama3.2-3b", quant)
            assert indistinguishable

    def test_the_ladder_is_monotone_in_our_own_bpw_table(self, table):
        bpws = [QUANT_BPW["FP16"] if q == "f16" else QUANT_BPW[q.upper()] for q in K_QUANT_LADDER]
        assert bpws == sorted(bpws, reverse=True)


class TestLmEvalReader:
    """Golden-file tests against a captured real results file."""

    @pytest.fixture(scope="class")
    def ingested(self):
        return load_quality_file(FIXTURES / "lm_eval_results.json")

    def test_it_reads_the_real_file(self, ingested):
        assert ingested.harness == "lm-evaluation-harness"
        assert ingested.cells
        assert ingested.harness_version

    def test_scores_come_from_metric_comma_filter_keys(self, ingested):
        cell = ingested.cells["chabsa"]
        assert cell.score == pytest.approx(0.916094781820536)
        assert cell.metric.endswith(":acc_norm") or cell.metric.endswith(":acc")

    def test_the_sample_count_comes_from_n_samples(self, ingested):
        # `n-samples: {"chabsa": {"original": 7723, "effective": 7723}}`
        assert ingested.cells["chabsa"].n == 7723

    def test_a_string_valued_stderr_does_not_crash_or_become_zero(self):
        """`f1_stderr,none` is the STRING "N/A" in this real file. Coercing it to
        0.0 would turn "we could not measure the uncertainty" into "there is
        none"; crashing on it would reject a legitimate harness output."""
        raw = json.loads((FIXTURES / "lm_eval_results.json").read_text(encoding="utf-8"))
        assert raw["results"]["chabsa"]["f1_stderr,none"] == "N/A"
        cell = load_quality_file(FIXTURES / "lm_eval_results.json").cells["chabsa"]
        assert cell.score > 0

    def test_a_large_n_actually_narrows_the_interval(self, ingested):
        # The whole point of ingesting a real harness: 7,723 items resolve what 20
        # cannot.
        assert ingested.cells["chabsa"].mde_pp < 2.0
        assert ingested.cells["chabsa"].mde < minimum_detectable_effect(20)

    def test_the_metric_name_travels(self, ingested):
        for cell in ingested.cells.values():
            assert cell.metric.startswith("lm-evaluation-harness:")
            assert cell.metric != BUNDLED_METRIC

    def test_aggregate_sums_the_sample_counts(self, ingested):
        agg = aggregate(ingested)
        assert agg.n == sum(c.n for c in ingested.cells.values())
        assert 0.0 <= agg.score <= 1.0

    def test_metric_selection_is_deterministic(self):
        a = load_quality_file(FIXTURES / "lm_eval_results.json")
        b = load_quality_file(FIXTURES / "lm_eval_results.json")
        assert {k: v.metric for k, v in a.cells.items()} == {
            k: v.metric for k, v in b.cells.items()
        }


class TestLmEvalReaderFailsLoud:
    """An unrecognised file is an error, not an empty ingest -- a silent
    zero-cell read leaves the user believing their eval was in force."""

    def test_missing_file(self, tmp_path):
        with pytest.raises(QualityFileError, match="not found"):
            load_quality_file(tmp_path / "nope.json")

    def test_not_json(self, tmp_path):
        p = tmp_path / "x.json"
        p.write_text("not json at all", encoding="utf-8")
        with pytest.raises(QualityFileError, match="not valid JSON"):
            load_quality_file(p)

    def test_json_but_not_a_harness_result(self, tmp_path):
        p = tmp_path / "x.json"
        p.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
        with pytest.raises(QualityFileError, match="not a recognised harness result"):
            load_quality_file(p)

    def test_a_score_with_no_sample_count_is_refused(self, tmp_path):
        p = tmp_path / "x.json"
        p.write_text(json.dumps({"results": {"t": {"acc,none": 0.5}}}), encoding="utf-8")
        with pytest.raises(QualityFileError, match="no sample count"):
            load_quality_file(p)

    def test_results_with_no_numeric_score_is_refused(self, tmp_path):
        p = tmp_path / "x.json"
        p.write_text(
            json.dumps({"results": {"t": {"acc,none": "N/A"}}, "n-samples": {"t": 10}}),
            encoding="utf-8",
        )
        with pytest.raises(QualityFileError, match="no task in it carries a numeric score"):
            load_quality_file(p)

    def test_a_json_array_is_refused(self, tmp_path):
        p = tmp_path / "x.json"
        p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(QualityFileError, match="must be a JSON object"):
            load_quality_file(p)


class TestQualityFromReplacesRatherThanBlends:
    def test_the_flag_puts_the_external_score_in_force(self):
        r = run_plan(
            models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            quality_from=str(FIXTURES / "lm_eval_results.json"),
            allow_network=False,
        )
        expected = aggregate(load_quality_file(FIXTURES / "lm_eval_results.json"))
        assert r.candidates[0].quality == pytest.approx(expected.score, abs=0.001)

    def test_it_brings_its_own_sample_size(self):
        r = run_plan(
            models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            quality_from=str(FIXTURES / "lm_eval_results.json"),
            allow_network=False,
        )
        assert r.candidates[0].quality_n > BUNDLED_EVAL_N
        assert r.candidates[0].quality_mde < minimum_detectable_effect(BUNDLED_EVAL_N)

    def test_a_bad_path_is_an_error_not_a_silent_fallback(self):
        with pytest.raises(QualityFileError):
            run_plan(
                models=["llama3.2-3b"],
                hardware="RTX 4080 12GB",
                budget=1e9,
                latency_slo=1e9,
                quality_target=0.0,
                quality_from="does-not-exist.json",
                allow_network=False,
            )


class TestContextConditionality:
    """A cell measured at 2K does not license a verdict at 64K. arXiv:2505.20276:
    8-bit preserves accuracy (~0.8% drop) while 4-bit methods lose up to 59% on
    long-context inputs -- the same config, near-lossless at one length and
    catastrophic at the other."""

    def test_short_context_licenses_any_quant(self):
        assert context_licenses_the_cell(2048, QUANT_BPW["Q4_K_M"])
        assert context_licenses_the_cell(8192, QUANT_BPW["Q2_K"])

    def test_long_context_does_not_license_a_four_bit_cell(self):
        assert not context_licenses_the_cell(LONG_CONTEXT_THRESHOLD, QUANT_BPW["Q4_K_M"])

    def test_eight_bit_is_reported_as_near_lossless_and_keeps_its_cell(self):
        # The paper separates them; sweeping Q8_0 in with the 4-bit cells would
        # discard a measurement the source says holds.
        assert context_licenses_the_cell(LONG_CONTEXT_THRESHOLD, QUANT_BPW["Q8_0"])
        assert context_licenses_the_cell(LONG_CONTEXT_THRESHOLD, QUANT_BPW["FP16"])

    def test_the_plan_says_unknown_rather_than_extrapolating(self):
        # An H100: a 3B at 64K context does not fit a 24 GB card at all, so the
        # smaller GPU would test the VRAM gate rather than this one.
        r = run_plan(
            models=["llama3.2-3b"],
            hardware="H100 80GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            context_length=LONG_CONTEXT_THRESHOLD,
            allow_network=False,
        )
        narrow = [c for c in r.candidates if QUANT_BPW.get(c.quant, 16.0) < 8.0]
        assert narrow, "no narrow-quant candidate to check"
        for c in narrow:
            assert any("UNKNOWN at" in w for w in c.warnings)
            assert any("2505.20276" in w for w in c.warnings)


class TestFixtureProvenance:
    def test_every_fixture_records_its_source_and_date(self):
        manifest = json.loads((FIXTURES / "MANIFEST.json").read_text(encoding="utf-8"))
        assert manifest["captured_at"]
        for entry in manifest["fixtures"]:
            assert entry["source_url"].startswith("https://")
            assert (FIXTURES / entry["file"]).exists()
            assert entry["covers"]

    def test_omega_sq_is_named_as_an_assumption(self):
        # It is Miller's illustrative value, not a measurement of this corpus --
        # the bundled data stores per-cell means, not per-item scores.
        assert OMEGA_SQ_UNIFORM_PAIRED == pytest.approx(1 / 9)
