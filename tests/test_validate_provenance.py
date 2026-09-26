"""P8.5: sourced measurements, evidence classes, and the headline audit metrics.

The audit harness shipped in 0.22.0 and was never run against a real
measurement. Its measurement schema was ``{cell_key: {metric: float}}`` -- bare
numbers with nowhere to put a source, a date, or what the number actually
measures. Publishing an audit on that schema would grade the planner against
numbers nobody can trace. These tests pin the four failure modes the roadmap
names and the properties that stop each:

1. Third-party cells are not own-rig cells -- separate class, never blended.
2. Grading against numbers the planner was fitted on is not a test -- refused.
3. Metric mismatch fabricates an error rate -- every value states its definition,
   and a definition the planner does not predict is kept but never scored.
4. Underspecified sources are published but kept out of the headline.
"""

from __future__ import annotations

import json
import math

import pytest

from chimeraforge.validate import (
    DEF_DECODE,
    DEF_E2E_TPS,
    DEF_PREFILL,
    DEF_TTFT,
    EVIDENCE_OWN_RIG,
    EVIDENCE_THIRD_PARTY,
    CellOutcome,
    Matrix,
    MatrixCell,
    MeasuredCell,
    ValidationError,
    build_audit,
    format_markdown,
    load_measurements,
    outcome_from_measurement,
    score,
)

KEY = "llama3.2-1b|FP16|ollama|c2048|p512|o128|b1"
URL = "https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-1"


def _cell(**over) -> dict:
    base = {
        "evidence": EVIDENCE_THIRD_PARTY,
        "source_url": URL,
        "captured_at": "2026-09-25",
        "config_quote": "llama-bench -m model.gguf -ngl 99 -fa 1",
        "underspecified": False,
        "metrics": [{"definition": DEF_DECODE, "value": 150.0, "quote": "tg128 | 150.00"}],
    }
    base.update(over)
    return base


def _file(cells: dict, **over) -> dict:
    base = {"schema_version": 2, "hardware": "RTX 4080 12GB", "cells": cells}
    base.update(over)
    return base


def _write(tmp_path, data) -> str:
    p = tmp_path / "measured.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def _matrix(**over) -> Matrix:
    base = dict(
        hardware="RTX 4080 12GB",
        registered_at="2026-09-25",
        cells=[MatrixCell(model="llama3.2-1b", quant="FP16", backend="ollama")],
    )
    base.update(over)
    return Matrix(**base)


# -- The schema: an unsourced cell does not load ------------------------------


