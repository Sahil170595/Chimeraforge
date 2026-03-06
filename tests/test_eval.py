"""ChimeraForge Eval — unit tests.

Tests quality metrics (exact match, ROUGE-L, BERTScore, coherence,
composite, tiers), built-in tasks, runner, and CLI integration.

Run:
    pytest tests/test_eval.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# TestExactMatch
# ---------------------------------------------------------------------------


class TestExactMatch:
    def test_perfect_match(self):
        from chimeraforge.eval.metrics import compute_exact_match

        preds = ["Paris", "1945", "H2O"]
        refs = ["Paris", "1945", "H2O"]
        assert compute_exact_match(preds, refs) == 1.0

    def test_no_match(self):
        from chimeraforge.eval.metrics import compute_exact_match

        preds = ["London", "1944", "CO2"]
        refs = ["Paris", "1945", "H2O"]
        assert compute_exact_match(preds, refs) == 0.0

    def test_case_insensitive(self):
        from chimeraforge.eval.metrics import compute_exact_match

        preds = ["paris", "PARIS"]
        refs = ["Paris", "paris"]
        assert compute_exact_match(preds, refs) == 1.0

    def test_empty_lists(self):
        from chimeraforge.eval.metrics import compute_exact_match

        assert compute_exact_match([], []) == 0.0


# ---------------------------------------------------------------------------
# TestRougeL
# ---------------------------------------------------------------------------


class TestRougeL:
    def test_identical_strings(self):
        from chimeraforge.eval.metrics import compute_rouge_l

        preds = ["the cat sat on the mat"]
        refs = ["the cat sat on the mat"]
        assert compute_rouge_l(preds, refs) == pytest.approx(1.0)

    def test_partial_overlap(self):
        from chimeraforge.eval.metrics import compute_rouge_l

        preds = ["the cat sat"]
        refs = ["the cat sat on the mat"]
        score = compute_rouge_l(preds, refs)
        assert 0.0 < score < 1.0

    def test_empty_returns_zero(self):
        from chimeraforge.eval.metrics import compute_rouge_l

        assert compute_rouge_l([], ["something"]) == 0.0


# ---------------------------------------------------------------------------
# TestBERTScore
# ---------------------------------------------------------------------------


class TestBERTScore:
    def test_returns_valid_score(self):
        from chimeraforge.eval.metrics import compute_bert_score

        # If evaluate + bert-score installed, returns actual score;
        # otherwise warns and returns 0.0.
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            score = compute_bert_score(["hello"], ["hello"])
        assert -0.01 <= score <= 1.01  # BERTScore can slightly exceed 1.0 due to FP precision

    def test_empty_returns_zero(self):
        from chimeraforge.eval.metrics import compute_bert_score

        assert compute_bert_score([], []) == 0.0


# ---------------------------------------------------------------------------
# TestCoherence
# ---------------------------------------------------------------------------


class TestCoherence:
    def test_identical_lengths(self):
        from chimeraforge.eval.metrics import compute_coherence

        preds = ["hello world"]
        refs = ["hello world"]
        assert compute_coherence(preds, refs) == 1.0

    def test_very_different_lengths(self):
        from chimeraforge.eval.metrics import compute_coherence

        preds = ["hi"]
        refs = ["this is a much longer reference text with many words"]
        score = compute_coherence(preds, refs)
        assert 0.0 < score < 0.5

    def test_both_empty_strings(self):
        from chimeraforge.eval.metrics import compute_coherence

        assert compute_coherence([""], [""]) == 1.0

    def test_one_empty_string(self):
        from chimeraforge.eval.metrics import compute_coherence

        assert compute_coherence([""], ["hello"]) == 0.0


# ---------------------------------------------------------------------------
# TestComposite
# ---------------------------------------------------------------------------


class TestComposite:
    def test_all_ones(self):
        from chimeraforge.eval.metrics import compute_composite

        assert compute_composite(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0)

    def test_all_zeros(self):
        from chimeraforge.eval.metrics import compute_composite

        assert compute_composite(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)

    def test_bert_zero_redistributes(self):
        from chimeraforge.eval.metrics import compute_composite

        # When bert_score=0: 0.2*em + 0.6*rouge + 0.2*coh
        result = compute_composite(1.0, 1.0, 0.0, 1.0)
        assert result == pytest.approx(1.0)

    def test_normal_weights(self):
        from chimeraforge.eval.metrics import compute_composite

        # 0.2*0.5 + 0.3*0.6 + 0.3*0.7 + 0.2*0.8 = 0.1 + 0.18 + 0.21 + 0.16 = 0.65
        result = compute_composite(0.5, 0.6, 0.7, 0.8)
        assert result == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# TestClassifyTier
# ---------------------------------------------------------------------------


class TestClassifyTier:
    def test_negligible(self):
        from chimeraforge.eval.metrics import classify_tier

        # No drop -> negligible
        assert classify_tier(1.0, 1.0) == "negligible"

    def test_acceptable(self):
        from chimeraforge.eval.metrics import classify_tier

        # 5pp drop -> acceptable
        assert classify_tier(0.95, 1.0) == "acceptable"

    def test_concerning(self):
        from chimeraforge.eval.metrics import classify_tier

        # 12pp drop -> concerning
        assert classify_tier(0.88, 1.0) == "concerning"

    def test_unacceptable(self):
        from chimeraforge.eval.metrics import classify_tier

        # 20pp drop -> unacceptable
        assert classify_tier(0.80, 1.0) == "unacceptable"

    def test_zero_baseline_returns_unknown(self):
        from chimeraforge.eval.metrics import classify_tier

        assert classify_tier(0.5, 0.0) == "unknown"

    def test_boundary_negligible(self):
        from chimeraforge.eval.metrics import classify_tier

        # Exactly -3pp -> negligible (>= -3)
        assert classify_tier(0.97, 1.0) == "negligible"


# ---------------------------------------------------------------------------
# TestEvaluateQuality
# ---------------------------------------------------------------------------


class TestEvaluateQuality:
    def test_returns_quality_score(self):
        from chimeraforge.eval.metrics import evaluate_quality

        preds = ["Paris", "1945"]
        refs = ["Paris", "1945"]
        qs = evaluate_quality(preds, refs, model="test", quant="FP16")
        assert qs.model == "test"
        assert qs.quant == "FP16"
        assert qs.exact_match == 1.0
        assert qs.n_samples == 2

    def test_tier_with_fp16_baseline(self):
        from chimeraforge.eval.metrics import evaluate_quality

        qs = evaluate_quality(
            ["Paris"],
            ["Paris"],
            model="test",
            quant="Q4_K_M",
            fp16_composite=1.0,
        )
        assert qs.tier in ("negligible", "acceptable", "concerning", "unacceptable")


# ---------------------------------------------------------------------------
# TestTasks
# ---------------------------------------------------------------------------


class TestTasks:
    def test_list_tasks(self):
        from chimeraforge.eval.tasks import list_tasks

        tasks = list_tasks()
        assert "general_knowledge" in tasks
        assert "summarization" in tasks
        assert "code" in tasks

    def test_get_task(self):
        from chimeraforge.eval.tasks import get_task

        t = get_task("general_knowledge")
        assert len(t.prompts) == 10
        assert len(t.references) == 10

    def test_get_unknown_task_raises(self):
        from chimeraforge.eval.tasks import get_task

        with pytest.raises(KeyError, match="Unknown eval task"):
            get_task("nonexistent_task")

    def test_prompts_and_refs_same_length(self):
        from chimeraforge.eval.tasks import BUILTIN_TASKS

        for name, task in BUILTIN_TASKS.items():
            assert len(task.prompts) == len(task.references), f"Mismatch in task '{name}'"


# ---------------------------------------------------------------------------
# TestRunner
# ---------------------------------------------------------------------------


class TestRunner:
    def test_run_eval_basic(self):
        from chimeraforge.eval.runner import run_eval

        result = run_eval(
            predictions=["Paris", "Mercury"],
            references=["Paris", "Mercury"],
            model="test-model",
            task="test",
        )
        assert result.model == "test-model"
        assert result.task == "test"
        assert result.scores.exact_match == 1.0

    def test_run_eval_length_mismatch_warns(self):
        from chimeraforge.eval.runner import run_eval

        result = run_eval(
            predictions=["Paris", "Mercury", "extra"],
            references=["Paris", "Mercury"],
        )
        assert any("Length mismatch" in w for w in result.warnings)

    def test_run_eval_empty_warns(self):
        from chimeraforge.eval.runner import run_eval

        result = run_eval(predictions=[], references=[])
        assert any("Empty" in w for w in result.warnings)

    def test_run_eval_from_file(self, tmp_path: Path):
        from chimeraforge.eval.runner import run_eval_from_file

        preds = tmp_path / "preds.txt"
        refs = tmp_path / "refs.txt"
        preds.write_text("Paris\nMercury\n")
        refs.write_text("Paris\nMercury\n")

        result = run_eval_from_file(preds, refs, model="fm")
        assert result.scores.exact_match == 1.0

    def test_run_eval_from_file_missing(self, tmp_path: Path):
        from chimeraforge.eval.runner import run_eval_from_file

        with pytest.raises(FileNotFoundError):
            run_eval_from_file(tmp_path / "nope.txt", tmp_path / "also_nope.txt")


# ---------------------------------------------------------------------------
# TestFormatting
# ---------------------------------------------------------------------------


class TestFormatting:
    def test_format_eval_json_round_trip(self):
        from chimeraforge.eval.runner import format_eval_json, run_eval

        result = run_eval(["Paris"], ["Paris"], model="m", task="t")
        j = format_eval_json([result])
        parsed = json.loads(j)
        assert len(parsed) == 1
        assert parsed[0]["model"] == "m"

    def test_format_eval_table(self, tmp_path: Path):
        from rich.console import Console

        from chimeraforge.eval.runner import format_eval_table, run_eval

        result = run_eval(["Paris"], ["Paris"], model="m", task="t")
        c = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
        format_eval_table([result], c)
        # No exception means success


# ---------------------------------------------------------------------------
# TestCLIEval
# ---------------------------------------------------------------------------


class TestCLIEval:
    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_eval_help(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["eval", "--help"])
        output = self._strip_ansi(result.output)
        assert result.exit_code == 0
        assert "--predictions" in output

    def test_eval_no_input_exits_1(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["eval"])
        assert result.exit_code == 1

    def test_eval_list_tasks(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["eval", "--list-tasks"])
        assert result.exit_code == 0
        assert "general_knowledge" in result.output

    def test_eval_with_task(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["eval", "--task", "general_knowledge", "--model", "test"])
        assert result.exit_code == 0

    def test_eval_with_files(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        preds = tmp_path / "preds.txt"
        refs = tmp_path / "refs.txt"
        preds.write_text("Paris\nMercury\n")
        refs.write_text("Paris\nMercury\n")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "eval",
                "--predictions",
                str(preds),
                "--references",
                str(refs),
                "--model",
                "test",
            ],
        )
        assert result.exit_code == 0

    def test_eval_json_output(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "eval",
                "--task",
                "general_knowledge",
                "--json",
            ],
        )
        assert result.exit_code == 0
        # Extract JSON array from output (torch may emit warnings to stdout)
        import re

        match = re.search(r"^\[", result.output, re.MULTILINE)
        assert match is not None, f"No JSON array found in output: {result.output[:200]}"
        parsed = json.loads(result.output[match.start() :])
        assert len(parsed) == 1
