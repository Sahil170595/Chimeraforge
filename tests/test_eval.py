"""ChimeraForge Eval - unit tests.

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


@pytest.fixture(autouse=True)
def _deterministic_evaluate(monkeypatch):
    """Stand in for the `evaluate` library across this whole module.

    CI installs `[all,dev]`, so `evaluate` is always importable there, and any
    test touching the scoring path pulled in torch, transformers and bert-score
    and then downloaded and materialized roberta-large to score two-word
    strings. That cost 65s of a 99s suite, and the weight materialization
    segfaulted intermittently on Windows -- a native crash in a suite that
    otherwise never touches native threading.

    The stand-in keeps the library path wired and exercised, deterministically
    and in microseconds. ROUGE delegates to the real pure-Python LCS so scores
    stay meaningful; BERTScore reuses it as a stand-in, since these tests are
    about plumbing and aggregation, not about validating BERTScore's semantics.

    Tests that need the library *absent* patch `builtins.__import__`, which runs
    before this lookup; tests that need different values install their own stub.
    """
    import sys
    import types

    from chimeraforge.eval.metrics import _rouge_l_f1

    class _Rouge:
        def compute(self, predictions, references, rouge_types):
            scores = [_rouge_l_f1(p, r) for p, r in zip(predictions, references)]
            return {"rougeL": sum(scores) / len(scores) if scores else 0.0}

    class _BertScore:
        def compute(self, predictions, references, lang):
            return {"f1": [_rouge_l_f1(p, r) for p, r in zip(predictions, references)]}

    def _load(name):
        if name == "bertscore":
            return _BertScore()
        if name == "rouge":
            return _Rouge()
        raise ValueError(f"unexpected metric requested: {name}")

    module = types.ModuleType("evaluate")
    module.load = _load
    monkeypatch.setitem(sys.modules, "evaluate", module)


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
    """`compute_rouge_l` has two implementations -- the `evaluate` library and a
    pure-Python LCS fallback -- and these tests used to exercise only whichever
    happened to be installed.

    CI installs `[all,dev]`, so `evaluate` is always present there and the
    fallback was never run at all: two implementations under one name, with no
    test able to say which produced a number or whether they agree. The fallback
    is now pinned directly against values derived by hand and confirmed equal to
    the library's, so a divergence fails without importing torch to find out.
    """

    # LCS-based F1, worked through by hand:
    #   "the cat sat" vs "the cat sat on the mat" -> LCS = 3 tokens.
    #   precision = 3/3 = 1.0, recall = 3/6 = 0.5
    #   F1 = 2 * 1.0 * 0.5 / 1.5 = 0.6667
    # Confirmed equal to evaluate's rougeL on this input.
    @pytest.mark.parametrize(
        ("pred", "ref", "expected"),
        [
            ("the cat sat on the mat", "the cat sat on the mat", 1.0),
            ("the cat sat", "the cat sat on the mat", 2 / 3),
            ("dogs run fast", "the cat sat on the mat", 0.0),
        ],
    )
    def test_fallback_matches_hand_derived_f1(self, pred, ref, expected):
        from chimeraforge.eval.metrics import _rouge_l_f1

        assert _rouge_l_f1(pred, ref) == pytest.approx(expected, abs=1e-4)

    def test_fallback_is_symmetric_in_f1(self):
        """F1 is symmetric, so swapping prediction and reference cannot change it.
        A precision/recall mix-up in the fallback would break this."""
        from chimeraforge.eval.metrics import _rouge_l_f1

        a = _rouge_l_f1("the cat sat", "the cat sat on the mat")
        b = _rouge_l_f1("the cat sat on the mat", "the cat sat")
        assert a == pytest.approx(b)

    def test_library_path_is_used_when_available(self, monkeypatch):
        """Contract of the wiring, without paying ~15s to import torch."""
        import sys
        import types

        from chimeraforge.eval import metrics

        seen = {}

        class _Stub:
            def compute(self, predictions, references, rouge_types):
                seen["types"] = rouge_types
                seen["n"] = len(predictions)
                return {"rougeL": 0.42}

        module = types.ModuleType("evaluate")
        module.load = lambda name: _Stub()
        monkeypatch.setitem(sys.modules, "evaluate", module)

        assert metrics.compute_rouge_l(["a b c"], ["a b"]) == pytest.approx(0.42)
        assert seen["types"] == ["rougeL"]

    def test_falls_back_when_the_library_is_missing(self, monkeypatch):
        """The fallback must produce the real score, not a sentinel -- this path is
        what every machine without the `eval` extra actually runs."""
        import builtins

        from chimeraforge.eval import metrics

        real_import = builtins.__import__

        def _no_evaluate(name, *args, **kwargs):
            if name == "evaluate":
                raise ImportError("simulated: evaluate is not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _no_evaluate)
        assert metrics.compute_rouge_l(["the cat sat"], ["the cat sat on the mat"]) == (
            pytest.approx(2 / 3, abs=1e-4)
        )

    def test_empty_returns_zero(self):
        from chimeraforge.eval.metrics import compute_rouge_l

        assert compute_rouge_l([], ["something"]) == 0.0


# ---------------------------------------------------------------------------
# TestBERTScore
# ---------------------------------------------------------------------------


class TestBERTScore:
    """These stub `evaluate` rather than scoring for real.

    The previous single test called `compute_bert_score(["hello"], ["hello"])`
    and asserted `-0.01 <= score <= 1.01`. Both branches satisfy that: the real
    score is 1.0 and the missing-dependency sentinel is 0.0, so it could not tell
    a working BERTScore from an absent one -- while downloading and materializing
    roberta-large to prove it, at 24.1s, a quarter of the whole suite's runtime.
    That model load is also the only place this suite touches native torch
    threading, and it segfaulted intermittently on Windows.

    Both branches are now asserted explicitly, and no model is loaded.
    """

    @staticmethod
    def _fake_evaluate(monkeypatch, loader):
        """Inject a stub `evaluate` into sys.modules.

        Importing the real library costs ~17s because it drags in torch and
        transformers, which is the very thing these tests exist to avoid.
        `import evaluate` consults sys.modules first, so the stub wins.
        """
        import sys
        import types

        module = types.ModuleType("evaluate")
        module.load = loader
        monkeypatch.setitem(sys.modules, "evaluate", module)

    def test_returns_the_mean_f1_across_pairs(self, monkeypatch):
        from chimeraforge.eval import metrics

        class _Stub:
            def compute(self, predictions, references, lang):
                assert lang == "en"
                assert len(predictions) == len(references)
                return {"f1": [0.9, 0.7]}

        self._fake_evaluate(monkeypatch, lambda name: _Stub())
        got = metrics.compute_bert_score(["a", "b"], ["a", "b"])
        assert got == pytest.approx(0.8)

    def test_pairs_are_truncated_to_the_shorter_list(self, monkeypatch):
        from chimeraforge.eval import metrics

        seen = {}

        class _Stub:
            def compute(self, predictions, references, lang):
                seen["n"] = len(predictions)
                return {"f1": [1.0] * len(predictions)}

        self._fake_evaluate(monkeypatch, lambda name: _Stub())
        metrics.compute_bert_score(["a", "b", "c"], ["a"])
        assert seen["n"] == 1

    def test_missing_dependency_returns_zero_and_warns(self, monkeypatch):
        """The sentinel the composite keys its reweighting off, so it has to be
        exactly 0.0 and it has to be audible."""
        import builtins

        from chimeraforge.eval import metrics

        real_import = builtins.__import__

        def _no_evaluate(name, *args, **kwargs):
            if name == "evaluate":
                raise ImportError("simulated: evaluate is not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _no_evaluate)
        with pytest.warns(UserWarning, match="BERTScore unavailable"):
            assert metrics.compute_bert_score(["a"], ["a"]) == 0.0

    def test_a_backend_failure_is_caught_not_raised(self, monkeypatch):
        """OSError/ValueError from a corrupt or partially-downloaded cache must
        degrade to the sentinel, not take the eval down."""
        from chimeraforge.eval import metrics

        def _boom(name):
            raise OSError("simulated: corrupt model cache")

        self._fake_evaluate(monkeypatch, _boom)
        with pytest.warns(UserWarning, match="BERTScore unavailable"):
            assert metrics.compute_bert_score(["a"], ["a"]) == 0.0

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
        # Not `in (all four values)`, which is true by construction. Identical
        # prediction and reference against an FP16 baseline of 1.0 is the
        # no-degradation case, so the tier is pinned to the specific one that means
        # that -- three of the four branches were otherwise unreachable here.
        assert qs.tier == "negligible"


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
        # The eval path imports torch/transformers, which emit logging + a tqdm
        # progress bar. In a real shell that goes to stderr (stdout stays clean
        # JSON), but typer's CliRunner merges the streams into result.output, and
        # the JSON "[" lands mid-line after the bar's carriage return. Locate the
        # array start ("[" followed by a newline - tqdm's "[00:00" is not) and
        # raw_decode so any trailing noise is ignored.
        import re

        match = re.search(r"\[\s*\n", result.output)
        assert match is not None, f"No JSON array found in output: {result.output[:200]}"
        parsed, _ = json.JSONDecoder().raw_decode(result.output[match.start() :])
        assert len(parsed) == 1
