"""The README states what the planner's bundled tables actually hold, next to the
~204,000 figure, and that statement is computed from the data so it cannot drift.

The figure counts the research program; the planner's throughput table is 23 FP16
rows from one GPU. Read side by side without this, the larger number reads as if
it backs every prediction.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _shape_module():
    spec = importlib.util.spec_from_file_location(
        "corpus_shape", ROOT / "scripts" / "corpus_shape.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cs():
    return _shape_module()


@pytest.fixture(scope="module")
def fitted(cs):
    return json.loads(cs.FITTED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def scorecard(cs):
    return json.loads(cs.SCORECARD.read_text(encoding="utf-8"))


def test_readme_block_matches_the_bundled_data(cs):
    readme = cs.README.read_text(encoding="utf-8")
    assert cs.readme_block(readme) == cs.current()


def test_block_sits_next_to_the_headline_claim(cs):
    """Guardrail: the real shape is stated beside the claim, not pages away."""
    readme = cs.README.read_text(encoding="utf-8")
    claim = readme.index("204,000")
    assert 0 < readme.index(cs.START) - claim < 400


def test_every_other_mention_points_back(cs):
    readme = cs.README.read_text(encoding="utf-8")
    first = readme.index("204,000")
    for i in range(len(readme)):
        i = readme.find("204,000", first + 1)
        if i == -1:
            break
        start = readme.rfind("\n", 0, i)
        end = readme.find("\n", i)
        line = readme[start:end]
        assert "planner" in line and "tables" in line, line.strip()[:120]
        first = i


def test_shape_is_recomputed_not_copied(cs, fitted, scorecard):
    shape = cs.measure(fitted, scorecard, 17)
    tput = fitted["throughput"]["lookup"]
    assert shape["throughput_rows"] == len(tput) == 23
    assert shape["throughput_quants"] == ["FP16"]
    assert sum(shape["serving_rows"].values()) + shape["harness_rows"] == len(tput)
    assert shape["largest_params_b"] == 3.21


def test_stale_provenance_record_fails_loudly(cs, fitted, scorecard):
    tampered = copy.deepcopy(fitted)
    tampered["throughput"]["lookup"]["llama3.1-8b|vllm|FP16"] = 99.0
    with pytest.raises(cs.ShapeError, match="stale"):
        cs.measure(tampered, scorecard, 17)


def test_limitations_are_quoted_verbatim(cs, fitted):
    block = cs.current()
    for limit in fitted["_provenance"]["limitations"]:
        assert f"- {limit}" in block


def test_block_is_ascii(cs):
    cs.current().encode("ascii")
