"""Tests for the live safety screen — refusal classifier + screen runner."""

from __future__ import annotations

import pytest

from chimeraforge.safety import classify_refusal, refusal_pattern_count, run_safety_screen
from chimeraforge.safety.runner import SafetyScreenResult


# ── Refusal classifier ───────────────────────────────────────────────


class TestRefusalClassifier:
    @pytest.mark.parametrize(
        "text",
        [
            "I cannot help with that request.",
            "I'm sorry, but I can't assist with this.",
            "I will not provide instructions for that.",
            "I'm not able to help you with that.",
            "As an AI, I cannot comply with this request.",
            "That would be illegal, so I must decline.",
            "I apologize, but this violates my guidelines.",
            "I can't help you with that.",
        ],
    )
    def test_refusals_detected(self, text):
        assert classify_refusal(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Sure! Here are the steps you asked for: first, ...",
            "The capital of France is Paris.",
            "Absolutely, let me walk you through it.",
            "Here is a recipe for chocolate cake.",
        ],
    )
    def test_compliance_not_refusal(self, text):
        assert classify_refusal(text) is False

    def test_empty_is_not_refusal(self):
        assert classify_refusal("") is False
        assert classify_refusal("   \n  ") is False

    def test_refusal_must_be_in_head(self):
        body = "Here are the full detailed steps. " * 40
        assert classify_refusal(body + "I cannot do more.", head_chars=50) is False

    def test_pattern_count(self):
        assert refusal_pattern_count() >= 8


# ── Screen runner (mocked backend, no live model) ────────────────────


class _FakeBackend:
    name = "fake"

    def __init__(self, responses, health=(True, "ok"), model_ok=(True, "")):
        self._responses = list(responses)
        self._health = health
        self._model_ok = model_ok
        self._i = 0

    async def health_check(self):
        return self._health

    async def check_model(self, model):
        return self._model_ok

    async def generate_text(self, model, prompt, options=None):
        r = self._responses[self._i % len(self._responses)]
        self._i += 1
        if isinstance(r, Exception):
            raise r
        return r

    async def get_version(self):
        return "fake-1.0"

    async def generate(self, model, prompt, options=None):  # unused by the screen
        raise NotImplementedError


def _patch_backend(monkeypatch, backend):
    monkeypatch.setattr("chimeraforge.safety.runner.get_backend", lambda name, **kw: backend)


class TestSafetyScreenRunner:
    @pytest.mark.asyncio
    async def test_all_refused(self, monkeypatch):
        _patch_backend(monkeypatch, _FakeBackend(["I cannot help with that."]))
        res = await run_safety_screen("m", ["p1", "p2", "p3"], backend_name="fake")
        assert isinstance(res, SafetyScreenResult)
        assert res.refusal_rate == 1.0
        assert res.n_refused == 3 and res.n_prompts == 3

    @pytest.mark.asyncio
    async def test_mixed_refusal_rate(self, monkeypatch):
        _patch_backend(
            monkeypatch,
            _FakeBackend(
                ["I cannot help.", "Sure, here you go: ...", "I cannot help.", "Of course!"]
            ),
        )
        res = await run_safety_screen("m", ["a", "b", "c", "d"], backend_name="fake")
        assert res.refusal_rate == 0.5
        assert res.n_refused == 2 and res.n_prompts == 4

    @pytest.mark.asyncio
    async def test_per_prompt_failure_is_resilient(self, monkeypatch):
        _patch_backend(
            monkeypatch,
            _FakeBackend(["I cannot help.", RuntimeError("boom"), "I cannot help."]),
        )
        res = await run_safety_screen("m", ["a", "b", "c"], backend_name="fake")
        assert res.n_errors == 1
        assert res.n_prompts == 2  # errored prompt excluded from the rate
        assert res.refusal_rate == 1.0
        assert any("failed" in w for w in res.warnings)

    @pytest.mark.asyncio
    async def test_all_failed_raises(self, monkeypatch):
        _patch_backend(monkeypatch, _FakeBackend([RuntimeError("down")]))
        with pytest.raises(RuntimeError, match="All 2 prompts failed"):
            await run_safety_screen("m", ["a", "b"], backend_name="fake")

    @pytest.mark.asyncio
    async def test_health_fail_raises(self, monkeypatch):
        _patch_backend(monkeypatch, _FakeBackend(["x"], health=(False, "Ollama not running")))
        with pytest.raises(RuntimeError, match="not running"):
            await run_safety_screen("m", ["a"], backend_name="fake")

    @pytest.mark.asyncio
    async def test_model_check_fail_raises(self, monkeypatch):
        _patch_backend(monkeypatch, _FakeBackend(["x"], model_ok=(False, "Model not found")))
        with pytest.raises(RuntimeError, match="not found"):
            await run_safety_screen("m", ["a"], backend_name="fake")

    @pytest.mark.asyncio
    async def test_empty_prompts_raises(self, monkeypatch):
        _patch_backend(monkeypatch, _FakeBackend(["x"]))
        with pytest.raises(ValueError, match="no prompts"):
            await run_safety_screen("m", [], backend_name="fake")

    @pytest.mark.asyncio
    async def test_not_implemented_propagates(self, monkeypatch):
        backend = _FakeBackend(["x"])

        async def _raise(*a, **k):
            raise NotImplementedError("vllm has no text generation yet")

        backend.generate_text = _raise
        _patch_backend(monkeypatch, backend)
        with pytest.raises(NotImplementedError):
            await run_safety_screen("m", ["a"], backend_name="fake")

    @pytest.mark.asyncio
    async def test_to_dict(self, monkeypatch):
        _patch_backend(monkeypatch, _FakeBackend(["I cannot help."]))
        res = await run_safety_screen(
            "llama3.2-3b", ["a", "b"], backend_name="fake", quant="Q4_K_M"
        )
        d = res.to_dict()
        assert d["model"] == "llama3.2-3b" and d["quant"] == "Q4_K_M"
        assert d["refusal_rate"] == 1.0 and d["n_prompts"] == 2
