"""Tests for the prediction-vs-measured falsification audit.

The audit's value is entirely in the properties that stop it lying, so those are
what is pinned here: the fingerprint moves when the matrix does, in-corpus lookups
are never presented as out-of-sample predictions, the worst cell survives
aggregation, and a percentage built from two datapoints is labeled as an anecdote.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from chimeraforge.validate import (
    CLASS_LOOKUP,
    CLASS_PARALLEL,
    CLASS_ROOFLINE,
    LEAD_CLASS,
    MIN_CELLS_FOR_RATE,
    Audit,
    CellOutcome,
    Matrix,
    MatrixCell,
    ValidationError,
    build_audit,
    classify,
    format_markdown,
    load_measurements,
    relative_error,
    score,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "validation-matrix.json"


def _matrix(**over) -> Matrix:
    base = dict(
        hardware="RTX 4080 12GB",
        registered_at="2026-08-19",
        cells=[
            MatrixCell(model="llama3.2-1b", quant="FP16", backend="ollama"),
            MatrixCell(model="llama3.2-3b", quant="Q4_K_M", backend="ollama"),
        ],
        notes="",
    )
    base.update(over)
    return Matrix(**base)


def _outcome(key, cls, errs, skipped=None) -> CellOutcome:
    return CellOutcome(
        key=key,
        cell=MatrixCell(model="m", quant="Q4_K_M", backend="ollama"),
        provenance_class=cls,
        errors=errs,
        skipped=skipped,
    )


class TestMatrixValidation:
    def test_example_matrix_parses(self):
        m = Matrix.load(EXAMPLE)
        assert len(m.cells) == 10 and m.hardware

    def test_missing_field_is_rejected(self):
        with pytest.raises(ValidationError, match="registered_at"):
            Matrix.from_dict({"hardware": "x", "cells": [{"model": "m"}]})

    def test_non_iso_registration_date_is_rejected(self):
        with pytest.raises(ValidationError, match="ISO date"):
            Matrix.from_dict(
                {"hardware": "x", "registered_at": "last tuesday", "cells": [{"model": "m"}]}
            )

    def test_empty_matrix_is_rejected(self):
        with pytest.raises(ValidationError, match="no cells"):
            Matrix.from_dict({"hardware": "x", "registered_at": "2026-08-19", "cells": []})

    def test_duplicate_cells_are_rejected(self):
        cell = {"model": "m", "quant": "FP16", "backend": "ollama"}
        with pytest.raises(ValidationError, match="duplicate"):
            Matrix.from_dict(
                {"hardware": "x", "registered_at": "2026-08-19", "cells": [cell, dict(cell)]}
            )

    def test_missing_file_is_actionable(self):
        with pytest.raises(ValidationError, match="not found"):
            Matrix.load(ROOT / "nope-does-not-exist.json")


class TestFingerprintStopsCherryPicking:
    """The pre-registration promise has to be checkable, not just stated."""

    def test_stable_for_the_same_matrix(self):
        assert _matrix().fingerprint() == _matrix().fingerprint()

    def test_independent_of_cell_order(self):
        a = _matrix()
        b = _matrix(cells=list(reversed(a.cells)))
        assert a.fingerprint() == b.fingerprint()

    def test_changes_when_a_cell_is_dropped(self):
        a = _matrix()
        assert a.fingerprint() != _matrix(cells=a.cells[:1]).fingerprint()

    def test_changes_when_a_cell_is_edited(self):
        a = _matrix()
        edited = [MatrixCell(model="llama3.2-1b", quant="Q2_K", backend="ollama"), a.cells[1]]
        assert a.fingerprint() != _matrix(cells=edited).fingerprint()

    def test_changes_with_hardware(self):
        assert _matrix().fingerprint() != _matrix(hardware="H100 80GB").fingerprint()

    def test_audit_records_the_fingerprint_it_ran_against(self):
        m = _matrix()
        assert build_audit(m, []).fingerprint == m.fingerprint()


class TestClassification:
    def test_measured_throughput_is_in_corpus(self):
        assert classify({"throughput": "measured"}) == CLASS_LOOKUP

    def test_estimated_throughput_is_the_out_of_sample_path(self):
        assert classify({"throughput": "estimated"}) == CLASS_ROOFLINE

    def test_unknown_provenance_is_not_treated_as_measured(self):
        assert classify({}) == CLASS_ROOFLINE

    @pytest.mark.parametrize("tp,pp", [(4, 1), (1, 2)])
    def test_multi_gpu_is_its_own_class(self, tp, pp):
        # A comms model layered on either basis is a separate claim.
        assert classify({"throughput": "measured"}, tp, pp) == CLASS_PARALLEL

    def test_lead_class_is_the_one_making_a_prediction(self):
        assert LEAD_CLASS == CLASS_ROOFLINE


class TestRelativeError:
    def test_sign_means_optimistic(self):
        assert relative_error(110.0, 100.0) == pytest.approx(0.10)
        assert relative_error(90.0, 100.0) == pytest.approx(-0.10)

    def test_zero_measurement_is_undefined_not_zero(self):
        assert relative_error(10.0, 0.0) is None

    def test_missing_measurement_is_undefined(self):
        assert relative_error(10.0, None) is None


class TestScorecard:
    def test_splits_by_class(self):
        rows = score(
            [
                _outcome("a", CLASS_ROOFLINE, {"throughput_tps": 0.1}),
                _outcome("b", CLASS_LOOKUP, {"throughput_tps": 0.01}),
            ]
        )
        assert {r.provenance_class for r in rows} == {CLASS_ROOFLINE, CLASS_LOOKUP}

    def test_mape_is_absolute_so_errors_do_not_cancel(self):
        rows = score(
            [
                _outcome("a", CLASS_ROOFLINE, {"throughput_tps": 0.20}),
                _outcome("b", CLASS_ROOFLINE, {"throughput_tps": -0.20}),
            ]
        )
        assert rows[0].mape == pytest.approx(0.20)
        assert rows[0].median_signed == pytest.approx(0.0)

    def test_worst_cell_survives_aggregation(self):
        rows = score(
            [_outcome(f"ok{i}", CLASS_ROOFLINE, {"throughput_tps": 0.01}) for i in range(9)]
            + [_outcome("bad", CLASS_ROOFLINE, {"throughput_tps": -0.9})]
        )
        assert rows[0].worst_key == "bad"
        assert rows[0].worst_error == pytest.approx(-0.9)

    def test_small_sample_is_labeled_underpowered(self):
        rows = score([_outcome("a", CLASS_ROOFLINE, {"throughput_tps": 0.1})])
        assert rows[0].n == 1 and rows[0].underpowered

    def test_large_sample_is_not(self):
        rows = score(
            [
                _outcome(f"c{i}", CLASS_ROOFLINE, {"throughput_tps": 0.1})
                for i in range(MIN_CELLS_FOR_RATE)
            ]
        )
        assert not rows[0].underpowered

    def test_skipped_cells_are_excluded_from_statistics(self):
        rows = score(
            [
                _outcome("a", CLASS_ROOFLINE, {"throughput_tps": 0.1}),
                _outcome("b", CLASS_ROOFLINE, {"throughput_tps": 9.9}, skipped="no measurement"),
            ]
        )
        assert rows[0].n == 1

    def test_no_measurements_scores_nothing_rather_than_zero(self):
        assert score([_outcome("a", CLASS_ROOFLINE, {}, skipped="x")]) == []


class TestReport:
    def _audit(self) -> Audit:
        return build_audit(
            _matrix(),
            [
                _outcome("roof-a", CLASS_ROOFLINE, {"throughput_tps": 0.12}),
                _outcome("look-a", CLASS_LOOKUP, {"throughput_tps": 0.001}),
                _outcome("skip-a", CLASS_ROOFLINE, {}, skipped="no measurement for this cell"),
            ],
            generated_at="2026-08-19",
        )

    def test_leads_with_the_out_of_sample_class(self):
        md = format_markdown(self._audit())
        assert md.index(CLASS_ROOFLINE) < md.index(CLASS_LOOKUP)

    def test_in_corpus_class_is_labeled_not_a_test(self):
        md = format_markdown(self._audit())
        assert "is** the prediction" in md or "IS the prediction" in md

    def test_skipped_cells_are_listed_not_hidden(self):
        assert "skip-a" in format_markdown(self._audit())

    def test_fingerprint_and_registration_date_are_printed(self):
        md = format_markdown(self._audit())
        assert "2026-08-19" in md and "fingerprint" in md.lower()

    def test_sign_convention_is_stated(self):
        assert "optimistic" in format_markdown(self._audit())

    def test_underpowered_rows_are_flagged_in_the_report(self):
        assert "anecdote" in format_markdown(self._audit())


class TestMeasurementLoading:
    def test_bare_mapping(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(json.dumps({"k": {"throughput_tps": 1.0}}), encoding="utf-8")
        assert load_measurements(p)["k"]["throughput_tps"] == 1.0

    def test_a_previous_audit_can_be_rescored(self, tmp_path):
        # The published raw output must be enough to re-derive the table.
        audit = build_audit(
            _matrix(),
            [
                CellOutcome(
                    key="k",
                    cell=MatrixCell(model="m", quant="FP16", backend="ollama"),
                    provenance_class=CLASS_ROOFLINE,
                    predicted={"throughput_tps": 110.0},
                    measured={"throughput_tps": 100.0},
                    errors={"throughput_tps": 0.1},
                )
            ],
        )
        p = tmp_path / "audit.json"
        p.write_text(json.dumps(audit.to_dict()), encoding="utf-8")
        assert load_measurements(p)["k"]["throughput_tps"] == 100.0

    def test_missing_file_is_actionable(self, tmp_path):
        with pytest.raises(ValidationError, match="not found"):
            load_measurements(tmp_path / "nope.json")

    def test_malformed_json_is_actionable(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValidationError, match="valid JSON"):
            load_measurements(p)


class TestCli:
    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["validate", *args])

    def test_refuses_without_anything_to_compare_against(self):
        r = self._run("--matrix", str(EXAMPLE))
        assert r.exit_code == 1
        assert "--measurements" in r.output or "measurements" in r.output

    def test_bad_matrix_fails_clean(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text("{not json", encoding="utf-8")
        r = self._run("--matrix", str(p), "--measurements", str(p))
        assert r.exit_code == 1
        assert not isinstance(r.exception, (KeyError, TypeError))

    def test_offline_scoring_end_to_end(self, tmp_path):
        # A cell the bundled corpus measures, scored against a supplied number.
        m = tmp_path / "matrix.json"
        m.write_text(
            json.dumps(
                {
                    "hardware": "RTX 4080 12GB",
                    "registered_at": "2026-08-19",
                    "cells": [{"model": "llama3.2-1b", "quant": "FP16", "backend": "ollama"}],
                }
            ),
            encoding="utf-8",
        )
        meas = tmp_path / "meas.json"
        meas.write_text(
            json.dumps({"llama3.2-1b|FP16|ollama|c2048|p512|o128|b1": {"throughput_tps": 100.0}}),
            encoding="utf-8",
        )
        out = tmp_path / "audit.json"
        r = self._run(
            "--matrix", str(m), "--measurements", str(meas), "--json", "--output", str(out)
        )
        assert r.exit_code == 0, r.output
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["matrix_fingerprint"]
        assert data["cells"][0]["measured"]["throughput_tps"] == 100.0
        assert "throughput_tps" in data["cells"][0]["errors"]

    def test_unmeasured_cells_are_recorded_with_a_reason(self, tmp_path):
        m = tmp_path / "matrix.json"
        m.write_text(
            json.dumps(
                {
                    "hardware": "RTX 4080 12GB",
                    "registered_at": "2026-08-19",
                    "cells": [{"model": "llama3.2-1b", "quant": "FP16", "backend": "ollama"}],
                }
            ),
            encoding="utf-8",
        )
        meas = tmp_path / "meas.json"
        meas.write_text(json.dumps({"some-other-cell": {"throughput_tps": 1.0}}), encoding="utf-8")
        out = tmp_path / "audit.json"
        r = self._run(
            "--matrix", str(m), "--measurements", str(meas), "--json", "--output", str(out)
        )
        assert r.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["cells"][0]["skipped"]

    def test_writes_a_markdown_report(self, tmp_path):
        m = tmp_path / "matrix.json"
        m.write_text(
            json.dumps(
                {
                    "hardware": "RTX 4080 12GB",
                    "registered_at": "2026-08-19",
                    "cells": [{"model": "llama3.2-1b", "quant": "FP16", "backend": "ollama"}],
                }
            ),
            encoding="utf-8",
        )
        meas = tmp_path / "meas.json"
        meas.write_text(
            json.dumps({"llama3.2-1b|FP16|ollama|c2048|p512|o128|b1": {"throughput_tps": 100.0}}),
            encoding="utf-8",
        )
        rep = tmp_path / "report.md"
        r = self._run("--matrix", str(m), "--measurements", str(meas), "--report", str(rep))
        assert r.exit_code == 0
        assert "prediction-vs-measured" in rep.read_text(encoding="utf-8").lower()
