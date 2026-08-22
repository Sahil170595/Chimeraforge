"""Tests for the decision-report artifact (`plan --report`).

The brief reuses numbers the planner already computed, so the risk is not the
arithmetic -- it is the prose. A formatted document reads as more durable than a
terminal line, so two properties are load-bearing and both are asserted here:
every reported number carries a provenance phrase, and a stale price snapshot is a
refusal rather than a nicer font.
"""

from __future__ import annotations

import re

import pytest

from chimeraforge.planner.brief import (
    PROV_DERIVED,
    PROVENANCE_MARK,
    PROVENANCE_PHRASE,
    Brief,
    BriefError,
    BriefInputs,
    build_brief,
    render_markdown,
)
from chimeraforge.planner.service import run_plan


@pytest.fixture(scope="module")
def plan_result():
    return run_plan(
        model_size="8b", hardware="RTX 4090 24GB", request_rate=2.0, budget=5000, avg_tokens=128
    )


@pytest.fixture
def inputs():
    return BriefInputs(
        hardware="RTX 4090 24GB",
        model_size="8b",
        request_rate=2.0,
        budget_usd_month=5000,
    )


@pytest.fixture
def brief(plan_result, inputs):
    return build_brief(inputs=inputs, candidates=plan_result.candidates, generated_at="2026-08-21")


def _fresh_api(**over) -> dict:
    base = {
        "self_host_monthly_usd": 43.2,
        "requests_per_month": 5_184_000,
        "prompt_tokens": 512,
        "output_tokens": 128,
        "prices_captured_at": "2026-08-18",
        "prices_age_days": 3,
        "prices_stale": False,
        "sources": {"anthropic": "https://example.invalid"},
        "options": [
            {
                "key": "anthropic:x",
                "provider": "anthropic",
                "name": "Model X",
                "class": "frontier",
                "input_per_1m_usd": 3.0,
                "output_per_1m_usd": 15.0,
                "monthly_cost_usd": 17_000.0,
                "cost_per_request_usd": 0.0033,
                "breakeven_output_tokens_month": 1_234_567,
                "self_host_cheaper": True,
            }
        ],
    }
    base.update(over)
    return base


class TestProvenanceDiscipline:
    def test_every_metric_row_has_a_known_provenance(self, brief):
        for m in brief.metrics:
            assert m.provenance in PROVENANCE_PHRASE, (
                f"metric {m.label!r} carries provenance {m.provenance!r}, which has no "
                "phrase -- it would render an unqualified number"
            )

    def test_every_metric_row_renders_its_phrase(self, brief):
        md = render_markdown(brief)
        for m in brief.metrics:
            assert PROVENANCE_PHRASE[m.provenance] in md

    def test_no_metric_row_is_unlabeled(self, brief):
        assert brief.metrics
        assert all(m.provenance for m in brief.metrics)

    def test_estimates_are_marked_in_the_table(self, brief):
        est = [m for m in brief.metrics if m.provenance == "estimated"]
        assert est, "an 8B plan on a 4090 should have at least one estimated number"
        assert all(m.marked.startswith("~") for m in est)

    def test_measured_values_are_unmarked(self, brief):
        for m in brief.metrics:
            if m.provenance == "measured":
                assert not m.marked.startswith(("~", "?"))

    def test_gpu_count_is_not_claimed_as_measured(self, brief):
        """The GPU count comes from the search, not the TR corpus. Labeling it
        `measured` would cite a benchmark that never measured it."""
        row = next(m for m in brief.metrics if m.label == "GPUs")
        assert row.provenance == PROV_DERIVED

    def test_cost_is_not_claimed_as_measured(self, brief):
        # Cost is a list price times hours -- arithmetic, not a benchmark result.
        row = next(m for m in brief.metrics if m.label == "Cost")
        assert row.provenance == PROV_DERIVED
        assert "excludes engineering time" in row.note

    def test_unknown_provenance_gets_a_warning_phrase(self):
        assert "unvalidated" in PROVENANCE_PHRASE["unknown"]
        assert PROVENANCE_MARK["unknown"] == "?"

    def test_every_number_in_the_metric_table_is_qualified(self, brief):
        """Rule test: walk the rendered metric table and require a phrase on each
        row. A number added to the template without one is the whole failure mode."""
        md = render_markdown(brief)
        table = md.split("| Metric | Value | Provenance |")[1].split("\n\n")[0]
        rows = [r for r in table.splitlines() if r.startswith("| ") and "---" not in r]
        assert rows
        phrases = tuple(PROVENANCE_PHRASE.values())
        for row in rows:
            assert any(p in row for p in phrases), f"unqualified row: {row}"


