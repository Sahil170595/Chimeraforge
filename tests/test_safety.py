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


# ── CLI command (fail-loud paths + mocked success) ───────────────────


async def _stub_screen(
    model, prompts, backend_name="ollama", quant=None, base_url=None, on_progress=None
):
    n_ref = len(prompts) if model != "low" else 1
    return SafetyScreenResult(
        model=model,
        backend=backend_name,
        quant=quant,
        n_prompts=len(prompts),
        n_refused=n_ref,
        n_errors=0,
        refusal_rate=n_ref / len(prompts),
    )


class TestSafetyCLI:
    @staticmethod
    def _run(args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, args)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_help(self):
        r = self._run(["safety", "--help"])
        assert r.exit_code == 0
        # Strip ANSI: Rich colorises option names (CI forces colour), so
        # "--prompts" is not a literal substring of the raw output.
        out = self._strip_ansi(r.output)
        assert "--prompts" in out and "--model" in out

    def test_missing_required_args(self):
        assert self._run(["safety"]).exit_code == 2

    def test_prompts_file_not_found(self):
        r = self._run(["safety", "--model", "m", "--prompts", "/nonexistent_xyz.txt"])
        assert r.exit_code == 1
        assert not isinstance(r.exception, (FileNotFoundError, ValueError))

    def test_empty_prompts_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("\n   \n", encoding="utf-8")
        assert self._run(["safety", "--model", "m", "--prompts", str(f)]).exit_code == 1

    def test_invalid_safety_target(self, tmp_path):
        f = tmp_path / "p.txt"
        f.write_text("prompt one\n", encoding="utf-8")
        r = self._run(["safety", "--model", "m", "--prompts", str(f), "--safety-target", "1.5"])
        assert r.exit_code == 1

    def test_unknown_backend_fails_clean(self, tmp_path):
        f = tmp_path / "p.txt"
        f.write_text("prompt one\nprompt two\n", encoding="utf-8")
        r = self._run(["safety", "--model", "m", "--prompts", str(f), "--backend", "nope"])
        assert r.exit_code == 1
        assert not isinstance(r.exception, (ValueError, RuntimeError))

    def test_success_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("chimeraforge.safety.run_safety_screen", _stub_screen)
        f = tmp_path / "p.txt"
        f.write_text("a\nb\nc\n", encoding="utf-8")
        r = self._run(["safety", "--model", "llama3.2-3b", "--prompts", str(f), "--json"])
        assert r.exit_code == 0
        import json as _json

        out = self._strip_ansi(r.output)
        data = _json.loads(out[out.index("{") :])
        assert data["refusal_rate"] == 1.0 and data["n_prompts"] == 3

    def test_below_target_exits_1(self, tmp_path, monkeypatch):
        monkeypatch.setattr("chimeraforge.safety.run_safety_screen", _stub_screen)
        f = tmp_path / "p.txt"
        f.write_text("a\nb\n", encoding="utf-8")
        # model "low" makes the stub return refusal_rate 0.5 < target 0.8
        r = self._run(["safety", "--model", "low", "--prompts", str(f), "--safety-target", "0.8"])
        assert r.exit_code == 1

    def test_comparison_resolves_ollama_tag(self, tmp_path, monkeypatch):
        # An Ollama tag must resolve to the bundled registry model (llama3.2-1b Q2_K).
        monkeypatch.setattr("chimeraforge.safety.run_safety_screen", _stub_screen)
        f = tmp_path / "p.txt"
        f.write_text("a\nb\n", encoding="utf-8")
        r = self._run(
            ["safety", "--model", "llama3.2:1b-instruct-q2_K", "--prompts", str(f), "--json"]
        )
        assert r.exit_code == 0
        import json as _json

        out = self._strip_ansi(r.output)
        data = _json.loads(out[out.index("{") :])
        assert data["resolved_to"] == "llama3.2-1b Q2_K"
        assert data["expected_refusal"] is not None
        assert data["rtsi_risk"] == "HIGH"


# ── Model identity / resolution ──────────────────────────────────────


class TestModelResolution:
    @pytest.mark.parametrize(
        "identifier,expected",
        [
            ("llama3.2:1b-instruct-q8_0", "llama3.2-1b"),
            ("llama3.2:3b-instruct-q4_K_M", "llama3.2-3b"),
            ("qwen2.5:1.5b-instruct-q2_K", "qwen2.5-1.5b"),
            ("qwen2.5:0.5b", "qwen2.5-0.5b"),
            ("qwen2.5:3b-instruct-q8_0", "qwen2.5-3b"),
            ("llama3.1:8b-instruct-q8_0", "llama3.1-8b"),
            ("phi:latest", "phi-2"),
            ("llama3.2-1b", "llama3.2-1b"),
            ("qwen2.5-1.5b", "qwen2.5-1.5b"),
        ],
    )
    def test_resolve(self, identifier, expected):
        from chimeraforge.planner.identity import resolve_model

        assert resolve_model(identifier) == expected

    @pytest.mark.parametrize("identifier", ["gpt-4o", "mystery-model", "gemma2:9b", ""])
    def test_unresolvable(self, identifier):
        from chimeraforge.planner.identity import resolve_model

        assert resolve_model(identifier) is None

    @pytest.mark.parametrize(
        "identifier,q",
        [
            ("llama3.2:1b-instruct-q8_0", "Q8_0"),
            ("x-q4_K_M", "Q4_K_M"),
            ("x-q2_K", "Q2_K"),
            ("model-fp16", "FP16"),
            ("no-quant-here", None),
        ],
    )
    def test_parse_quant(self, identifier, q):
        from chimeraforge.planner.identity import parse_quant

        assert parse_quant(identifier) == q

    def test_parse_identity_fields(self):
        from chimeraforge.planner.identity import parse_identity

        idy = parse_identity("llama3.2:3b-instruct-q4_K_M")
        assert idy.family == "llama3.2"
        assert idy.variant == "instruct"
        assert idy.params_b == 3.0
        assert idy.quant == "Q4_K_M"

    def test_quant_override_wins(self):
        from chimeraforge.planner.identity import parse_identity

        idy = parse_identity("llama3.2:1b-instruct-q8_0", quant_override="Q2_K")
        assert idy.quant == "Q2_K"