class TestSourcedSchema:
    def test_a_well_formed_cell_loads(self, tmp_path):
        cells = load_measurements(_write(tmp_path, _file({KEY: _cell()})))
        m = cells[KEY]
        assert isinstance(m, MeasuredCell)
        assert m.evidence == EVIDENCE_THIRD_PARTY
        assert m.source_url == URL

    @pytest.mark.parametrize("missing", ["source_url", "captured_at", "evidence"])
    def test_third_party_cell_missing_provenance_is_rejected(self, tmp_path, missing):
        raw = _cell()
        del raw[missing]
        with pytest.raises(ValidationError, match=missing):
            load_measurements(_write(tmp_path, _file({KEY: raw})))

    def test_underspecified_must_be_decided_not_defaulted(self, tmp_path):
        raw = _cell()
        del raw["underspecified"]
        with pytest.raises(ValidationError, match="underspecified"):
            load_measurements(_write(tmp_path, _file({KEY: raw})))

    def test_metric_without_definition_is_rejected(self, tmp_path):
        raw = _cell(metrics=[{"value": 150.0}])
        with pytest.raises(ValidationError, match="definition"):
            load_measurements(_write(tmp_path, _file({KEY: raw})))

    def test_ambiguous_definition_is_rejected_by_name(self, tmp_path):
        """'tokens/sec' with no stated basis could be decode, e2e or aggregate."""
        raw = _cell(metrics=[{"definition": "ambiguous", "value": 150.0}])
        with pytest.raises(ValidationError, match="ambiguous"):
            load_measurements(_write(tmp_path, _file({KEY: raw})))

    @pytest.mark.parametrize("bad", [0, -1.0, float("nan"), "fast"])
    def test_non_positive_or_non_numeric_value_is_rejected(self, tmp_path, bad):
        raw = _cell(metrics=[{"definition": DEF_DECODE, "value": bad}])
        path = tmp_path / "m.json"
        path.write_text(json.dumps(_file({KEY: raw})).replace("NaN", '"nan"'), encoding="utf-8")
        with pytest.raises(ValidationError):
            load_measurements(str(path))

    def test_non_http_source_is_rejected(self, tmp_path):
        with pytest.raises(ValidationError, match="source_url"):
            load_measurements(_write(tmp_path, _file({KEY: _cell(source_url="my notes")})))

    def test_bare_floats_are_refused_with_the_reason(self, tmp_path):
        """The v1 schema is exactly the unsourced shape this item exists to end."""
        with pytest.raises(ValidationError, match="source"):
            load_measurements(_write(tmp_path, {KEY: {"throughput_tps": 150.0}}))

    def test_file_must_name_its_hardware(self, tmp_path):
        data = _file({KEY: _cell()})
        del data["hardware"]
        with pytest.raises(ValidationError, match="hardware"):
            load_measurements(_write(tmp_path, data))

    def test_own_rig_cell_may_cite_its_environment_instead_of_a_url(self, tmp_path):
        raw = _cell(evidence=EVIDENCE_OWN_RIG, environment={"gpu": "RTX 4080 12GB"})
        del raw["source_url"]
        assert load_measurements(_write(tmp_path, _file({KEY: raw})))[KEY].environment

    def test_own_rig_cell_with_neither_is_unsourced(self, tmp_path):
        raw = _cell(evidence=EVIDENCE_OWN_RIG)
        del raw["source_url"]
        with pytest.raises(ValidationError, match="environment"):
            load_measurements(_write(tmp_path, _file({KEY: raw})))


class TestNotGradingAgainstOurOwnCorpus:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/Sahil170595/Chimeraforge/blob/main/outputs/TR125.md",
            "https://github.com/sahil170595/Banterhearts/tree/main/experiments",
        ],
    )
    def test_third_party_cell_citing_the_tr_corpus_is_refused(self, tmp_path, url):
        with pytest.raises(ValidationError, match="fitted"):
            load_measurements(_write(tmp_path, _file({KEY: _cell(source_url=url)})))


# -- Metric definitions: compare like with like --------------------------------