class TestStaleRefusal:
    def test_fresh_snapshot_renders(self, plan_result, inputs):
        b = build_brief(
            inputs=inputs, candidates=plan_result.candidates, api_comparison=_fresh_api()
        )
        assert "Self-host vs hosted API" in render_markdown(b)

    def test_stale_snapshot_refuses(self, plan_result, inputs):
        with pytest.raises(BriefError, match="refusing to render"):
            build_brief(
                inputs=inputs,
                candidates=plan_result.candidates,
                api_comparison=_fresh_api(prices_stale=True, prices_age_days=400),
            )

    def test_refusal_says_how_to_fix_it(self, plan_result, inputs):
        with pytest.raises(BriefError) as exc:
            build_brief(
                inputs=inputs,
                candidates=plan_result.candidates,
                api_comparison=_fresh_api(prices_stale=True, prices_age_days=400),
            )
        msg = str(exc.value)
        assert "400 days old" in msg
        assert "build_api_pricing" in msg and "--compare-api" in msg

    def test_no_candidates_refuses_rather_than_rendering_an_empty_brief(self, inputs):
        with pytest.raises(BriefError, match="nothing to recommend"):
            build_brief(inputs=inputs, candidates=[])

    def test_capture_date_appears_in_the_api_section(self, plan_result, inputs):
        md = render_markdown(
            build_brief(
                inputs=inputs, candidates=plan_result.candidates, api_comparison=_fresh_api()
            )
        )
        assert "2026-08-18" in md and "3 days old" in md


class TestReproCommand:
    def test_defaults_are_omitted(self):
        cmd = BriefInputs(hardware="RTX 4090 24GB", model_size="8b").repro_command()
        assert "--request-rate" not in cmd
        assert "--kv-quant" not in cmd

    def test_non_defaults_are_present(self):
        cmd = BriefInputs(
            hardware="RTX 4090 24GB",
            model_size="8b",
            request_rate=2.0,
            budget_usd_month=5000,
            workload="agent",
            kv_quant="q8",
        ).repro_command()
        for token in ("--request-rate 2", "--budget 5000", "--workload agent", "--kv-quant q8"):
            assert token in cmd

    def test_hardware_with_spaces_is_quoted(self):
        cmd = BriefInputs(hardware="RTX 4090 24GB").repro_command()
        assert "'RTX 4090 24GB'" in cmd

    def test_explicit_model_wins_over_size_class(self):
        cmd = BriefInputs(hardware="H100 80GB", model="Qwen/Qwen3-8B").repro_command()
        assert "--model Qwen/Qwen3-8B" in cmd
        assert "--model-size" not in cmd

    def test_repeated_model_flag_round_trips(self):
        # `plan --model` is repeatable, so the CLI hands a list through. Building the
        # command by concatenating it raised a TypeError only at render time -- after
        # the plan had already run and the user was waiting on a file.
        cmd = BriefInputs(hardware="H100 80GB", model=["a/b", "c/d"]).repro_command()
        assert cmd.count("--model ") == 2
        assert "a/b" in cmd and "c/d" in cmd
        assert "[" not in cmd

    def test_single_model_string_still_works(self):
        assert BriefInputs(hardware="H100 80GB", model="a/b").models == ["a/b"]

    def test_none_valued_flags_are_never_emitted(self):
        cmd = BriefInputs(hardware="H100 80GB").repro_command()
        assert "None" not in cmd

    def test_command_actually_runs_and_reproduces_the_plan(self, plan_result, inputs):
        """A repro command that does not reproduce is worse than none: it invites a
        reader to trust a document they cannot check."""
        import shlex

        from typer.testing import CliRunner

        from chimeraforge.cli import app

        argv = shlex.split(inputs.repro_command())
        assert argv[:2] == ["chimeraforge", "plan"]
        r = CliRunner().invoke(app, argv[1:] + ["--json"])
        assert r.exit_code == 0, r.output
        import json

        got = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert got
        want = plan_result.candidates[0]
        assert got[0]["model"] == want.model
        assert got[0]["quant"] == want.quant
        assert got[0]["backend"] == want.backend


