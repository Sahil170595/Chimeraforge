"""The published third-party validation corpus and audit (P8.5).

Pins three things: the corpus on disk is exactly what the builder produces from
the extraction record (nothing hand-edited after the fact); the builder refuses
an unsourced or unregistered cell; and the published scorecard is reproducible
from its own committed raw JSON, and is current against today's planner.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib

import pytest

from chimeraforge.validate import (
    EVIDENCE_THIRD_PARTY,
    CellOutcome,
    MatrixCell,
    MeasuredCell,
    score,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpora"


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location(
        "build_validation_corpus", ROOT / "scripts" / "build_validation_corpus.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _raw() -> dict:
    return json.loads((ROOT / "scripts" / "validation_sources.json").read_text(encoding="utf-8"))


class TestCorpusIsTheBuildersOutput:
    def test_on_disk_corpus_matches_a_rebuild(self, builder):
        for path, text in builder._files(builder.build()).items():
            assert path.read_text(encoding="utf-8") == text, f"{path.name} was edited by hand"

    def test_every_exclusion_names_its_rule(self):
        excluded = json.loads((CORPUS / "exclusions.json").read_text(encoding="utf-8"))["excluded"]
        assert excluded
        for e in excluded:
            assert e["reason"].startswith(("rule ", "no planner identity")), e

    def test_every_raw_cell_is_either_scored_or_excluded(self, builder):
        """Nothing disappears between extraction and audit without a reason."""
        built = builder.build()
        excluded = {e["cell_id"] for e in built["exclusions"]["excluded"]}
        included = set()
        for ms in built["measured"].values():
            for rec in ms["cells"].values():
                included |= set(rec["notes"].split("raw cells ")[1].split(", "))
        assert included | excluded == {c["cell_id"] for c in _raw()["cells"]}
        assert not included & excluded

    def test_unused_sources_are_published_with_reasons(self):
        mx = json.loads((CORPUS / "h100-80gb.matrix.json").read_text(encoding="utf-8"))
        unused = [s for s in mx["sources"] if s["status"] == "unused"]
        assert unused and all(s.get("reason") for s in unused)

    def test_no_source_is_the_tr_corpus(self):
        for s in _raw()["sources"]:
            assert not any(m in s["url"].lower() for m in ("sahil170595", "chimeraforge"))


class TestBuilderFailsLoudly:
    def _build_with(self, builder, monkeypatch, tmp_path, mutate):
        raw = copy.deepcopy(_raw())
        mutate(raw)
        p = tmp_path / "sources.json"
        p.write_text(json.dumps(raw), encoding="utf-8")
        monkeypatch.setattr(builder, "SOURCES_FILE", p)
        return builder.build()

    @pytest.mark.parametrize("field", ["source_url", "captured_at", "metric_definition"])
    def test_a_cell_missing_provenance_fails_the_build(self, builder, monkeypatch, tmp_path, field):
        def drop(raw):
            raw["cells"][0][field] = ""

        with pytest.raises(builder.CorpusError, match=field):
            self._build_with(builder, monkeypatch, tmp_path, drop)

    def test_a_cell_from_an_unregistered_source_fails(self, builder, monkeypatch, tmp_path):
        def orphan(raw):
            raw["cells"][0]["source_id"] = "S99-not-enumerated"

        with pytest.raises(builder.CorpusError, match="registered source"):
            self._build_with(builder, monkeypatch, tmp_path, orphan)

    def test_a_gpu_outside_the_database_fails(self, builder, monkeypatch, tmp_path):
        def unknown(raw):
            raw["cells"][0]["planner_gpu"] = "RTX 6090 48GB"

        with pytest.raises(builder.CorpusError, match="hardware.json"):
            self._build_with(builder, monkeypatch, tmp_path, unknown)

    def test_a_tr_corpus_source_fails_even_if_registered(self, builder, monkeypatch, tmp_path):
        """The loader's own-corpus refusal runs at build time, not only at audit time."""
        from chimeraforge.validate import ValidationError

        def ours(raw):
            url = "https://github.com/Sahil170595/Chimeraforge/blob/main/TR125.md"
            for c in raw["cells"]:
                if c["cell_id"] == "C004":
                    c["source_url"] = url

        with pytest.raises(ValidationError, match="fitted"):
            self._build_with(builder, monkeypatch, tmp_path, ours)


class TestPublishedAuditReproduces:
    def _audits(self) -> list[dict]:
        return [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((CORPUS / "audits").glob("*.audit.json"))
        ]

    def test_scorecard_rederives_from_the_committed_raw_json(self):
        """No network, no GPU, no planner: the committed cells alone reproduce it."""
        outcomes = []
        for a in self._audits():
            for c in a["cells"]:
                cell = c["cell"]
                spec = cell.pop("spec", {}) or {}
                outcomes.append(
                    CellOutcome(
                        key=f"{a['hardware']} :: {c['key']}",
                        cell=MatrixCell(**cell, spec=tuple(sorted(spec.items()))),
                        provenance_class=c["provenance_class"],
                        errors=c["errors"],
                        skipped=c["skipped"],
                        evidence=c["evidence"],
                        underspecified=c["underspecified"],
                        measurement=(
                            MeasuredCell.from_dict(c["key"], c["measurement"])
                            if c["measurement"]
                            else None
                        ),
                    )
                )
        published = json.loads((CORPUS / "scorecard.json").read_text(encoding="utf-8"))
        rows = [r.to_dict() for r in score(outcomes, published["bands"])]
        assert rows == published["scorecard"]

    def test_published_audit_is_current_against_todays_planner(self, builder):
        """A planner change that moves any audited number -- better or worse --
        must re-publish the scorecard deliberately, not leave a stale one live."""
        audits = builder.run_audit()["audits"]
        live = builder.combined(audits)
        published = json.loads((CORPUS / "scorecard.json").read_text(encoding="utf-8"))
        hint = (
            "the audit moved: run scripts/build_validation_corpus.py --audit and "
            "update the published figures (README, TR147) with the change"
        )
        assert [r.to_dict() for r in live.rows] == published["scorecard"], hint
        split = {k: [r.to_dict() for r in v] for k, v in builder.by_memory(audits).items()}
        assert split == published["by_memory"], hint

    def test_headline_is_third_party_evidence_only(self):
        published = json.loads((CORPUS / "scorecard.json").read_text(encoding="utf-8"))
        assert published["scorecard"]
        assert {r["evidence"] for r in published["scorecard"]} == {EVIDENCE_THIRD_PARTY}

    def test_matrices_carry_the_registered_bands(self, builder):
        for p in CORPUS.glob("*.matrix.json"):
            assert json.loads(p.read_text(encoding="utf-8"))["bands"] == builder.BANDS
