"""Hardware as a resolved, sourced, overridable input.

P8.6. Three problems with one root cause: the GPU table was the last hand-typed
dataset in the product, and it drives more of the answer than any other, since
decode is modelled as bandwidth-bound.

* **No provenance.** 22 `GPUSpec` literals with a prose comment block -- no
  `captured_at`, no per-entry source URL, no regeneration path. That is the
  project's own house rule ("A dataset without a `captured_at` and a source is
  not shippable") unmet in the dataset that matters most.
* **A hard wall.** `plan --hardware "RTX 6090 48GB"` exited 1 with a list of
  known GPUs. Failing loud was right, but the planner is *model*-agnostic by
  design and was *hardware*-locked by accident: an unreleased model can be
  planned with `--params-b`, and an unlisted GPU could not be planned at all.
* **One field, two quantities.** `cost_per_hour`'s own comment said datacenter
  values are "approximate on-demand cloud rates" and consumer values are
  "amortised card cost". Those are not the same thing, and the field drives the
  budget gate, `$/1M-tok`, and the self-host-vs-API break-even.

The migration's central property is that **nothing moved**: every value the old
literals carried is the value the dataset carries, so no plan changes on the
refactor alone. A spec correction would be a separate, arguable thing, and
mixing it into a migration would hide it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chimeraforge.planner.hardware import (
    AUTO_HARDWARE,
    GPU_DB,
    GPU_OVERRIDE_FIELDS,
    GPU_OVERRIDE_REQUIRED,
    PRICE_BASIS_AMORTISED,
    PRICE_BASIS_MARKETPLACE,
    PRICE_BASIS_PHRASE,
    REFERENCE_GPU,
    GPUSpec,
    HardwareError,
    bandwidth_ratio,
    match_driver_name,
    resolve_hardware,
    spec_from_overrides,
)
from chimeraforge.planner.service import run_plan

DATASET = (
    Path(__file__).parent.parent / "src" / "chimeraforge" / "planner" / "data" / "hardware.json"
)

# Every value the hand-typed table carried, transcribed here so the migration is
# checked against the OLD numbers rather than against the file it produced.
# (name, vram_gb, bandwidth_gbps, cost_per_hour, fp16_tflops, tdp_watts,
#  interconnect_gbps, fp8_supported)
LEGACY = [
    ("RTX 4060 8GB", 8.0, 272.0, 0.020, 30.2, 115.0, 64.0, True),
    ("RTX 4060 Ti 8GB", 8.0, 288.0, 0.025, 44.1, 160.0, 64.0, True),
    ("RTX 4060 Ti 16GB", 16.0, 288.0, 0.030, 44.1, 165.0, 64.0, True),
    ("RTX 4070 12GB", 12.0, 504.0, 0.030, 58.4, 200.0, 64.0, True),
    ("RTX 4070 Ti 12GB", 12.0, 504.0, 0.035, 80.2, 285.0, 64.0, True),
    ("RTX 4080 12GB", 12.0, 432.0, 0.035, 67.7, 150.0, 64.0, True),
    ("RTX 4080 16GB", 16.0, 717.0, 0.045, 97.5, 320.0, 64.0, True),
    ("RTX 4090 24GB", 24.0, 1008.0, 0.060, 165.2, 450.0, 64.0, True),
    ("RTX 5070 12GB", 12.0, 672.0, 0.030, 61.7, 250.0, 128.0, True),
    ("RTX 5070 Ti 16GB", 16.0, 896.0, 0.038, 87.9, 300.0, 128.0, True),
    ("RTX 5080 16GB", 16.0, 960.0, 0.045, 112.6, 360.0, 128.0, True),
    ("RTX 5090 32GB", 32.0, 1792.0, 0.075, 209.5, 575.0, 128.0, True),
    ("RTX 3090 24GB", 24.0, 936.0, 0.040, 71.0, 350.0, 64.0, False),
    ("RTX 3080 10GB", 10.0, 760.0, 0.025, 59.5, 320.0, 64.0, False),
    ("A100 40GB", 40.0, 1555.0, 1.10, 312.0, 400.0, 600.0, False),
    ("A100 80GB", 80.0, 2039.0, 1.60, 312.0, 400.0, 600.0, False),
    ("H100 80GB", 80.0, 3352.0, 2.50, 989.0, 700.0, 900.0, True),
    ("H200 141GB", 141.0, 4800.0, 3.50, 989.0, 700.0, 900.0, True),
    ("B200 180GB", 180.0, 7700.0, 5.50, 2250.0, 1000.0, 1800.0, True),
    ("L4 24GB", 24.0, 300.0, 0.50, 121.0, 72.0, 64.0, True),
    ("T4 16GB", 16.0, 320.0, 0.35, 65.0, 70.0, 64.0, False),
    ("MI300X 192GB", 192.0, 5300.0, 2.00, 1307.0, 750.0, 896.0, True),
]


class TestMigrationChangedNothing:
    """The property the whole item hangs on. If a number moved here, a plan moved,
    and it moved for a reason nobody reviewed."""

    def test_the_same_gpus_are_present(self):
        assert set(GPU_DB) == {row[0] for row in LEGACY}
        assert len(GPU_DB) == 22

    @pytest.mark.parametrize("row", LEGACY, ids=[r[0] for r in LEGACY])
    def test_every_field_survives(self, row):
        name, vram, bw, cost, tflops, tdp, link, fp8 = row
        spec = GPU_DB[name]
        assert spec.vram_gb == vram
        assert spec.bandwidth_gbps == bw
        assert spec.cost_per_hour == cost
        assert spec.fp16_tflops == tflops
        assert spec.tdp_watts == tdp
        assert spec.interconnect_gbps == link
        assert spec.fp8_supported is fp8

    def test_the_reference_gpu_is_still_the_denominator(self):
        # Every cross-GPU extrapolation and MBU_DEFAULT are anchored here.
        assert bandwidth_ratio(REFERENCE_GPU) == 1.0
        assert GPU_DB[REFERENCE_GPU].bandwidth_gbps == 432.0

    def test_a_plan_on_the_reference_rig_still_resolves(self):
        r = run_plan(
            models=["llama3.2-3b"],
            hardware=REFERENCE_GPU,
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            allow_network=False,
        )
        assert r.candidates


class TestDatasetProvenance:
    @pytest.fixture(scope="class")
    def data(self):
        return json.loads(DATASET.read_text(encoding="utf-8"))

    def test_the_dataset_is_dated(self, data):
        assert data["captured_at"]
        assert data["schema_version"] == 1

    def test_every_entry_names_a_source_and_a_date(self, data):
        for entry in data["gpus"]:
            assert entry["source_url"].startswith("https://"), entry["name"]
            assert entry["captured_at"], entry["name"]

    def test_the_build_script_validates_the_bundled_file(self):
        # The validator is the gate, so it has to actually pass on what shipped.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_hardware_data",
            Path(__file__).parent.parent / "scripts" / "build_hardware_data.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.validate(json.loads(DATASET.read_text(encoding="utf-8")))

    def test_the_script_regenerates_exactly_what_shipped(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_hardware_data",
            Path(__file__).parent.parent / "scripts" / "build_hardware_data.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.build() == json.loads(DATASET.read_text(encoding="utf-8"))

    def test_a_value_outside_its_bounds_fails_the_build(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_hardware_data",
            Path(__file__).parent.parent / "scripts" / "build_hardware_data.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bad = json.loads(DATASET.read_text(encoding="utf-8"))
        bad["gpus"][0]["bandwidth_gbps"] = 999999.0
        with pytest.raises(module.ValidationError, match="outside"):
            module.validate(bad)

    def test_a_missing_source_url_fails_the_build(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_hardware_data",
            Path(__file__).parent.parent / "scripts" / "build_hardware_data.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bad = json.loads(DATASET.read_text(encoding="utf-8"))
        bad["gpus"][0]["source_url"] = "http://example.com"
        with pytest.raises(module.ValidationError, match="https"):
            module.validate(bad)


class TestPriceBasisIsNotOneField:
    """An amortised purchase price and a rental rate answer different questions."""

    def test_consumer_cards_are_amortised_purchases(self):
        assert GPU_DB["RTX 4090 24GB"].price_basis == PRICE_BASIS_AMORTISED

    def test_datacenter_cards_are_labelled_marketplace_not_on_demand(self):
        """H100 at $2.50/hr and B200 at $5.50/hr track GPU marketplace rates,
        roughly 4-5x below hyperscaler on-demand. The comment claimed on-demand.
        Relabelled to what they are rather than changed -- changing them is a
        pricing decision, and this is a migration."""
        assert GPU_DB["H100 80GB"].price_basis == PRICE_BASIS_MARKETPLACE
        assert GPU_DB["B200 180GB"].price_basis == PRICE_BASIS_MARKETPLACE
        assert GPU_DB["H100 80GB"].cost_per_hour == 2.50

    def test_every_basis_in_use_has_a_phrase(self):
        # A bare dollar figure means two different things; the plan has to be able
        # to say which, so a basis with no prose is unshippable.
        for spec in GPU_DB.values():
            assert spec.price_basis in PRICE_BASIS_PHRASE

    def test_the_plan_states_which_basis_it_priced_against(self):
        c = run_plan(
            models=["llama3.2-3b"],
            hardware="H100 80GB",
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            allow_network=False,
        ).candidates[0]
        assert any("marketplace" in w for w in c.warnings)
        assert any("GPU-hour" in w for w in c.warnings)


class TestTflopsBasisTravels:
    def test_a_halved_sparse_figure_is_labelled_as_one(self):
        # B200's datasheet prints only a with-sparsity FP16 number (4500); 2250 is
        # that halved. Defensible, but not a datasheet row.
        assert GPU_DB["B200 180GB"].tflops_basis == "halved-with-sparsity"

    def test_a_datasheet_row_is_labelled_dense(self):
        # MI300X's sheet prints the dense 1307 directly, so halving would be wrong.
        assert GPU_DB["MI300X 192GB"].tflops_basis == "dense"
        assert GPU_DB["MI300X 192GB"].fp16_tflops == 1307.0

    def test_consumer_parts_are_labelled_derived(self):
        assert GPU_DB["RTX 4090 24GB"].tflops_basis == "derived-2x-fp32"


class TestUnlistedGpusAreNoLongerAWall:
    def test_a_card_with_the_required_figures_resolves(self):
        spec, warnings = resolve_hardware(
            "RTX 6090 48GB", {"vram_gb": 48.0, "bandwidth_gbps": 1300.0, "tdp_watts": 300.0}
        )
        assert spec.vram_gb == 48.0
        assert spec.bandwidth_gbps == 1300.0
        assert spec.user_supplied is True
        assert warnings and "not in the GPU database" in warnings[0]

    def test_it_can_actually_be_planned(self):
        r = run_plan(
            models=["llama3.2-3b"],
            hardware="RTX 6090 48GB",
            gpu_overrides={"vram_gb": 48.0, "bandwidth_gbps": 1300.0},
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            allow_network=False,
        )
        assert r.candidates

    @pytest.mark.parametrize("missing", GPU_OVERRIDE_REQUIRED)
    def test_the_minimum_fields_are_required(self, missing):
        overrides = {"vram_gb": 48.0, "bandwidth_gbps": 1300.0}
        overrides.pop(missing)
        with pytest.raises(HardwareError, match=GPU_OVERRIDE_FIELDS[missing]):
            resolve_hardware("RTX 6090 48GB", overrides)

    def test_an_unsupplied_field_is_unknown_not_the_reference_cards_value(self):
        """The latent silent default this closes: `bandwidth_ratio()` returns 1.0
        for an unknown GPU and the roofline fell back to the reference card's
        bandwidth. A field nobody supplied must read as unknown."""
        spec = spec_from_overrides("X", {"vram_gb": 48.0, "bandwidth_gbps": 1300.0})
        assert spec.fp16_tflops == 0.0
        assert spec.tdp_watts == 0.0
        assert spec.interconnect_gbps == 0.0
        assert spec.bandwidth_gbps != GPU_DB[REFERENCE_GPU].bandwidth_gbps

    def test_fp8_is_refused_rather_than_assumed_on_an_unlisted_card(self):
        # FP8 support is not knowable from vram+bandwidth, and offering it on a
        # part that emulates it hands out a config that does not run.
        spec = spec_from_overrides("X", {"vram_gb": 48.0, "bandwidth_gbps": 1300.0})
        assert spec.fp8_supported is False

    def test_the_error_for_an_unlisted_card_now_points_at_the_way_out(self):
        with pytest.raises(ValueError, match="--gpu-vram-gb"):
            run_plan(
                models=["llama3.2-3b"],
                hardware="RTX 6090 48GB",
                budget=1e9,
                latency_slo=1e9,
                quality_target=0.0,
                allow_network=False,
            )


class TestOverridingAKnownCard:
    def test_an_override_wins_and_says_so(self):
        spec, warnings = resolve_hardware("H100 80GB", {"cost_per_hour": 8.0})
        assert spec.cost_per_hour == 8.0
        assert spec.user_supplied is True
        assert any("--gpu-price-per-hour" in w for w in warnings)

    def test_an_override_clears_the_provenance_it_no_longer_has(self):
        # The entry is now the user's claim, so it must not keep citing a vendor
        # page for a figure that page does not carry.
        spec, _ = resolve_hardware("H100 80GB", {"bandwidth_gbps": 4000.0})
        assert spec.source_url == ""
        assert spec.captured_at == ""

    def test_unoverridden_fields_are_kept(self):
        spec, _ = resolve_hardware("H100 80GB", {"cost_per_hour": 8.0})
        assert spec.vram_gb == 80.0
        assert spec.bandwidth_gbps == 3352.0

    def test_no_override_is_the_bundled_spec_unchanged(self):
        spec, warnings = resolve_hardware("H100 80GB")
        assert spec is GPU_DB["H100 80GB"]
        assert warnings == []

    def test_supplying_a_known_cards_own_figures_reproduces_its_plan(self):
        """The migration property, from the other direction: overrides that match
        the dataset must not change the answer."""
        known = GPU_DB["RTX 4090 24GB"]
        kw = dict(
            models=["llama3.2-3b"],
            budget=1e9,
            latency_slo=1e9,
            quality_target=0.0,
            allow_network=False,
        )
        plain = run_plan(hardware="RTX 4090 24GB", **kw).candidates[0]
        overridden = run_plan(
            hardware="RTX 4090 24GB",
            gpu_overrides={
                "vram_gb": known.vram_gb,
                "bandwidth_gbps": known.bandwidth_gbps,
                "fp16_tflops": known.fp16_tflops,
                "tdp_watts": known.tdp_watts,
                "interconnect_gbps": known.interconnect_gbps,
                "cost_per_hour": known.cost_per_hour,
            },
            **kw,
        ).candidates[0]
        assert overridden.vram_gb == plain.vram_gb
        assert overridden.throughput_tps == plain.throughput_tps
        assert overridden.monthly_cost == plain.monthly_cost


class TestAutoDetection:
    def test_auto_reports_a_match_when_the_driver_names_a_known_card(self, monkeypatch):
        monkeypatch.setattr(
            "chimeraforge.planner.hardware.detect_local_gpu",
            lambda: ("NVIDIA GeForce RTX 4090", 24.0),
        )
        spec, warnings = resolve_hardware(AUTO_HARDWARE)
        assert spec.name == "RTX 4090 24GB"
        assert any("auto detected" in w for w in warnings)

    def test_auto_on_an_unmatched_device_refuses_rather_than_guessing_bandwidth(self, monkeypatch):
        """The driver reports VRAM; it does not report memory bandwidth. Inferring
        it from the name would produce a confident plan for a card nobody sized."""
        monkeypatch.setattr(
            "chimeraforge.planner.hardware.detect_local_gpu",
            lambda: ("NVIDIA Imaginary 9000", 48.0),
        )
        with pytest.raises(HardwareError, match="--gpu-bandwidth-gbps"):
            resolve_hardware(AUTO_HARDWARE)

    def test_auto_plus_a_supplied_bandwidth_uses_the_driver_vram(self, monkeypatch):
        monkeypatch.setattr(
            "chimeraforge.planner.hardware.detect_local_gpu",
            lambda: ("NVIDIA Imaginary 9000", 48.0),
        )
        spec, warnings = resolve_hardware(AUTO_HARDWARE, {"bandwidth_gbps": 1300.0})
        assert spec.vram_gb == 48.0
        assert spec.bandwidth_gbps == 1300.0
        assert spec.user_supplied is True
        assert any("driver's figure" in w for w in warnings)

    def test_auto_with_no_gpu_is_an_actionable_error(self, monkeypatch):
        monkeypatch.setattr("chimeraforge.planner.hardware.detect_local_gpu", lambda: None)
        with pytest.raises(HardwareError, match="found no NVIDIA GPU"):
            resolve_hardware(AUTO_HARDWARE)

    def test_detect_returns_none_rather_than_raising_without_a_driver(self):
        # Never an exception on an ordinary machine: absence of a GPU is a fact,
        # not a failure.
        from chimeraforge.planner.hardware import detect_local_gpu

        result = detect_local_gpu()
        assert result is None or (isinstance(result, tuple) and len(result) == 2)


class TestDriverNameMatching:
    """`get_gpu` is a substring match in either direction, and neither
    "NVIDIA GeForce RTX 4090" nor "RTX 4090 24GB" contains the other -- so
    `--hardware auto` would have failed to recognise the most common consumer
    card in the database."""

    @pytest.mark.parametrize(
        "driver,vram,expected",
        [
            ("NVIDIA GeForce RTX 4090", 24.0, "RTX 4090 24GB"),
            ("NVIDIA GeForce RTX 5090", 32.0, "RTX 5090 32GB"),
            ("NVIDIA A100-SXM4-80GB", 80.0, "A100 80GB"),
            ("NVIDIA A100-PCIE-40GB", 40.0, "A100 40GB"),
            ("NVIDIA H100 80GB HBM3", 80.0, "H100 80GB"),
            ("Tesla T4", 16.0, "T4 16GB"),
            ("NVIDIA L4", 24.0, "L4 24GB"),
        ],
    )
    def test_real_driver_name_shapes(self, driver, vram, expected):
        assert match_driver_name(driver, vram).name == expected

    def test_a_longer_model_wins_over_its_own_prefix(self):
        # "RTX 4060" is a prefix of "RTX 4060 Ti"; the Ti driver must not be
        # claimed by the non-Ti entry, which has different compute and TDP.
        assert match_driver_name("NVIDIA GeForce RTX 4060 Ti", 16.0).name == "RTX 4060 Ti 16GB"
        assert match_driver_name("NVIDIA GeForce RTX 4060", 8.0).name == "RTX 4060 8GB"

    def test_vram_disambiguates_two_capacities_of_one_model(self):
        assert match_driver_name("NVIDIA GeForce RTX 4060 Ti", 8.0).name == "RTX 4060 Ti 8GB"
        assert match_driver_name("NVIDIA GeForce RTX 4060 Ti", 16.0).name == "RTX 4060 Ti 16GB"

    def test_an_ambiguous_model_without_vram_is_not_matched(self):
        # Guessing 8 GB for a 16 GB card silently halves every VRAM verdict.
        assert match_driver_name("NVIDIA GeForce RTX 4060 Ti", None) is None

    def test_an_unknown_card_matches_nothing(self):
        assert match_driver_name("NVIDIA Imaginary 9000", 48.0) is None

    def test_an_empty_name_matches_nothing(self):
        assert match_driver_name("", 24.0) is None
        assert match_driver_name("   ", 24.0) is None


class TestGpuSpecDefaults:
    def test_a_hand_built_spec_cannot_silently_claim_a_cloud_rate(self):
        spec = GPUSpec("X", 24.0, 1000.0, 0.05)
        assert spec.price_basis == PRICE_BASIS_AMORTISED
        assert spec.user_supplied is False
        assert spec.source_url == ""