class TestMetricDefinitions:
    def _outcome(self, metrics, prompt_tokens=512, predicted=None):
        cell = MatrixCell(
            model="llama3.2-1b", quant="FP16", backend="ollama", prompt_tokens=prompt_tokens
        )
        m = MeasuredCell.from_dict(cell.key, _cell(metrics=metrics))
        return outcome_from_measurement(
            cell,
            "roofline-estimate",
            predicted or {"throughput_tps": 160.0, "ttft_ms": 50.0, "p95_latency_ms": 900.0},
            m,
        )

    def test_decode_is_scored_against_throughput(self):
        o = self._outcome([{"definition": DEF_DECODE, "value": 200.0}])
        assert o.errors["throughput_tps"] == pytest.approx(-0.2)
        assert o.measured_basis["throughput_tps"] == DEF_DECODE

    def test_end_to_end_rate_is_kept_but_never_scored_as_decode(self):
        """e2e tok/s includes prefill; scoring it against a decode prediction would
        fabricate an optimism the planner does not have."""
        o = self._outcome([{"definition": DEF_E2E_TPS, "value": 120.0}])
        assert "throughput_tps" not in o.errors
        assert DEF_E2E_TPS in o.unscored

    def test_prefill_rate_converts_to_ttft_at_the_cells_prompt_length(self):
        o = self._outcome(
            [{"definition": DEF_PREFILL, "value": 10240.0, "prompt_tokens": 512}],
        )
        # 512 tokens / 10240 tok/s = 50 ms
        assert o.measured["ttft_ms"] == pytest.approx(50.0)
        assert o.errors["ttft_ms"] == pytest.approx(0.0)
        assert o.measured_basis["ttft_ms"] == DEF_PREFILL

    def test_prefill_measured_at_another_prompt_length_is_refused(self):
        with pytest.raises(ValidationError, match="prompt"):
            self._outcome([{"definition": DEF_PREFILL, "value": 10240.0, "prompt_tokens": 128}])

    def test_single_request_latency_is_scored_against_service_time(self):
        o = self._outcome(
            [{"definition": "e2e_latency_ms", "value": 1000.0}],
            predicted={"throughput_tps": 160.0, "ttft_ms": 50.0, "e2e_latency_ms": 850.0},
        )
        assert o.errors["e2e_latency_ms"] == pytest.approx(-0.15)
        # ...and never against the queueing p95, which is a different quantity.
        assert "p95_latency_ms" not in o.errors

    def test_two_measurements_of_one_quantity_is_an_error_not_a_pick(self):
        with pytest.raises(ValidationError, match="ttft_ms"):
            self._outcome(
                [
                    {"definition": DEF_TTFT, "value": 40.0},
                    {"definition": DEF_PREFILL, "value": 10240.0, "prompt_tokens": 512},
                ]
            )


# -- Evidence classes: never blended ------------------------------------------


def _scored(key, evidence, err, cls="roofline-estimate", underspecified=False):
    return CellOutcome(
        key=key,
        cell=MatrixCell(model=key, quant="FP16", backend="ollama"),
        provenance_class=cls,
        errors={"throughput_tps": err},
        evidence=evidence,
        underspecified=underspecified,
    )


class TestEvidenceSeparation:
    def test_third_party_and_own_rig_are_separate_rows(self):
        rows = score(
            [
                _scored("a", EVIDENCE_THIRD_PARTY, 0.10),
                _scored("b", EVIDENCE_OWN_RIG, -0.50),
            ]
        )
        by_ev = {r.evidence: r for r in rows}
        assert set(by_ev) == {EVIDENCE_THIRD_PARTY, EVIDENCE_OWN_RIG}
        assert by_ev[EVIDENCE_THIRD_PARTY].n == 1
        assert by_ev[EVIDENCE_THIRD_PARTY].worst_error == pytest.approx(0.10)

    def test_underspecified_cells_are_out_of_the_headline(self):
        rows = score(
            [
                _scored("a", EVIDENCE_THIRD_PARTY, 0.10),
                _scored("b", EVIDENCE_THIRD_PARTY, 3.00, underspecified=True),
            ]
        )
        assert len(rows) == 1 and rows[0].n == 1
        assert rows[0].worst_error == pytest.approx(0.10)

    def test_underspecified_cells_are_still_published(self):
        outcomes = [
            _scored("a", EVIDENCE_THIRD_PARTY, 0.10),
            _scored("b", EVIDENCE_THIRD_PARTY, 3.00, underspecified=True),
        ]
        audit = build_audit(_matrix(), outcomes)
        assert {c["key"] for c in audit.to_dict()["cells"]} == {"a", "b"}
        md = format_markdown(audit)
        assert "Underspecified" in md and "`b`" in md

    def test_pipe_delimited_keys_do_not_split_the_table_row(self):
        audit = build_audit(_matrix(), [_scored("m|FP16|ollama", EVIDENCE_THIRD_PARTY, 0.1)])
        row = next(ln for ln in format_markdown(audit).splitlines() if ln.startswith("| thr"))
        assert "m\\|FP16\\|ollama" in row
        assert row.replace("\\|", "").count("|") == 9  # 8 columns

    def test_report_states_third_party_is_never_blended(self):
        audit = build_audit(_matrix(), [_scored("a", EVIDENCE_THIRD_PARTY, 0.1)])
        md = format_markdown(audit)
        assert "third-party-measured" in md
        assert "never averaged" in md


