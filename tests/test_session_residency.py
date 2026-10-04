"""Tests for multi-turn session residency (`plan --think-time --session-turns`).

A prefix-cache hit on a conversation's next turn needs that conversation's KV to
still be resident when the user comes back. Between turns the conversation is
idle -- not decoding, not counted by the concurrency ceiling -- but its prefix
has to survive in the KV pool for the whole think time. By Little's law the fleet
holds request_rate x (T-1)/T x think_time idle conversations at once, each with
its prompt + visible output. A config whose free KV cannot hold them cannot
deliver the stated hit rate, so the planner limits it:

    retention = min(1, conversations the free KV can hold / idle conversations)
    effective hit rate = stated hit rate x retention

and computes TTFT from the effective rate, inside the (N x B) search, because
more replicas genuinely hold more. Off unless both flags are given.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from chimeraforge.planner.engine import session_retention
from chimeraforge.planner.service import run_plan

BASE = dict(
    model_size="8b",
    hardware="RTX 4090 24GB",
    request_rate=2.0,
    budget=1e9,
    quality_target=0.0,
    prompt_tokens=4096,
    context_length=8192,
    prefix_cache_hit_rate=0.9,
)
SESSION = dict(think_time_s=60.0, session_turns=10)
# 2 req/s x 9/10 of turns followed by another x 60 s.
IDLE = 2.0 * 0.9 * 60.0


def _plan(**over):
    kw = dict(BASE)
    kw.update(over)
    return run_plan(**kw)


def _cells(cands):
    return {(c.model, c.quant, c.backend): c for c in cands}


class TestOffByDefault:
    def test_byte_identical_without_the_flags(self):
        a = _plan().candidates
        b = _plan(think_time_s=None, session_turns=None).candidates
        assert [asdict(c) for c in a] == [asdict(c) for c in b]

    def test_no_session_fields_or_warning_when_off(self):
        c = _plan().candidates[0]
        assert c.session_turns == 0 and c.session_retention == 1.0
        assert c.prefix_cache_hit_rate_effective == c.prefix_cache_hit_rate
        assert not any("idle conversation" in w for w in c.warnings)


class TestInputs:
    @pytest.mark.parametrize(
        "over, msg",
        [
            ({"think_time_s": 60.0}, "together"),
            ({"session_turns": 5}, "together"),
            ({"think_time_s": 0.0, "session_turns": 5}, "think_time"),
            ({"think_time_s": 30.0, "session_turns": 1}, "session_turns"),
            ({"think_time_s": 30.0, "session_turns": 5, "prefix_cache_hit_rate": 0.0}, "hit rate"),
        ],
    )
    def test_refused(self, over, msg):
        with pytest.raises(ValueError, match=msg):
            _plan(**over)


class TestRetention:
    def test_pure_function(self):
        assert session_retention(0.0, 0.0) == 1.0
        assert session_retention(100.0, 25.0) == 0.25
        assert session_retention(100.0, 400.0) == 1.0
        assert session_retention(100.0, -3.0) == 0.0

    def test_ollama_holds_one_conversation_per_replica(self):
        """Ollama keeps the prompt cache of its slot; the next request replaces it."""
        for c in _plan(**SESSION).candidates:
            if c.backend == "ollama":
                assert c.session_idle_conversations == pytest.approx(IDLE)
                assert c.session_capacity_conversations == pytest.approx(c.n_agents)
                # Reported to 4 decimal places.
                assert c.session_retention == pytest.approx(min(1.0, c.n_agents / IDLE), abs=5e-5)

    def test_effective_hit_rate_and_prefill_follow_retention(self):
        for c in _plan(**SESSION).candidates:
            h = 0.9 * c.session_retention
            assert c.prefix_cache_hit_rate == 0.9
            assert c.prefix_cache_hit_rate_effective == pytest.approx(h, abs=1e-4)
            # Retention is reported to 4 decimal places, which can move one token.
            assert abs(c.prefill_tokens_effective - max(round(4096 * (1 - h)), 1)) <= 1

    def test_short_think_time_changes_nothing(self):
        """When the fleet can hold every idle conversation, TTFT is the plain plan's."""
        plain = _cells(_plan().candidates)
        brief = _cells(_plan(think_time_s=0.01, session_turns=10).candidates)
        for k, c in brief.items():
            if k in plain:
                assert c.session_retention == 1.0
                assert c.ttft_ms == plain[k].ttft_ms

    def test_long_think_time_costs_ttft(self):
        plain = _cells(_plan().candidates)
        held = _cells(_plan(**SESSION).candidates)
        shared = [k for k in held if k in plain]
        assert shared
        assert all(held[k].ttft_ms >= plain[k].ttft_ms for k in shared)
        assert any(held[k].session_retention < 1.0 for k in shared)
        assert any(held[k].ttft_ms > plain[k].ttft_ms for k in shared)

    def test_residency_ttft_rejection_names_the_failed_gate(self):
        result = _plan(
            models=["llama3.1-8b"],
            allow_network=False,
            think_time_s=600.0,
            session_turns=10,
            ttft_slo=200.0,
            latency_slo=100000.0,
        )
        failures = [
            detail
            for model, _, gate, detail in result.trace
            if model == "llama3.1-8b" and gate == "latency"
        ]
        assert failures
        assert all("TTFT" in detail for detail in failures), failures

    def test_retention_never_rises_with_think_time(self):
        prev = None
        for s in (5.0, 30.0, 120.0, 600.0):
            cells = _cells(_plan(think_time_s=s, session_turns=10).candidates)
            if prev is not None:
                for k, c in cells.items():
                    if k in prev and c.n_agents == prev[k].n_agents:
                        assert c.session_retention <= prev[k].session_retention + 1e-9
            prev = cells

    def test_batching_capacity_is_the_free_pool(self):
        """vLLM keeps finished requests' blocks as evictable cache; what is free after
        the running batch is what idle conversations can occupy."""
        for c in _plan(**SESSION).candidates:
            if c.backend == "vllm":
                assert 0.0 < c.session_capacity_conversations
                assert c.session_retention == pytest.approx(
                    min(1.0, c.session_capacity_conversations / IDLE), abs=1e-4
                )

    def test_warning_states_the_assumptions(self):
        c = next(c for c in _plan(**SESSION).candidates if c.session_retention < 1.0)
        text = " ".join(c.warnings)
        assert "idle conversation" in text
        assert "session-affinity" in text


