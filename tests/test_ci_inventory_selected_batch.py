"""The installed inventory seam must exercise actual producers and all selected slots."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from test_ci_acceptance import load_script


def corpus_bytes(monkeypatch, *, crlf=False, semantic_change=False):
    from chimeraforge.planner import models

    corpus = Path(models.__file__).parent / "data/fitted_models.json"
    original = corpus.read_bytes()
    consumed = original.replace(b"\r\n", b"\n")
    if semantic_change:
        data = json.loads(consumed)
        # Outside the archived custom-model population, but still a real coefficient.
        data["safety"]["lookup"]["qwen2.5-7b|Q4_K_M"] += 0.001
        consumed = json.dumps(data, sort_keys=True).encode()
    elif crlf:
        consumed = consumed.replace(b"\n", b"\r\n")
    native_read = Path.read_bytes

    def read_bytes(path):
        if path == corpus:
            return consumed
        return native_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    return corpus, original, consumed, native_read


def consume(tmp_path):
    load_script("ci_installed_acceptance")
    script = load_script("ci_inventory_check")
    return script.accept_selected_batch(tmp_path, dict(os.environ), hosted_native_absence=False)


def test_selected_batch_consumer_admits_native_lf_corpus_receipt(tmp_path, monkeypatch):
    corpus, original, consumed, native_read = corpus_bytes(monkeypatch)
    actual = consume(tmp_path)
    assert actual["legacy_prediction_equivalence_with_tool_change_retained"]
    receipts = actual["legacy_receipts"]
    assert receipts["corpus_state"] == "changed"
    assert receipts["required_failures"] == ["corpus", "tool"]
    assert receipts["consumed_input_sha256"] == hashlib.sha256(consumed).hexdigest()
    assert receipts["saved_coefficient_sha256"] == receipts["consumed_coefficient_sha256"]
    assert native_read(corpus) == original


def test_selected_batch_consumer_admits_native_crlf_corpus_receipt(tmp_path, monkeypatch):
    corpus, original, consumed, native_read = corpus_bytes(monkeypatch, crlf=True)
    actual = consume(tmp_path)
    receipts = actual["legacy_receipts"]
    assert receipts["corpus_state"] == "unchanged"
    assert receipts["required_failures"] == ["tool"]
    assert receipts["consumed_input_sha256"] == hashlib.sha256(consumed).hexdigest()
    assert native_read(corpus) == original


def test_selected_batch_consumer_refuses_unused_coefficient_change(tmp_path, monkeypatch, capsys):
    from chimeraforge import api

    corpus_bytes(monkeypatch, semantic_change=True)
    legacy = api.load_plan(Path(__file__).parent / "fixtures/inventory/legacy086-qwen-b8.json")
    report = api.check_plan(legacy).to_dict()
    corpus = report["components"]["corpus"]
    assert report["comparison"]["changed"] is False
    assert corpus["before"]["sha256"] != corpus["after"]["sha256"]
    with pytest.raises(AssertionError, match="Legacy coefficient corpus differs"):
        consume(tmp_path)
    diagnostic = [
        json.loads(line)["legacy_corpus_check"]
        for line in capsys.readouterr().err.splitlines()
        if line.startswith('{"legacy_corpus_check":')
    ]
    assert len(diagnostic) == 1
    assert diagnostic[0]["prediction_changed"] is False
    assert diagnostic[0]["required_failures"] == ["corpus", "tool"]
    assert diagnostic[0]["saved_coefficient_sha256"] != diagnostic[0]["consumed_coefficient_sha256"]
    assert str(tmp_path) not in json.dumps(diagnostic)


def test_selected_batch_consumer_keeps_other_required_component_guard(tmp_path, monkeypatch):
    from chimeraforge import api
    from chimeraforge.planner import hardware

    gpu = hardware.GPU_DB["RTX 4090 24GB"]
    monkeypatch.setitem(
        hardware.GPU_DB, gpu.name, replace(gpu, source_url=gpu.source_url + "#changed")
    )
    legacy = api.load_plan(Path(__file__).parent / "fixtures/inventory/legacy086-qwen-b8.json")
    report = api.check_plan(legacy).to_dict()
    assert report["comparison"]["changed"] is False
    assert report["components"]["hardware"]["state"] == "changed"
    with pytest.raises(AssertionError):
        consume(tmp_path)


def test_selected_batch_consumer_keeps_native_prediction_guard(tmp_path, monkeypatch):
    from chimeraforge import api

    path = Path(__file__).parent / "fixtures/inventory/legacy086-qwen-b8.json"
    original = path.read_bytes()
    data = api.load_plan(path).to_dict()
    data["result"]["candidates"][0]["vram_gb"] += 0.125
    body = {key: value for key, value in data.items() if key != "fingerprint"}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    mutant = api.artifact_from_dict(data)
    assert api.check_plan(mutant).to_dict()["comparison"]["changed"] is True
    load = api.load_plan

    def load_plan(value):
        return mutant if Path(value) == path else load(value)

    monkeypatch.setattr(api, "load_plan", load_plan)
    with pytest.raises(AssertionError, match="Legacy predictions changed"):
        consume(tmp_path)
    assert path.read_bytes() == original


def test_selected_batch_installed_consumer_without_native_gpu_contact(tmp_path):
    load_script("ci_installed_acceptance")
    script = load_script("ci_inventory_check")
    actual = script.accept_selected_batch(tmp_path, dict(os.environ), hosted_native_absence=False)
    assert actual["literal_addition_mib"] == 784
    assert actual["legacy_default_parity_and_selected_refusal"]
    assert actual["legacy_prediction_equivalence_with_tool_change_retained"]
    assert actual["hosted_cpu_native_absence"] is None
    assert actual["deployment_ready"] is None and actual["all_saved_bytes_held"]
    assert {name: result["api_exit"] for name, result in actual["controls"].items()} == {
        "selected_pass": 0,
        "selected_shortfall": 5,
        "overlap": 4,
        "free_unavailable": 4,
        "missing": 5,
        "malformed": 4,
        "odd_context_pass": 0,
        "all_original_six": 0,
    }
    assert all(value["owned_children_closed"] for value in actual["controls"].values())