# -- Headline metrics ---------------------------------------------------------


class TestHeadlineMetrics:
    def test_gmfe_is_symmetric_in_over_and_under_prediction(self):
        # 2x too high and 2x too low are the same size of mistake: GMFE 2.0.
        rows = score(
            [
                _scored("a", EVIDENCE_THIRD_PARTY, 1.0),  # pred = 2 * meas
                _scored("b", EVIDENCE_THIRD_PARTY, -0.5),  # pred = 0.5 * meas
            ]
        )
        assert rows[0].gmfe == pytest.approx(2.0)

    def test_bias_is_signed_so_optimism_is_visible(self):
        rows = score([_scored(k, EVIDENCE_THIRD_PARTY, 0.3) for k in "abc"])
        assert rows[0].median_signed == pytest.approx(0.3)

    def test_pass_rate_needs_a_pre_registered_band(self):
        rows = score([_scored("a", EVIDENCE_THIRD_PARTY, 0.1)])
        assert rows[0].pass_rate is None

    def test_pass_rate_against_the_registered_band(self):
        outcomes = [
            _scored(k, EVIDENCE_THIRD_PARTY, e) for k, e in zip("abcd", (0.1, -0.2, 0.3, -0.6))
        ]
        rows = score(outcomes, bands={"throughput_tps": 0.25})
        assert rows[0].pass_rate == pytest.approx(0.5)
        assert rows[0].band == 0.25

    def test_median_abs_error(self):
        rows = score([_scored(k, EVIDENCE_THIRD_PARTY, e) for k, e in zip("abc", (0.1, -0.2, 0.9))])
        assert rows[0].median_abs == pytest.approx(0.2)


# -- Pre-registration covers what the audit now depends on ---------------------


class TestFingerprintCoverage:
    def test_legacy_matrix_hash_is_unchanged(self):
        """Adding fields must not re-hash matrices that do not use them."""
        import pathlib

        example = (
            pathlib.Path(__file__).resolve().parents[1] / "examples" / "validation-matrix.json"
        )
        assert Matrix.load(example).fingerprint() == (
            "5786bfda445ef12cf44d4515c294b1c048c2db7defa0b0d5c954702642aa8d76"
        )

    def test_bands_are_fingerprinted(self):
        assert _matrix().fingerprint() != _matrix(bands={"throughput_tps": 0.25}).fingerprint()
        assert (
            _matrix(bands={"throughput_tps": 0.25}).fingerprint()
            != _matrix(bands={"throughput_tps": 0.5}).fingerprint()
        )

    def test_source_list_is_fingerprinted(self):
        """Choosing which benchmarks to look for is cherry-picking by another name,
        so the consulted-source list is part of what was pre-registered."""
        a = _matrix(sources=[{"url": URL, "status": "used"}])
        b = _matrix(
            sources=[{"url": URL, "status": "used"}, {"url": "https://x", "status": "unused"}]
        )
        assert a.fingerprint() != b.fingerprint() != _matrix().fingerprint()

    def test_cell_spec_is_fingerprinted(self):
        spec = {"params_b": 8.03, "n_layers": 32, "n_kv_heads": 8, "d_head": 128}
        a = _matrix(cells=[MatrixCell(model="m", quant="FP16", backend="vllm", spec=spec)])
        b = _matrix(
            cells=[
                MatrixCell(model="m", quant="FP16", backend="vllm", spec={**spec, "params_b": 7})
            ]
        )
        assert a.fingerprint() != b.fingerprint()

    def test_matrix_loads_bands_sources_and_spec(self):
        m = Matrix.from_dict(
            {
                "hardware": "RTX 4090 24GB",
                "registered_at": "2026-09-25",
                "bands": {"throughput_tps": 0.25},
                "sources": [{"url": URL, "status": "used"}],
                "cells": [
                    {
                        "model": "meta-llama/Llama-3.1-8B-Instruct",
                        "quant": "Q4_K_M",
                        "backend": "ollama",
                        "spec": {"params_b": 8.03, "n_layers": 32, "n_kv_heads": 8, "d_head": 128},
                    }
                ],
            }
        )
        assert m.bands == {"throughput_tps": 0.25}
        assert m.cells[0].spec_dict["n_layers"] == 32

    def test_a_band_for_an_unknown_metric_is_rejected(self):
        with pytest.raises(ValidationError, match="band"):
            Matrix.from_dict(
                {
                    "hardware": "RTX 4090 24GB",
                    "registered_at": "2026-09-25",
                    "bands": {"tokens": 0.25},
                    "cells": [{"model": "m", "quant": "FP16", "backend": "ollama"}],
                }
            )