runner = CliRunner()
CLI = [
    "plan",
    "--model-size",
    "8b",
    "--hardware",
    "RTX 4090 24GB",
    "--budget",
    "1000000000",
    "--prompt-tokens",
    "4096",
    "--context-length",
    "8192",
    "--request-rate",
    "2",
]


class TestSurfaces:
    def test_cli_json(self):
        r = runner.invoke(
            app,
            [
                *CLI,
                "--prefix-cache-hit-rate",
                "0.9",
                "--think-time",
                "60",
                "--session-turns",
                "10",
                "--json",
            ],
        )
        assert r.exit_code == 0, r.output
        row = json.loads(r.output)[0]
        assert row["session_idle_conversations"] == pytest.approx(IDLE)
        assert 0.0 <= row["session_retention"] <= 1.0

    def test_cli_refuses_sessions_without_a_hit_rate(self):
        r = runner.invoke(app, [*CLI, "--think-time", "60", "--session-turns", "10"])
        assert r.exit_code == 1
        assert "hit rate" in " ".join(r.output.split())

    def test_mcp(self):
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(
            model_size="8b",
            hardware="RTX 4090 24GB",
            request_rate=2.0,
            prompt_tokens=4096,
            context_length=8192,
            prefix_cache_hit_rate=0.9,
            think_time_s=60.0,
            session_turns=10,
        )
        assert out["ok"], out
        assert out["recommended"]["session_retention"] <= 1.0

    def test_report_reproduces_the_flags(self, tmp_path):
        out = tmp_path / "b.md"
        r = runner.invoke(
            app,
            [
                *CLI,
                "--prefix-cache-hit-rate",
                "0.9",
                "--think-time",
                "60",
                "--session-turns",
                "10",
                "--report",
                str(out),
            ],
        )
        assert r.exit_code == 0, r.output
        text = out.read_text(encoding="utf-8")
        assert "--think-time 60" in text and "--session-turns 10" in text
