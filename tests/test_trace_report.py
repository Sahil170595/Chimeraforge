"""Strict native diagnostics retain the full declared population."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from test_ci_acceptance import load_script
from test_fleet_monitor import make_native_fleet


synthetic = load_script("ci_fleet_trace_gate").synthetic


@pytest.fixture(scope="module")
def native_diagnostic(tmp_path_factory):
    saved, _ = make_native_fleet(tpot_slo=1000)
    path = tmp_path_factory.mktemp("native-report") / "plan.json"
    saved.save(path)
    data = synthetic(path, duration=0.1)
    assert len(api.load_fleet_trace(data).to_dict()["slots"]) == 3
    assert len(data["native_trace"]["requests"]) == 6
    return data


def test_original_native_population_is_admitted(native_diagnostic):
    assert len(api.load_fleet_trace(native_diagnostic).to_dict()["slots"]) == 3


def test_public_fleet_render_retains_last_member_and_row(native_diagnostic):
    report = api.render_trace_report(native_diagnostic, kind="fleet-trace", format="html")
    assert 'data-member="3"' in report.content
    assert 'data-row="6"' in report.content


def test_cli_fleet_report_workflow(native_diagnostic, tmp_path):
    source = tmp_path / "fleet.json"
    source.write_text(json.dumps(native_diagnostic), encoding="utf-8")
    output = tmp_path / "fleet.html"
    result = CliRunner().invoke(
        app,
        [
            "report",
            "--kind",
            "fleet-trace",
            "--input",
            str(source),
            "--format",
            "html",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert output.read_bytes() == result.stdout_bytes


def test_all_formats_scope_privacy_and_xml(native_diagnostic):
    import xml.etree.ElementTree as ET
    from chimeraforge.bench.fleet_trace_receipt import native_projection
    from chimeraforge.bench.trace import TraceReplay

    ordinary = native_projection(native_diagnostic["native_trace"])
    for kind, source in (("trace", TraceReplay(ordinary)), ("fleet-trace", native_diagnostic)):
        for fmt in ("html", "markdown", "svg"):
            report = api.render_trace_report(
                source, kind=kind, format=fmt, title='<img src="https://title.invalid/x"> & \u03bb'
            )
            assert "server service time" in report.content
            assert "ci/manual-fleet" not in report.content
            assert "member-0.invalid" not in report.content
            assert "fixture-0" not in report.content
            assert "<img src=" not in report.content
            assert "https://title.invalid/x" in report.content.replace(
                "\\", ""
            )  # intentionally public title text
            assert "unavailable" in report.content
            if fmt == "svg":
                root = ET.fromstring(report.content)
                assert len(root.findall(".//{*}g[@data-row]")) == 6
                assert len(root.findall(".//{*}g[@data-member]")) == (
                    3 if kind == "fleet-trace" else 0
                )
                assert not root.findall(".//{*}script")
                assert not root.findall(".//{*}foreignObject")
            assert "\r" not in report.content and report.content.endswith("\n")


def test_generic_persistence_copy_replace_and_delayed_alias_guards(native_diagnostic, tmp_path):
    import copy
    from dataclasses import asdict, replace
    import os
    from chimeraforge.bench.fleet_trace_types import FleetTraceReplay

    source = tmp_path / "fleet.json"
    source.write_text(json.dumps(native_diagnostic), encoding="utf-8")
    secret = tmp_path / "private-input.pem"
    secret.write_bytes(b"private certificate canary")
    native = FleetTraceReplay(native_diagnostic, (secret,))
    report = api.render_trace_report(native, kind="fleet-trace")
    assert set(asdict(report)) == {"content", "kind", "format"}
    assert str(secret) not in json.dumps(asdict(report))
    for current in (report, copy.copy(report), copy.deepcopy(report), replace(report)):
        assert current._input_paths == (secret.absolute(),)
        with pytest.raises(api.PlanError):
            current.save(secret)
    from_file = api.render_trace_report(source, kind="fleet-trace")
    alias = tmp_path / "same.json"
    os.link(source, alias)
    before = source.read_bytes()
    with pytest.raises(api.PlanError):
        from_file.save(alias)
    assert source.read_bytes() == before
    assert secret.read_bytes() == b"private certificate canary"


def test_actual_held_file_guard_is_unioned_with_typed_guard(
    native_diagnostic, tmp_path, monkeypatch
):
    from chimeraforge.report import trace_inputs
    from chimeraforge.bench.trace import TraceReplay
    from chimeraforge.bench.fleet_trace_receipt import native_projection

    source, tls = tmp_path / "trace.json", tmp_path / "ca.pem"
    raw = native_projection(native_diagnostic["native_trace"])
    source.write_text(json.dumps(raw), encoding="utf-8")
    tls.write_bytes(b"certificate bytes")
    ordinary = TraceReplay(raw, (tls,))
    # Native ordinary held reader returns source separately; both input roles must survive.
    original = trace_inputs.hold
    held = original(source, "trace")
    held["protected_paths"] = (*held["protected_paths"], *ordinary._protected_paths)
    monkeypatch.setattr("chimeraforge.report.trace.hold", lambda *args: held)
    report = api.render_trace_report(source)
    for path in (source, tls):
        with pytest.raises(api.PlanError):
            report.save(path)


@pytest.mark.parametrize("kind", ["trace", "fleet-trace"])
def test_oversize_typed_input_refuses_before_native_copy(native_diagnostic, monkeypatch, kind):
    import copy
    from chimeraforge.bench.trace import TraceReplay
    from chimeraforge.bench.fleet_trace_types import FleetTraceReplay
    from chimeraforge.report import trace_inputs

    source = (
        TraceReplay(copy.deepcopy(native_diagnostic["native_trace"]))
        if kind == "trace"
        else FleetTraceReplay(copy.deepcopy(native_diagnostic))
    )
    monkeypatch.setattr(trace_inputs, "MAX_RECEIPT_BYTES", 100)
    monkeypatch.setattr(trace_inputs, "MAX_TOTAL_BYTES", 100)

    def forbidden_copy(*args, **kwargs):
        raise AssertionError("eager native copy happened before admission")

    monkeypatch.setattr(copy, "deepcopy", forbidden_copy)
    with pytest.raises(api.PlanError, match="bounded"):
        api.render_trace_report(source, kind=kind)


@pytest.mark.parametrize("fmt", ["html", "markdown", "svg"])
def test_exact_output_cap_and_no_publication(native_diagnostic, tmp_path, monkeypatch, fmt):
    from chimeraforge.report import trace as renderer

    report = api.render_trace_report(native_diagnostic, kind="fleet-trace", format=fmt)
    exact = len(report.content.encode("utf-8"))
    monkeypatch.setattr(renderer, "MAX_OUTPUT_BYTES", exact)
    assert api.render_trace_report(native_diagnostic, kind="fleet-trace", format=fmt) == report
    monkeypatch.setattr(renderer, "MAX_OUTPUT_BYTES", exact - 1)
    with pytest.raises(api.PlanError):
        api.render_trace_report(native_diagnostic, kind="fleet-trace", format=fmt)
    out = tmp_path / "held-artifact"
    out.write_bytes(b"prior")
    with pytest.raises(api.PlanError):
        report.save(out)
    assert out.read_bytes() == b"prior"


@pytest.mark.parametrize("title", ["", "x" * 201, "private\nline", "\ud800", "\x00", "\u202e"])
def test_invalid_public_title(native_diagnostic, title):
    with pytest.raises(api.PlanError):
        api.render_trace_report(native_diagnostic, kind="fleet-trace", title=title)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_strict_before_projection(native_diagnostic, value):
    import copy
    from chimeraforge.planner.replay import digest

    data = copy.deepcopy(native_diagnostic)
    data["controls"]["concurrency"] = value
    if type(value) is bool:
        data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    with pytest.raises(api.PlanError):
        api.render_trace_report(data, kind="fleet-trace")


@pytest.mark.parametrize(
    "kind", ["plan-trace", "trace-campaign", "fleet-trace-campaign", "benchmark"]
)
def test_no_implicit_unwrap(native_diagnostic, kind):
    with pytest.raises(api.PlanError):
        api.render_trace_report({"kind": kind, "native_trace": native_diagnostic["native_trace"]})


def test_cli_refuses_mixed_selectors_and_leaves_output(native_diagnostic, tmp_path):
    source, out = tmp_path / "source.json", tmp_path / "out.svg"
    source.write_text(json.dumps(native_diagnostic), encoding="utf-8")
    out.write_bytes(b"prior")
    base = ["report", "--kind", "fleet-trace", "--input", str(source), "--output", str(out)]
    for extra in (
        ["--json"],
        ["--results-files", str(source)],
        ["--results-dir", str(tmp_path)],
        ["--format", "unknown"],
    ):
        result = CliRunner().invoke(app, [*base, *extra])
        assert result.exit_code == 2
        assert result.stdout_bytes == b""
        assert out.read_bytes() == b"prior"


def test_native_adverse_all_states_planned_zero_and_zero_assigned(native_diagnostic, tmp_path):
    fixtures = load_script("ci_trace_report").fixtures

    saved, _ = make_native_fleet(tpot_slo=1000)
    path = tmp_path / "plan.json"
    saved.save(path)
    fleet, ordinary, planned = fixtures(path)
    for kind, data in (("trace", ordinary), ("fleet-trace", fleet)):
        for fmt in ("html", "svg", "markdown"):
            artifact = api.render_trace_report(data, kind=kind, format=fmt)
            assert "cancelled" in artifact.content and "not_started" in artifact.content
            assert "partial" in artifact.content and "failed" in artifact.content
            assert "unavailable" in artifact.content
            assert "native exit: 1" in artifact.content
            if kind == "fleet-trace":
                assert "zero_assigned" in artifact.content
            assert "0.0" in artifact.content or "| 0 |" in artifact.content
    assert "planned only" in api.render_trace_report(planned).content


def test_cli_explicit_title_equal_to_benchmark_default_is_preserved(native_diagnostic, tmp_path):
    source = tmp_path / "native.json"
    source.write_text(json.dumps(native_diagnostic), encoding="utf-8")
    title = "ChimeraForge Benchmark Report"
    expected = api.render_trace_report(source, kind="fleet-trace", format="html", title=title)
    result = CliRunner().invoke(
        app,
        [
            "report",
            "--kind",
            "fleet-trace",
            "--input",
            str(source),
            "--format",
            "html",
            "--title",
            title,
        ],
    )
    assert result.exit_code == 0
    assert result.stdout_bytes == expected.content.encode("utf-8")


def test_saved_input_is_read_once(native_diagnostic, tmp_path, monkeypatch):
    from chimeraforge import plan_bundle

    original = plan_bundle._read
    source = tmp_path / "native.json"
    source.write_text(json.dumps(native_diagnostic), encoding="utf-8")
    calls = []

    def read(path, limit):
        calls.append(path)
        assert len(calls) == 1
        return original(path, limit)

    monkeypatch.setattr(plan_bundle, "_read", read)
    assert api.render_trace_report(source, kind="fleet-trace").content
    assert calls == [source.absolute()]


def test_native_compact_count_is_not_pretty_admission(native_diagnostic, monkeypatch):
    from chimeraforge.report import trace_inputs

    raw = json.dumps(native_diagnostic, allow_nan=False).encode()
    assert len(json.dumps(native_diagnostic, indent=2).encode()) > len(raw)
    monkeypatch.setattr(trace_inputs, "MAX_TOTAL_BYTES", len(raw))
    assert api.render_trace_report(native_diagnostic, kind="fleet-trace").content


def test_finite_extreme_interval_geometry():
    import xml.etree.ElementTree as ET
    import math
    from test_trace_gate import receipt
    from chimeraforge.bench.trace_gate_inputs import load_trace

    data = receipt(duration=1e300, count=1, elapsed=1e300)
    assert load_trace(data)["data"] == data
    result = api.render_trace_report(data, format="svg")
    root = ET.fromstring(result.content)
    for element in root.iter():
        for key in ("x", "x1", "x2", "cx", "y", "y1", "y2", "cy", "width", "height"):
            if key in element.attrib:
                assert math.isfinite(float(element.attrib[key]))


@pytest.mark.parametrize("payload", [b"NaN", b'{"x":1,"x":2}', b"[]", b'{"secret-canary":1}'])
def test_malformed_saved_input_is_categorical_and_does_not_publish(tmp_path, payload):
    source, out = tmp_path / "bad.json", tmp_path / "prior.html"
    source.write_bytes(payload)
    out.write_bytes(b"prior")
    result = CliRunner().invoke(
        app, ["report", "--kind", "trace", "--input", str(source), "--output", str(out)]
    )
    assert result.exit_code == 2 and result.stdout_bytes == b""
    assert "secret-canary" not in result.output
    assert out.read_bytes() == b"prior"


def test_native_metadata_is_validated_before_privacy_omission():
    from test_trace_gate import receipt, seal

    data = receipt()
    canary = "closed-private-identity"
    data.update(model=canary, endpoint="https://closed-private.invalid", limits=canary)
    data["tool"]["version"] = canary
    data["serving_before"]["version"] = canary
    data["serving_after"]["version"] = canary
    from chimeraforge.bench.serving_binding import serving_stability

    data["serving_stability"] = serving_stability(data["serving_before"], data["serving_after"])
    seal(data)
    for fmt in ("html", "svg", "markdown"):
        rendered = api.render_trace_report(data, format=fmt)
        assert canary not in rendered.content and "closed-private.invalid" not in rendered.content
    data["serving_before"]["unexpected-private-field"] = canary
    seal(data)
    with pytest.raises(api.PlanError):
        api.render_trace_report(data)


def test_atomic_save_failure_is_categorical(native_diagnostic, tmp_path, monkeypatch):
    from pathlib import Path

    report = api.render_trace_report(native_diagnostic, kind="fleet-trace")
    target = tmp_path / "prior"
    target.write_bytes(b"prior")

    def fail(*args):
        raise OSError("private path/exception canary")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(api.PlanError, match="output unavailable") as error:
        report.save(target)
    assert error.value.__cause__ is None
    assert "private path" not in str(error.value)
    assert target.read_bytes() == b"prior" and not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "extra", [["--input", "repeat"], ["--results-files", ""], ["--results-dir", ""]]
)
def test_trace_cli_admits_exactly_one_input_and_no_explicit_legacy_selector(
    native_diagnostic, tmp_path, extra
):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(native_diagnostic), encoding="utf-8")
    extra = [str(source) if value == "repeat" else value for value in extra]
    result = CliRunner().invoke(
        app, ["report", "--kind", "fleet-trace", "--input", str(source), *extra]
    )
    assert result.exit_code == 2 and result.stdout_bytes == b""


def test_cli_default_title_matches_trace_api_default(native_diagnostic, tmp_path):
    source = tmp_path / "native.json"
    source.write_text(json.dumps(native_diagnostic), encoding="utf-8")
    expected = api.render_trace_report(source, kind="fleet-trace", format="html")
    result = CliRunner().invoke(
        app, ["report", "--kind", "fleet-trace", "--input", str(source), "--format", "html"]
    )
    assert result.exit_code == 0 and result.stdout_bytes == expected.content.encode("utf-8")


@pytest.mark.parametrize("separator", ["\u2028", "\u2029"])
def test_unicode_line_separators_are_not_single_line_titles(native_diagnostic, separator):
    with pytest.raises(api.PlanError):
        api.render_trace_report(
            native_diagnostic, kind="fleet-trace", title="first" + separator + "second"
        )


def _long_integer_receipt():
    from chimeraforge.bench import trace
    from chimeraforge.bench.trace_workload import TraceSLO, load_workload
    from chimeraforge.bench.trace_gate_inputs import load_trace

    requests = [
        api.TraceRequest("long-0", "private", 4, 0),
        api.TraceRequest("long-1", "private", 4, 0),
    ]
    rows = trace._initial_rows(requests)
    for i, row in enumerate(rows):
        row["state"] = "completed"
        row["times"].update(
            arrival_s=0,
            start_s=10**299 if i == 0 else 0,
            first_output_s=2 * 10**299 if i == 0 else 0,
            terminal_s=10**300 if i == 0 else 0,
        )
        row["native"].update(tokens_generated=4, eval_duration_ms=100)
        row.update(mean_tpot_ms=25.0, mean_tpot_basis="server-decode-duration/output-token-count")
    _, workload, _ = load_workload(requests)
    data = trace._report(
        requests,
        rows,
        workload=workload,
        targets=TraceSLO(latency_ms=2000),
        model="private",
        backend_name="ollama",
        base_url=None,
        concurrency=2,
        request_timeout=300,
        trace_timeout=600,
        cleanup={"state": "completed"},
        observation={},
        stop_reason=None,
        error=None,
        elapsed=10**301,
        origin=1000,
    )
    assert load_trace(data)["data"] == data
    return data


def test_native_long_integer_summary_is_completely_wrapped():
    import xml.etree.ElementTree as ET
    from test_trace_gate import receipt
    from chimeraforge.bench.trace_gate_inputs import load_trace

    data = receipt(duration=1e300, count=1, elapsed=10**301)
    assert load_trace(data)["data"] == data
    root = ET.fromstring(api.render_trace_report(data, format="svg").content)
    texts = [el.text or "" for el in root.findall(".//{*}text")]
    assert max(map(len, texts)) <= 150
    assert str(10**301) in "".join(texts)


def test_native_long_integer_rows_do_not_overlap():
    import xml.etree.ElementTree as ET

    root = ET.fromstring(api.render_trace_report(_long_integer_receipt(), format="svg").content)
    groups = root.findall(".//{*}g[@data-row]")
    last_first = max(float(el.attrib["y"]) for el in groups[0].findall("{*}text"))
    first_second = min(float(el.attrib["y"]) for el in groups[1].findall("{*}text"))
    assert last_first + 12 < first_second