# -- Re-derivation: the published report reproduces from its own raw JSON -----


class TestRederivation:
    def test_audit_json_rescores_to_the_same_scorecard(self, tmp_path):
        cell = MatrixCell(model="llama3.2-1b", quant="FP16", backend="ollama")
        m = MeasuredCell.from_dict(cell.key, _cell())
        o = outcome_from_measurement(cell, "measured-lookup", {"throughput_tps": 146.0}, m)
        audit = build_audit(_matrix(bands={"throughput_tps": 0.25}), [o])
        p = tmp_path / "audit.json"
        p.write_text(json.dumps(audit.to_dict()), encoding="utf-8")

        reloaded = load_measurements(str(p))
        o2 = outcome_from_measurement(
            cell, "measured-lookup", {"throughput_tps": 146.0}, reloaded[cell.key]
        )
        again = build_audit(_matrix(bands={"throughput_tps": 0.25}), [o2])
        assert again.to_dict()["scorecard"] == audit.to_dict()["scorecard"]
        assert reloaded[cell.key].source_url == URL


# -- CLI ---------------------------------------------------------------------


def _run(*args):
    from typer.testing import CliRunner

    from chimeraforge.cli import app

    return CliRunner().invoke(app, ["validate", *args])


def _matrix_file(tmp_path, cells, **extra) -> str:
    p = tmp_path / "matrix.json"
    p.write_text(
        json.dumps(
            {"hardware": "RTX 4080 12GB", "registered_at": "2026-09-25", "cells": cells, **extra}
        ),
        encoding="utf-8",
    )
    return str(p)


