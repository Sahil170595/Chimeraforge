"""What each provenance class is allowed to claim, and what it must carry.

P8.1. Two classes were missing and their absence was not cosmetic.

`derived` -- exact arithmetic over the inputs and the GPU database -- existed in
`brief.py` and was never emitted by the engine, so VRAM shipped labelled
`measured`. That cites the TR benchmark corpus as the source of a number the
corpus never measured: nobody weighed those bytes, they were multiplied out of an
architecture.

`extrapolated` existed but as a bare adjective. To a reader skimming a table it
lands as *stronger* than `estimated` -- its own definition contains the word
"measured" -- so the rule is that it may never appear without the anchor that
makes it self-describing. Checking that anchor turned up a second defect
underneath: three bundled rows sit above the memory-bandwidth ceiling and get
clamped, so `measured_tps x ratio` is not the reported number for them, and an
anchor offering only those two fields would have published a product that does
not reconstruct.

See `test_provenance_labels.py` for the cross-GPU labelling defect this builds on.
"""

from __future__ import annotations

import json

import pytest

from chimeraforge.mcp_server import _candidate_summary
from chimeraforge.planner.brief import PROVENANCE_PHRASE
from chimeraforge.planner.hardware import GPU_DB, REFERENCE_GPU, bandwidth_ratio
from chimeraforge.planner.provenance import (
    PROV_DERIVED,
    PROV_MEASURED,
    PROVENANCE_LEGEND,
    PROVENANCE_MARK,
    PROVENANCE_ORDER,
    from_corpus_row,
    prov_anchor,
    prov_class,
    prov_mark,
    worst,
)
from chimeraforge.planner.service import run_plan
from chimeraforge.validate import CLASS_EXTRAPOLATED, CLASS_ORDER


def _plan(gpu: str):
    """The ollama/FP16 config, which is the one with a bundled corpus row.

    The cheapest candidate is usually a quant with no measured row, so ranking
    on cost would test the `estimated` path everywhere and never exercise the
    lookup this module is about. Falls back to the winner where FP16 does not fit.
    """
    r = run_plan(
        models=["llama3.2-3b"],
        hardware=gpu,
        budget=1e9,
        quality_target=0.0,
        allow_network=False,
    )
    hits = [c for c in r.candidates if c.backend == "ollama" and c.quant == "FP16"]
    return hits[0] if hits else r.candidates[0]


class TestProvClassReader:
    """Every consumer reads a label through `prov_class`, so what it does with a
    value it cannot place decides how the whole product fails."""

    def test_reads_both_shapes(self):
        assert prov_class("measured") == "measured"
        assert prov_class({"class": "measured"}) == "measured"

    @pytest.mark.parametrize("value", [None, 0, "", "totally-made-up", {}, {"class": "nope"}, []])
    def test_unplaceable_values_fail_to_unknown_not_measured(self, value):
        # Failing OPEN here is how a confidently-wrong badge reaches a user: a
        # payload with a field this code cannot interpret must never render as
        # the strongest available claim.
        assert prov_class(value) == "unknown"

    def test_anchor_is_empty_for_a_bare_label(self):
        assert prov_anchor("measured") == {}
        assert prov_anchor(None) == {}

    def test_anchor_excludes_the_class_itself(self):
        assert prov_anchor({"class": "extrapolated", "ratio": 2.0}) == {"ratio": 2.0}


class TestDerivedIsNotMeasured:
    """VRAM is arithmetic. Filing it under `measured` attributed it to a benchmark."""

    def test_vram_is_derived(self):
        c = _plan(REFERENCE_GPU)
        assert prov_class(c.provenance["vram"]) == PROV_DERIVED
        assert prov_class(c.provenance["vram"]) != PROV_MEASURED

    def test_derived_names_the_arithmetic(self):
        # `derived` alone is as bare an adjective as `extrapolated` was.
        basis = prov_anchor(_plan(REFERENCE_GPU).provenance["vram"])["basis"]
        assert "KV-cache" in basis and "weights" in basis

    def test_cost_is_derived(self):
        # The bill is GPU-hours x a dated price snapshot: exact given its inputs,
        # and never measured.
        assert prov_class(_plan(REFERENCE_GPU).provenance["cost"]) == PROV_DERIVED

    def test_derived_ranks_with_measured_not_below_estimated(self):
        # A fleet takes the worst class across its GPU types. If `derived` sorted
        # as weak, adding it would have silently downgraded every mixed plan.
        assert worst([PROV_DERIVED, PROV_MEASURED]) == PROV_MEASURED
        assert worst([PROV_DERIVED, "estimated"]) == "estimated"
        assert worst([PROV_DERIVED]) == PROV_DERIVED

    def test_derived_is_not_marked_as_uncertain(self):
        assert PROVENANCE_MARK[PROV_DERIVED] == ""


class TestEveryNonReferenceGpuIsExtrapolated:
    """No threshold, no exceptions: any bandwidth_ratio != 1.0 is a transport."""

    @pytest.mark.parametrize("gpu", sorted(GPU_DB))
    def test_no_gpu_off_the_reference_rig_claims_measured(self, gpu):
        if bandwidth_ratio(gpu) == 1.0:
            return
        c = _plan(gpu)
        assert prov_class(c.provenance["throughput"]) != PROV_MEASURED, (
            f"{gpu} claims a measurement; the corpus has no row for it"
        )

    @pytest.mark.parametrize("gpu", sorted(GPU_DB))
    def test_every_extrapolation_names_where_it_came_from(self, gpu):
        c = _plan(gpu)
        if prov_class(c.provenance["throughput"]) != "extrapolated":
            return
        anchor = prov_anchor(c.provenance["throughput"])
        assert anchor["measured_on"] == REFERENCE_GPU
        assert anchor["ratio"] == pytest.approx(bandwidth_ratio(gpu), rel=1e-3)
        assert anchor["basis"] == "memory bandwidth"


