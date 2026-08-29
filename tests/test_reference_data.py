"""Tests for the reference rig's specification and the corpus's provenance.

Batch D of an adversarial review. Both findings concern the data everything else
is measured against.

`REFERENCE_GPU` is the denominator of every cross-GPU extrapolation and of
`MBU_DEFAULT`, and it carried 556 GB/s / 285 W -- figures belonging to neither
the card the corpus was measured on (an RTX 4080 **Laptop**: 192-bit, 432 GB/s,
60-150 W TGP) nor the desktop RTX 4080 (717 GB/s, 320 W). Every number derived
from that denominator was wrong by ~29%.

And `fitted_models.json` -- the file that decides which numbers are allowed to
say `measured` -- shipped with no `captured_at`, no source and no coverage
statement, while `api_pricing.json` next to it has all three and expires.
"""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.constants import MBU_DEFAULT
from chimeraforge.planner.hardware import GPU_DB, REFERENCE_GPU, bandwidth_ratio
from chimeraforge.planner.models import load_bundled_models

# The llama3.2-1b ollama FP16 datapoint MBU_DEFAULT is calibrated from.
CALIBRATION_TPS = 146.33
CALIBRATION_WEIGHT_GB = 2.48


@pytest.fixture(scope="module")
def corpus() -> dict:
    import importlib.resources as resources

    return json.loads(
        resources.files("chimeraforge.planner.data")
        .joinpath("fitted_models.json")
        .read_text(encoding="utf-8")
    )


class TestReferenceGpuMatchesTheActualRig:
    def test_bandwidth_is_the_laptop_part(self):
        """192-bit GDDR6 at 18 Gbps. NVIDIA publishes 12 GB on a 192-bit bus for
        the RTX 4080 Laptop GPU; no desktop RTX 4080 12GB exists (the desktop card
        is 16 GB), and the rig pairs it with an i9-13900HX, a mobile part."""
        assert GPU_DB[REFERENCE_GPU].bandwidth_gbps == 432.0

    def test_tdp_is_within_the_published_tgp_range(self):
        # NVIDIA publishes 60-150 W TGP for this part. 285 W was a desktop figure.
        tdp = GPU_DB[REFERENCE_GPU].tdp_watts
        assert 60.0 <= tdp <= 150.0

    def test_it_is_not_confusable_with_the_desktop_card(self):
        desktop = GPU_DB["RTX 4080 16GB"]
        assert GPU_DB[REFERENCE_GPU].bandwidth_gbps < desktop.bandwidth_gbps
        assert GPU_DB[REFERENCE_GPU].tdp_watts < desktop.tdp_watts

    def test_the_reference_ratio_is_unity(self):
        assert bandwidth_ratio(REFERENCE_GPU) == pytest.approx(1.0)


class TestMbuIsConsistentWithThatBandwidth:
    def test_mbu_is_back_solved_from_the_calibration_point(self):
        """MBU is not a free parameter: it is the one value that reproduces the
        measured 146.33 tok/s at the reference card's real bandwidth. It read 0.65
        only because the denominator was wrong."""
        ref_bw = GPU_DB[REFERENCE_GPU].bandwidth_gbps
        implied = CALIBRATION_TPS / (ref_bw / CALIBRATION_WEIGHT_GB)
        assert MBU_DEFAULT == pytest.approx(implied, abs=0.01)

    def test_mbu_is_physically_possible(self):
        # A utilisation above 1.0 would mean exceeding the memory bus.
        assert 0.0 < MBU_DEFAULT <= 1.0

    def test_the_reference_roofline_is_unchanged_by_the_correction(self):
        """The invariant that makes this correction safe: only the denominator
        moved, so MBU * bandwidth is the same product it always was, and the
        reference card's own prediction is bit-for-bit what it was before."""
        models = load_bundled_models()
        got = models.throughput.roofline_tps(1.24, "FP16", REFERENCE_GPU)
        assert got == pytest.approx(CALIBRATION_TPS, rel=0.01)

    def test_other_gpus_scale_from_the_corrected_basis(self):
        """The rig was achieving 84% of its real bandwidth, not 65% of a bandwidth
        it does not have -- so assuming equal MBU elsewhere predicts more, not less."""
        assert bandwidth_ratio("H100 80GB") == pytest.approx(
            GPU_DB["H100 80GB"].bandwidth_gbps / 432.0, rel=1e-6
        )
        assert bandwidth_ratio("H100 80GB") > 7.0


class TestCorpusCarriesItsProvenance:
    """CLAUDE.md: 'A dataset without a captured_at and a source is not shippable.'
    This is the dataset that decides which numbers may say `measured`."""

    def test_has_a_provenance_block(self, corpus):
        assert "_provenance" in corpus

    @pytest.mark.parametrize(
        "field", ["schema_version", "captured_at", "source", "method", "reference_hardware"]
    )
    def test_required_fields(self, corpus, field):
        assert corpus["_provenance"][field]

    def test_captured_at_is_a_real_date(self, corpus):
        import datetime as dt

        dt.date.fromisoformat(corpus["_provenance"]["captured_at"])

    def test_reference_hardware_names_the_laptop_part(self, corpus):
        ref = corpus["_provenance"]["reference_hardware"]
        assert "Laptop" in ref
        assert "432" in ref, "the bandwidth the whole corpus is scaled from"

    def test_coverage_matches_the_file_it_describes(self, corpus):
        """A coverage claim that drifts from the data is worse than none."""
        cov = corpus["_provenance"]["coverage"]
        lookup = corpus["throughput"]["lookup"]
        assert cov["throughput_rows"] == len(lookup)
        assert cov["throughput_models"] == sorted({k.split("|")[0] for k in lookup})
        assert cov["throughput_backends"] == sorted({k.split("|")[1] for k in lookup})
        assert cov["throughput_quants"] == sorted({k.split("|")[2] for k in lookup})
        assert cov["quality_cells"] == len(corpus["quality"]["lookup"])
        assert cov["safety_cells"] == len(corpus["safety"]["lookup"])

    def test_the_fp16_only_limitation_is_stated_and_true(self, corpus):
        """Every quantized throughput number in the product is an FP16 row times a
        multiplier. That is a large claim to leave implicit."""
        quants = {k.split("|")[2] for k in corpus["throughput"]["lookup"]}
        assert quants == {"FP16"}
        assert any("FP16" in lim for lim in corpus["_provenance"]["limitations"])

    def test_the_missing_regeneration_script_is_declared_not_faked(self, corpus):
        """Two sibling datasets are script-generated; this one is not. Recording
        the gap is honest -- shipping a stub script that cannot regenerate it
        would not be."""
        from pathlib import Path

        note = corpus["_provenance"]["regeneration"]
        assert "NOT yet regenerable" in note
        root = Path(__file__).resolve().parents[1]
        assert not (root / "scripts" / "build_fitted_models.py").exists(), (
            "the script now exists, so the provenance note is stale"
        )
        # The siblings it is being compared against really do exist.
        assert (root / "scripts" / "build_cost_data.py").exists()
        assert (root / "scripts" / "build_safety_data.py").exists()

    def test_the_block_does_not_disturb_the_loader(self):
        models = load_bundled_models()
        assert len(models.throughput.lookup) == 23
        assert models.vram.fitted