class TestRenderedContent:
    def test_has_a_generation_date_and_version(self, brief):
        md = render_markdown(brief)
        assert "2026-08-21" in md
        assert brief.tool_version in md

    def test_warnings_are_reproduced_verbatim(self, plan_result, inputs):
        b = build_brief(inputs=inputs, candidates=plan_result.candidates)
        md = render_markdown(b)
        for w in b.warnings:
            assert w in md, "a warning was paraphrased or dropped in the brief"

    def test_assumptions_are_labeled_as_inputs_not_findings(self, brief):
        md = render_markdown(brief)
        assert "Each line is an input, not a finding" in md

    def test_alternatives_table_present(self, brief):
        md = render_markdown(brief)
        if brief.alternatives:
            assert "Alternatives considered" in md
            for c in brief.alternatives:
                assert c.backend in md

    def test_launch_command_included_when_given(self, plan_result, inputs):
        b = build_brief(
            inputs=inputs,
            candidates=plan_result.candidates,
            launch={"backend": "vllm", "command": "vllm serve x", "env": [], "notes": ["n1"]},
        )
        md = render_markdown(b)
        assert "vllm serve x" in md and "n1" in md

    def test_no_naked_placeholder_left_in_the_template(self, brief):
        md = render_markdown(brief)
        assert not re.search(r"\{[a-z_]+\}", md), "an unformatted template slot survived"

    def test_to_dict_is_serializable(self, brief):
        import json

        d = brief.to_dict()
        assert json.loads(json.dumps(d))
        assert d["schema_version"] == 1
        assert d["repro_command"].startswith("chimeraforge plan")
        assert all("provenance" in m for m in d["metrics"])

    def test_brief_is_a_brief(self, brief):
        assert isinstance(brief, Brief)


class TestPlanCliReport:
    def _run(self, tmp_path, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        out = tmp_path / "brief.md"
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
                "--report",
                str(out),
                *args,
            ],
        )
        return r, out

    def test_writes_the_file(self, tmp_path):
        r, out = self._run(tmp_path)
        assert r.exit_code == 0, r.output
        assert out.exists()
        assert out.read_text(encoding="utf-8").startswith("# Deployment brief:")

    def test_reports_where_it_wrote(self, tmp_path):
        r, out = self._run(tmp_path)
        assert "Decision brief written to" in r.output

    def test_no_flag_writes_nothing(self, tmp_path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(app, ["plan", "--model-size", "8b", "--hardware", "RTX 4090 24GB"])
        assert r.exit_code == 0
        assert not list(tmp_path.iterdir())

    def test_infeasible_plan_exits_nonzero_without_writing(self, tmp_path):
        """A CI job that asks for a brief must fail rather than continue with no
        file where one was expected."""
        r, out = self._run(tmp_path, "--budget", "0.0001")
        assert r.exit_code == 1
        assert not out.exists()
        assert "Brief not written" in r.output

    def test_records_the_parallelism_actually_chosen(self, tmp_path):
        """--tp auto resolves to a degree during the search, so the brief must record
        the degree that ran. Recording "auto" would make the repro command depend on a
        search whose inputs (the corpus, the GPU DB) can move underneath it."""
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        out = tmp_path / "tp.md"
        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model",
                "meta-llama/Llama-3.1-405B-Instruct",
                "--hardware",
                "H100 80GB",
                "--tp",
                "auto",
                "--budget",
                "1e9",
                "--latency-slo",
                "60000",
                "--no-network",
                "--params-b",
                "405",
                "--n-layers",
                "126",
                "--n-kv-heads",
                "8",
                "--d-head",
                "128",
                "--report",
                str(out),
            ],
        )
        assert r.exit_code == 0, r.output[-800:]
        text = out.read_text(encoding="utf-8")
        # 405B cannot fit one 80GB card at any offered format, so auto must have
        # resolved to a real degree -- and the brief must record that, not "auto".
        assert "--tensor-parallel auto" not in text
        assert re.search(r"--tensor-parallel [2-9]", text), text.split("## Reproduce")[-1]
