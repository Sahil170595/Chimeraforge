"""Shared pytest fixtures for ChimeraForge tests."""

from __future__ import annotations

import pytest

from chimeraforge.planner.models import PlannerModels, load_bundled_models
from helpers import make_result


@pytest.fixture()
def bench_result():
    """Return a single default bench result dict."""
    return make_result()


@pytest.fixture(scope="session")
def bundled_models() -> PlannerModels:
    """Load the bundled fitted models (real data from TR133)."""
    return load_bundled_models()


@pytest.fixture()
def _deterministic_evaluate(monkeypatch) -> list[str]:
    """Stand in for the `evaluate` library in explicitly selected metric and CLI tests.

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

    metric_loads: list[str] = []

    class _Rouge:
        def compute(self, predictions, references, rouge_types):
            scores = [_rouge_l_f1(p, r) for p, r in zip(predictions, references)]
            return {"rougeL": sum(scores) / len(scores) if scores else 0.0}

    class _BertScore:
        def compute(self, predictions, references, lang):
            return {"f1": [_rouge_l_f1(p, r) for p, r in zip(predictions, references)]}

    def _load(name):
        metric_loads.append(name)
        if name == "bertscore":
            return _BertScore()
        if name == "rouge":
            return _Rouge()
        raise ValueError(f"unexpected metric requested: {name}")

    module = types.ModuleType("evaluate")
    module.load = _load
    monkeypatch.setitem(sys.modules, "evaluate", module)
    return metric_loads
