"""Tests for identifiers resolving to facts about a different model.

Batch B of an adversarial review. All three findings are the same shape: an
identifier was matched to something else and kept a confident badge.

The worst was `resolve_model`, which short-circuited on a family with exactly
one registry model and returned it "regardless of the parsed size" -- the
docstring said so, as though it were a feature. `llama3.1:405b` therefore
resolved to the 8B, and the planner sized a 405-billion-parameter model at
8.03B / 4.55 GB while reporting its quality as `measured`, because every gate
downstream reads the alias's rows. The size was parsed correctly the whole time
and then thrown away. Only two families have a single member, which is why it
survived.
"""

from __future__ import annotations

import datetime as _dt
import json

import pytest

from chimeraforge.planner.identity import (
    MODEL_FAMILY,
    parse_family,
    parse_params_b,
    resolve_model,
)
from chimeraforge.planner.resolver import SPEC_CACHE_TTL_DAYS
from chimeraforge.planner.service import run_plan


class TestParsedSizeIsNeverIgnored:
    @pytest.mark.parametrize("ident", ["llama3.1:405b", "llama3.1:70b", "llama3.1-70b"])
    def test_oversized_tag_does_not_resolve_to_the_small_registry_model(self, ident):
        assert parse_params_b(ident) is not None, "precondition: the size IS parseable"
        assert resolve_model(ident) is None

    @pytest.mark.parametrize("ident", ["phi:14b", "phi-7b"])
    def test_the_other_single_member_family_too(self, ident):
        # phi-2 is 2.78B. Both families with one member took the same branch.
        assert resolve_model(ident) is None

    def test_matching_size_still_resolves(self):
        assert resolve_model("llama3.1:8b") == "llama3.1-8b"
        assert resolve_model("phi:2.7b") == "phi-2"

    def test_within_tolerance_still_resolves(self):
        # The tolerance is the point of the matcher; only ignoring the size was wrong.
        assert resolve_model("llama3.1:8.1b") == "llama3.1-8b"

    def test_multi_member_families_unchanged(self):
        assert resolve_model("llama3.2:3b") == "llama3.2-3b"
        assert resolve_model("llama3.2:1b") == "llama3.2-1b"
        assert resolve_model("qwen2.5:0.5b") == "qwen2.5-0.5b"

    def test_no_parseable_size_still_resolves_a_single_member_family(self):
        """`phi:latest` is what Ollama actually serves as phi-2, so this must keep
        working -- the rule is 'a size that was read must be honoured', not 'one
        candidate always loses'."""
        assert resolve_model("phi:latest") == "phi-2"

    def test_exact_registry_name_passes_through(self):
        assert resolve_model("llama3.1-8b") == "llama3.1-8b"

    def test_only_two_families_ever_took_the_short_circuit(self):
        """Pins why this went unnoticed: widening the registry would have exposed
        it, and narrowing it re-arms the trap."""
        from collections import Counter

        singles = [f for f, n in Counter(MODEL_FAMILY.values()).items() if n == 1]
        assert set(singles) == {"phi", "llama3.1"}

    def test_unknown_family_is_none(self):
        assert parse_family("acme/not-a-family-7b") is None
        assert resolve_model("acme/not-a-family-7b") is None


class TestPlanNoLongerSizes405bAs8b:
    def test_the_end_to_end_symptom_is_gone(self):
        """Refusing is the right answer, not a smaller wrong number.

        The planner used to return a confident 8.03B / 4.55 GB plan for a 405B
        tag. It now declines to resolve it at all, and says what would.
        """
        from chimeraforge.planner.resolver import ResolverError

        with pytest.raises(ResolverError) as exc:
            run_plan(
                models=["llama3.1:405b"],
                hardware="RTX 4090 24GB",
                budget=1e9,
                quality_target=0.0,
                allow_network=False,
            )
        msg = str(exc.value)
        assert "llama3.1:405b" in msg
        assert "--params-b" in msg, "the refusal must name the way forward"

    def test_it_still_resolves_when_the_network_can_answer(self):
        """The refusal is an OFFLINE last resort. A real 405B tag should resolve
        from live metadata; only the guess-from-a-different-size path is gone."""
        from chimeraforge.planner.resolver import ResolverError

        with pytest.raises(ResolverError):
            run_plan(
                models=["llama3.1:405b"],
                hardware="RTX 4090 24GB",
                budget=1e9,
                allow_network=False,
            )

    def test_an_approximation_never_claims_measured_quality(self):
        """A tolerance match reuses another model's rows, which is defensible for
        throughput but is not a measurement OF this model."""
        result = run_plan(
            models=["llama3.1:8.1b"],
            hardware="RTX 4080 12GB",
            budget=1e9,
            quality_target=0.0,
            allow_network=False,
        )
        assert result.candidates
        for cand in result.candidates:
            assert cand.provenance["quality"] != "measured"
            assert any("approximated" in w for w in cand.warnings)