class TestCli:
    def test_hardware_mismatch_between_matrix_and_measurements_fails(self, tmp_path):
        mx = _matrix_file(
            tmp_path, [{"model": "llama3.2-1b", "quant": "FP16", "backend": "ollama"}]
        )
        meas = _write(tmp_path, _file({KEY: _cell()}, hardware="RTX 4090 24GB"))
        r = _run("--matrix", mx, "--measurements", meas, "--json")
        assert r.exit_code == 1
        assert "RTX 4090 24GB" in r.output

    def test_batched_cell_is_skipped_not_compared_to_a_single_stream_prediction(self, tmp_path):
        cells = [{"model": "llama3.2-1b", "quant": "FP16", "backend": "ollama", "batch": 8}]
        mx = _matrix_file(tmp_path, cells)
        key = "llama3.2-1b|FP16|ollama|c2048|p512|o128|b8"
        meas = _write(tmp_path, _file({key: _cell()}))
        out = tmp_path / "audit.json"
        r = _run("--matrix", mx, "--measurements", meas, "--json", "--output", str(out))
        assert r.exit_code == 0, r.output
        cell = json.loads(out.read_text(encoding="utf-8"))["cells"][0]
        assert cell["skipped"] and "single-stream" in cell["skipped"]

    def test_audit_ignores_the_local_measured_corpus(self, tmp_path, monkeypatch):
        """A published audit must be reproducible by anyone: predictions come from
        the bundled corpus, not whatever `measure` left in this user's cache."""
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "fitted_models.json").write_text(
            json.dumps({"throughput": {"lookup": {"llama3.2-1b|ollama|FP16": 1.0}}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(cache))
        from chimeraforge.planner.resolver import measured_corpus_path

        assert measured_corpus_path().exists()
        mx = _matrix_file(
            tmp_path, [{"model": "llama3.2-1b", "quant": "FP16", "backend": "ollama"}]
        )
        meas = _write(tmp_path, _file({KEY: _cell()}))
        out = tmp_path / "audit.json"
        r = _run("--matrix", mx, "--measurements", meas, "--json", "--output", str(out))
        assert r.exit_code == 0, r.output
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["cells"][0]["predicted"]["throughput_tps"] > 1.0
        assert data["models_basis"] == "bundled"

    def test_cell_spec_lets_an_off_registry_model_be_audited_offline(self, tmp_path):
        spec = {"params_b": 8.03, "n_layers": 32, "n_kv_heads": 8, "d_head": 128}
        cells = [
            {
                "model": "meta-llama/Llama-3.1-8B-Instruct",
                "quant": "Q4_K_M",
                "backend": "ollama",
                "spec": spec,
            }
        ]
        mx = _matrix_file(tmp_path, cells)
        key = "meta-llama/Llama-3.1-8B-Instruct|Q4_K_M|ollama|c2048|p512|o128|b1"
        meas = _write(tmp_path, _file({key: _cell()}))
        out = tmp_path / "audit.json"
        r = _run("--matrix", mx, "--measurements", meas, "--json", "--output", str(out))
        assert r.exit_code == 0, r.output
        cell = json.loads(out.read_text(encoding="utf-8"))["cells"][0]
        assert not cell["skipped"], cell["skipped"]
        assert cell["evidence"] == EVIDENCE_THIRD_PARTY
        assert math.isfinite(cell["errors"]["throughput_tps"])


# -- Found by running the audit (P8.5b) ----------------------------------------

L70 = {
    "params_b": 70.553706496,
    "n_layers": 80,
    "n_kv_heads": 8,
    "d_head": 128,
    "hidden_size": 8192,
}
L8 = {"params_b": 8.030261248, "n_layers": 32, "n_kv_heads": 8, "d_head": 128, "hidden_size": 4096}


def _audit_one(hardware, cell):
    from chimeraforge.validate import audit_cells, models_file

    with models_file(None) as path:
        return audit_cells(
            Matrix(hardware=hardware, registered_at="2026-09-25", cells=[cell]), {}, path
        )[0]


class TestAuditIsNotAFleetSizingExercise:
    def test_a_single_stream_cell_is_not_gated_on_fleet_capacity(self):
        """At 1 req/s x 512 tokens the capacity gate needed 512 tok/s, so a 70B that
        fits an 80 GB card was skipped -- the audit was sizing a fleet, not
        predicting one stream."""
        cell = MatrixCell(
            model="Meta-Llama-3-70B.Q4_K_M",
            quant="Q4_K_M",
            backend="ollama",
            avg_tokens=512,
            spec=tuple(sorted(L70.items())),
        )
        o = _audit_one("A100 80GB", cell)
        assert o.skipped == "no measurement for this cell"
        assert o.predicted["throughput_tps"] > 0

    def test_a_refused_cell_names_the_binding_gate(self):
        cell = MatrixCell(
            model="Meta-Llama-3-8B.F16",
            quant="FP16",
            backend="ollama",
            avg_tokens=512,
            spec=tuple(sorted(L8.items())),
        )
        o = _audit_one("RTX 4080 16GB", cell)
        assert "vram" in o.skipped and "16GB" in o.skipped


class TestSignConvention:
    def test_report_says_what_positive_means_for_latency(self):
        """'Positive = optimistic' is true for a rate and backwards for a latency:
        a TTFT predicted above measured is a pessimistic prediction."""
        audit = build_audit(_matrix(), [_scored("a", EVIDENCE_THIRD_PARTY, 0.1)])
        md = format_markdown(audit)
        assert "pessimistic" in md and "latency" in md