class TestFromCorpusRowArithmetic:
    """The builder, checked directly, so the rules read without running a plan."""

    def test_untouched_row_is_a_bare_measurement(self):
        value = from_corpus_row(measured_on="X", measured_tps=100.0, ratio=1.0, reported_tps=100.0)
        assert value == PROV_MEASURED

    def test_transport_alone_is_extrapolated(self):
        v = from_corpus_row(measured_on="X", measured_tps=100.0, ratio=2.0, reported_tps=200.0)
        assert v["class"] == "extrapolated"
        assert "clamped_to_bandwidth_ceiling" not in v
        assert v["measured_tps"] * v["ratio"] == pytest.approx(200.0)

    def test_clamp_alone_stays_measured_but_discloses(self):
        # The basis is still a real measurement of this card; what changed is
        # that the reported figure is the physical ceiling instead of the row.
        v = from_corpus_row(measured_on="X", measured_tps=100.0, ratio=1.0, reported_tps=70.0)
        assert v["class"] == PROV_MEASURED
        assert v["clamped_to_bandwidth_ceiling"] is True
        assert v["reported_tps"] == 70.0
        assert "ratio" not in v

    def test_both_are_disclosed_together(self):
        v = from_corpus_row(measured_on="X", measured_tps=100.0, ratio=2.0, reported_tps=140.0)
        assert v["class"] == "extrapolated"
        assert v["ratio"] == 2.0
        assert v["clamped_to_bandwidth_ceiling"] is True

    def test_a_non_binding_clamp_is_not_reported_as_one(self):
        # Float noise must not manufacture a disclosure; equality is not a clamp.
        v = from_corpus_row(
            measured_on="X", measured_tps=100.0, ratio=3.0, reported_tps=300.0000000001
        )
        assert "clamped_to_bandwidth_ceiling" not in v


class TestRenderSitesCannotOutrunTheEvidence:
    def test_every_class_has_a_phrase(self):
        # A phrase lookup that fell through to a default would render a new class
        # as an unqualified sentence, in the document people read instead of JSON.
        for cls in PROVENANCE_ORDER:
            assert cls in PROVENANCE_PHRASE, f"{cls} would render unqualified in a brief"
            assert PROVENANCE_PHRASE[cls].strip()

    def test_every_class_has_a_mark(self):
        for cls in PROVENANCE_ORDER:
            assert cls in PROVENANCE_MARK

    def test_extrapolated_does_not_share_the_estimated_mark(self):
        assert PROVENANCE_MARK["extrapolated"] != PROVENANCE_MARK["estimated"]

    def test_every_mark_that_means_something_is_in_the_legend(self):
        # A glyph with no legend entry is an unexplained assertion.
        for cls, mark in PROVENANCE_MARK.items():
            if mark:
                assert mark in PROVENANCE_LEGEND, f"{cls} renders {mark!r} with no legend"

    def test_prov_mark_accepts_the_anchored_form(self):
        anchored = {"class": "extrapolated", "ratio": 2.0}
        assert prov_mark(anchored) == PROVENANCE_MARK["extrapolated"]


class TestValidateClassing:
    def test_extrapolated_has_its_own_audit_class(self):
        assert CLASS_EXTRAPOLATED in CLASS_ORDER

    def test_audit_reports_it_between_roofline_and_lookup(self):
        # Ordering is presentation, but it encodes the claim strength the report
        # narrates, so it is pinned rather than left to import order.
        order = list(CLASS_ORDER)
        assert order.index("roofline-estimate") < order.index(CLASS_EXTRAPOLATED)
        assert order.index(CLASS_EXTRAPOLATED) < order.index("measured-lookup")


class TestMcpPayloadRoundTrip:
    """The MCP payload is what an assistant reads and repeats to a user, so the
    anchor has to survive serialization intact rather than being flattened."""

    @pytest.mark.parametrize("gpu", [REFERENCE_GPU, "B200 180GB"])
    def test_payload_is_json_and_keeps_the_class(self, gpu):
        payload = _candidate_summary(_plan(gpu))
        prov = json.loads(json.dumps(payload))["provenance"]
        assert prov_class(prov["vram"]) == PROV_DERIVED
        assert prov_class(prov["throughput"]) in ("measured", "extrapolated")
        assert prov_class(prov["cost"]) == PROV_DERIVED

    def test_payload_keeps_the_anchor(self):
        payload = _candidate_summary(_plan("B200 180GB"))
        anchor = prov_anchor(json.loads(json.dumps(payload))["provenance"]["throughput"])
        assert anchor["measured_on"] == REFERENCE_GPU
        assert isinstance(anchor["ratio"], float)

    def test_every_provenance_value_is_a_plain_json_type(self):
        for value in _candidate_summary(_plan("B200 180GB"))["provenance"].values():
            assert isinstance(value, (str, dict))
            if isinstance(value, dict):
                assert all(isinstance(v, (str, float, int, bool)) for v in value.values())