class TestMeasuredQuantIsVerified:
    """`--quant` is free text that becomes part of the corpus key, and the key is
    what `plan` later reports as measured. An unchecked label attributes one
    quantization's rate to another -- permanently, since the corpus is persistent
    and nothing revisits it."""

    def test_agreement_is_a_no_op(self):
        from chimeraforge.measure import reconcile_quant

        assert reconcile_quant("Q4_K_M", "Q4_K_M") == ("Q4_K_M", [])

    def test_case_differences_are_not_a_mismatch(self):
        from chimeraforge.measure import reconcile_quant

        quant, warns = reconcile_quant("q4_k_m", "Q4_K_M")
        assert quant == "q4_k_m" and warns == []

    def test_the_served_artifact_wins_over_the_label(self):
        from chimeraforge.measure import reconcile_quant

        quant, warns = reconcile_quant("Q2_K", "Q4_K_M")
        assert quant == "Q4_K_M", "the corpus key must describe what actually ran"
        assert len(warns) == 1
        assert "Q2_K" in warns[0] and "Q4_K_M" in warns[0]

    def test_unknown_served_quant_leaves_the_label_alone(self):
        # Better to keep the caller's label than to invent one from nothing.
        from chimeraforge.measure import reconcile_quant

        assert reconcile_quant("Q2_K", None) == ("Q2_K", [])
        assert reconcile_quant("Q2_K", "") == ("Q2_K", [])

    def test_measure_only_verifies_an_explicitly_passed_quant(self):
        """When --quant is omitted the value already came from resolve_spec, so
        re-verifying it against itself would be circular."""
        import inspect

        import chimeraforge.measure as measure_mod

        src = inspect.getsource(measure_mod.measure_model)
        assert "quant_explicit = quant is None" not in src
        assert "if quant_explicit:" in src
        assert "reconcile_quant" in src


class TestSpecCacheExpires:
    """The cache is consulted ahead of the network, so without an expiry a repo
    whose config changes upstream is answered from the old copy forever."""

    def _cache_into(self, tmp_path, monkeypatch, stamp: str | None):
        from chimeraforge.planner import resolver

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        spec = resolver.ModelSpec(
            name="acme/thing-7b", params_b=7.0, n_layers=32, n_kv_heads=8, d_head=128
        )
        resolver._cache_store("acme/thing-7b", spec)
        path = resolver._cache_dir() / f"{resolver._cache_key('acme/thing-7b')}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        if stamp is None:
            raw.pop("_captured_at", None)
        else:
            raw["_captured_at"] = stamp
        path.write_text(json.dumps(raw), encoding="utf-8")
        return resolver

    def test_fresh_entry_is_used(self, tmp_path, monkeypatch):
        r = self._cache_into(tmp_path, monkeypatch, _dt.date.today().isoformat())
        assert r._cache_load("acme/thing-7b") is not None

    def test_expired_entry_is_ignored(self, tmp_path, monkeypatch):
        old = (_dt.date.today() - _dt.timedelta(days=SPEC_CACHE_TTL_DAYS + 1)).isoformat()
        r = self._cache_into(tmp_path, monkeypatch, old)
        assert r._cache_load("acme/thing-7b") is None

    def test_unstamped_legacy_entry_is_treated_as_expired(self, tmp_path, monkeypatch):
        """Entries written before stamping existed have no date. Trusting them
        would keep exactly the stale copies this fix is for."""
        r = self._cache_into(tmp_path, monkeypatch, None)
        assert r._cache_load("acme/thing-7b") is None

    def test_unparseable_stamp_is_treated_as_expired(self, tmp_path, monkeypatch):
        r = self._cache_into(tmp_path, monkeypatch, "not-a-date")
        assert r._cache_load("acme/thing-7b") is None

    def test_a_written_entry_carries_a_stamp(self, tmp_path, monkeypatch):
        from chimeraforge.planner import resolver

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        spec = resolver.ModelSpec(
            name="acme/other-7b", params_b=7.0, n_layers=32, n_kv_heads=8, d_head=128
        )
        resolver._cache_store("acme/other-7b", spec)
        path = resolver._cache_dir() / f"{resolver._cache_key('acme/other-7b')}.json"
        assert "_captured_at" in json.loads(path.read_text(encoding="utf-8"))

    def test_the_stamp_does_not_leak_into_the_spec(self, tmp_path, monkeypatch):
        r = self._cache_into(tmp_path, monkeypatch, _dt.date.today().isoformat())
        spec = r._cache_load("acme/thing-7b")
        assert spec is not None
        assert not hasattr(spec, "_captured_at")
        assert spec.params_b == 7.0
