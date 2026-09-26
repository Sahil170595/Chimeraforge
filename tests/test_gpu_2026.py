"""P8.6 item 6: the 2026 parts, and what a missing vendor figure must mean.

Every value below was read from a vendor page or datasheet (URL per entry in
data/hardware.json) and re-checked for four parts against the live source. They
are typed here, not read from the dataset, so an edit to the dataset has to
agree with a reviewed test.

The second half pins a bug the new parts would otherwise have inherited: a
field the vendor does not publish was read as zero, and zero is a value -- a
spec with no FP16 figure reported TTFT 0.0 ms, and one with no price reported
$0/month labelled `derived`, sorted first and passed any budget.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.hardware import GPU_DB, get_gpu, match_driver_name
from chimeraforge.planner.service import run_plan

# name: (vram_gb, bandwidth_gbps, fp16_tflops or None, tflops_basis, tdp or None,
#        interconnect_gbps, fp8_supported)
PARTS_2026 = {
    "RTX PRO 6000 Blackwell Workstation 96GB": (
        96.0,
        1792.0,
        503.8,
        "fp32-accumulate-dense",
        600.0,
        128.0,
        True,
    ),
    "RTX PRO 6000 Blackwell Max-Q 96GB": (
        96.0,
        1792.0,
        438.9,
        "fp32-accumulate-dense",
        300.0,
        128.0,
        True,
    ),
    "RTX PRO 6000 Blackwell Server 96GB": (
        96.0,
        1597.0,
        None,
        "unlabeled-by-vendor",
        600.0,
        128.0,
        True,
    ),
    "MI325X 256GB": (256.0, 6000.0, 1307.4, "dense", 1000.0, 896.0, True),
    "MI350X 288GB": (288.0, 8000.0, 2309.6, "dense", 1000.0, 1075.2, True),
    "MI355X 288GB": (288.0, 8000.0, 2516.6, "dense", 1400.0, 1075.2, True),
    "MI455X 432GB": (432.0, 23300.0, 5033.0, "dense", None, 3600.0, True),
    "Arc Pro B60 24GB": (24.0, 456.0, None, "not-published", 200.0, 64.0, False),
    "Arc Pro B65 32GB": (32.0, 608.0, None, "not-published", 200.0, 128.0, False),
    "RX 9070 16GB": (16.0, 640.0, 145.0, "dense", 220.0, 128.0, True),
    "RX 9070 XT 16GB": (16.0, 640.0, 195.0, "dense", 304.0, 128.0, True),
    "RX 9060 XT 16GB": (16.0, 320.0, 103.0, "dense", 160.0, 128.0, True),
    "Radeon AI PRO R9700 32GB": (32.0, 640.0, 191.0, "dense", 300.0, 128.0, True),
}

# Vendor suggested prices (AMD press releases), amortised over the stated hours.
AMD_SEP = {"RX 9070 16GB": 549.0, "RX 9070 XT 16GB": 599.0, "RX 9060 XT 16GB": 349.0}


class TestThe2026PartsAreThere:
    @pytest.mark.parametrize("name", sorted(PARTS_2026))
    def test_vendor_figures(self, name):
        vram, bw, tflops, basis, tdp, link, fp8 = PARTS_2026[name]
        spec = GPU_DB[name]
        assert spec.vram_gb == vram
        assert spec.bandwidth_gbps == bw
        assert spec.fp16_tflops == (tflops or 0.0)
        assert spec.tflops_basis == basis
        assert spec.tdp_watts == (tdp or 0.0)
        assert spec.interconnect_gbps == link
        assert spec.fp8_supported is fp8
        assert spec.source_url.startswith("https://")
        assert spec.captured_at == "2026-09-25"

    def test_mi325x_dense_fp16_matches_mi300x_same_cdna3_compute(self):
        """Cross-check that the dense column was read, not the sparse one."""
        assert abs(GPU_DB["MI325X 256GB"].fp16_tflops - GPU_DB["MI300X 192GB"].fp16_tflops) < 1.0

    def test_an_unlabeled_headline_is_not_halved_into_a_dense_figure(self):
        """NVIDIA prints '1 PFLOP' FP16 for the Server Edition with no dense/sparse
        label. Halving it would be a guess; it stays unknown."""
        assert GPU_DB["RTX PRO 6000 Blackwell Server 96GB"].fp16_tflops == 0.0

    def test_mi430x_is_excluded_as_not_yet_shipping(self):
        assert not any("MI430X" in name for name in GPU_DB)

    @pytest.mark.parametrize("name,sep", sorted(AMD_SEP.items()))
    def test_consumer_price_is_the_vendor_sep_amortised(self, name, sep):
        from chimeraforge.planner.hardware import AMORTISATION_HOURS

        assert GPU_DB[name].price_basis == "amortised-purchase"
        assert GPU_DB[name].cost_per_hour == pytest.approx(round(sep / AMORTISATION_HOURS, 4))

    @pytest.mark.parametrize(
        "name",
        [n for n in PARTS_2026 if n not in AMD_SEP],
    )
    def test_no_vendor_price_means_no_price(self, name):
        assert GPU_DB[name].cost_per_hour == 0.0


class TestLookupStaysUnambiguous:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("RX 9070 XT", "RX 9070 XT 16GB"),
            ("RX 9070 16GB", "RX 9070 16GB"),
            ("MI355X", "MI355X 288GB"),
            ("MI300X", "MI300X 192GB"),
            ("RTX 4070", "RTX 4070 12GB"),
            ("B200", "B200 180GB"),
        ],
    )
    def test_get_gpu(self, query, expected):
        assert get_gpu(query).name == expected

    @pytest.mark.parametrize(
        "driver,expected",
        [
            (
                "NVIDIA RTX PRO 6000 Blackwell Workstation Edition",
                "RTX PRO 6000 Blackwell Workstation 96GB",
            ),
            (
                "NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition",
                "RTX PRO 6000 Blackwell Max-Q 96GB",
            ),
            ("NVIDIA RTX PRO 6000 Blackwell Server Edition", "RTX PRO 6000 Blackwell Server 96GB"),
        ],
    )
    def test_driver_names_pick_the_right_variant(self, driver, expected):
        assert match_driver_name(driver, 96.0).name == expected


def _plan(hardware, **kw):
    base = dict(
        model_size="8b",
        hardware=hardware,
        quality_target=0.0,
        budget=1e9,
        latency_slo=1e9,
        allow_network=False,
    )
    base.update(kw)
    return run_plan(**base)


class TestUnknownIsNotZero:
    def test_no_price_is_refused_at_the_budget_gate_not_priced_at_zero(self):
        plan = _plan("MI355X")
        assert not plan.candidates
        budget = [t for t in plan.trace if t[2] == "budget"]
        assert budget and "--gpu-price-per-hour" in budget[0][3]

    def test_a_supplied_price_makes_the_part_plannable(self):
        plan = _plan("MI355X", gpu_overrides={"cost_per_hour": 3.0})
        assert plan.candidates and all(c.monthly_cost > 0 for c in plan.candidates)

    def test_user_supplied_card_without_price_is_refused_too(self):
        plan = _plan("RTX 6090 48GB", gpu_overrides={"vram_gb": 48, "bandwidth_gbps": 1300})
        assert not plan.candidates
        assert any(t[2] == "budget" for t in plan.trace)

    def test_no_fp16_figure_reports_a_ttft_floor_not_zero(self):
        plan = _plan("Arc Pro B60", gpu_overrides={"cost_per_hour": 0.02})
        assert plan.candidates
        for c in plan.candidates:
            assert c.ttft_ms > 0, "TTFT 0.0 ms is a claim, not an unknown"
            assert any("no vendor dense FP16" in w for w in c.warnings)

    def test_an_explicit_ttft_slo_cannot_be_verified_without_compute(self):
        plan = _plan("Arc Pro B60", gpu_overrides={"cost_per_hour": 0.02}, ttft_slo=10_000)
        assert not plan.candidates
        assert any("TTFT" in t[3] and "FP16" in t[3] for t in plan.trace)

    def test_known_parts_are_unaffected(self):
        plan = _plan("RTX 4090 24GB")
        assert plan.candidates
        assert not any("no vendor dense FP16" in w for c in plan.candidates for w in c.warnings)


class TestListingsSayUnknown:
    def test_mcp_list_hardware_reports_null_not_zero(self):
        from chimeraforge.mcp_server import list_hardware

        rows = {g["name"]: g for g in list_hardware()["gpus"]}
        assert rows["MI355X 288GB"]["cost_per_hour_usd"] is None
        assert rows["Arc Pro B60 24GB"]["fp16_tflops"] is None
        assert rows["MI455X 432GB"]["tdp_watts"] is None
        assert rows["RTX 4090 24GB"]["cost_per_hour_usd"] == 0.06

    def test_cli_listing_says_unknown(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(app, ["plan", "--list-hardware", "--json"])
        assert r.exit_code == 0, r.output
        import json

        rows = {g["name"]: g for g in json.loads(r.output)}
        assert rows["MI355X 288GB"]["cost_per_hour"] is None
