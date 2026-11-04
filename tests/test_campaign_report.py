"""Whole native campaign presentation keeps every declared execution and member."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest

from chimeraforge import api
from chimeraforge.bench.trace_campaign_inputs import load_campaign
from test_fleet_monitor import make_native_fleet
from test_fleet_trace import endpoints, routes, workload
from test_ci_acceptance import load_script


@pytest.fixture
def campaign_consumer(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return load_script("ci_campaign_report")


@pytest.fixture
def stopped_campaigns(monkeypatch):
    saved, indices = make_native_fleet()

    def forbidden(*args, **kwargs):
        raise AssertionError("static/stopped diagnostics must not contact a backend")

    monkeypatch.setattr("httpx.AsyncClient.send", forbidden)

    async def produce():
        stopped = asyncio.Event()
        stopped.set()
        rows = [api.TraceRequest(f"row-{i}", f"PRIVATE PROMPT {i}", 8, 0) for i in range(2)]
        serial = await api.replay_trace_campaign(
            rows, model="private-controlled", replicates=3, stop_event=stopped
        )
        requests = workload(saved, indices["vllm"])
        fleet = await api.replay_fleet_trace_campaign(
            saved,
            requests,
            endpoints(),
            routes(requests, empty_last=True),
            executions=3,
            candidate_index=indices["vllm"],
            stop_event=stopped,
        )
        ordinary = await api.replay_trace(rows, model="private-controlled", stop_event=stopped)
        return serial, fleet, ordinary

    result = asyncio.run(produce())
    monkeypatch.setattr("chimeraforge.bench.trace.get_backend", forbidden)
    monkeypatch.setattr(api, "plan", forbidden)
    return result


def test_genuine_stopped_campaigns_and_ordinary_renderer_baseline(stopped_campaigns):
    serial, fleet, ordinary = stopped_campaigns
    assert len(load_campaign(serial)["replicas"]) == 3
    assert api.load_fleet_trace_campaign(fleet).to_dict()["execution"]["not_started"] == 3
    assert 'data-row="2"' in api.render_trace_report(ordinary, format="svg").content


@pytest.mark.parametrize("kind", ["trace-campaign", "fleet-trace-campaign"])
def test_api_renders_every_declared_stopped_execution(stopped_campaigns, kind):
    source = stopped_campaigns[int(kind == "fleet-trace-campaign")]
    report = api.render_trace_report(source, kind=kind, format="svg")
    assert report.kind == kind
    assert report.content.count('data-execution="') == 3
    assert 'data-execution="3"' in report.content
    assert report.content.count('data-row="') == (18 if kind == "fleet-trace-campaign" else 6)
    assert report.content.count('data-member="') == (9 if kind == "fleet-trace-campaign" else 0)
    assert "PRIVATE PROMPT" not in report.content
    assert "member-0.invalid" not in report.content
    assert "unavailable" in report.content


@pytest.mark.parametrize("kind", ["trace-campaign", "fleet-trace-campaign"])
def test_actual_os_cli_renders_complete_saved_campaign(stopped_campaigns, tmp_path, kind):
    source = stopped_campaigns[int(kind == "fleet-trace-campaign")]
    path = tmp_path / "input.json"
    source.save(path)
    before = path.read_bytes()
    output = tmp_path / "campaign.svg"
    args = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "chimeraforge.cli",
        "report",
        "--kind",
        kind,
        "--input",
        str(path),
        "--format",
        "svg",
        "--output",
        str(output),
    ]
    child = subprocess.run(
        args,
        cwd=tmp_path,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    (tmp_path / "cli.stdout").write_bytes(child.stdout)
    (tmp_path / "cli.stderr").write_bytes(child.stderr)
    assert child.returncode == 0, child.stderr.decode("utf-8")
    assert child.stdout == output.read_bytes()
    assert child.stdout.count(b'data-execution="') == 3
    assert path.read_bytes() == before


@pytest.fixture
def complete_campaigns(tmp_path, campaign_consumer):
    saved, _ = make_native_fleet(tpot_slo=1000)
    path = tmp_path / "plan.json"
    saved.save(path)
    return campaign_consumer.cases(path)


@pytest.mark.parametrize("fmt", ["html", "svg", "markdown"])
def test_all_returned_failed_missing_panels_and_original_rows(complete_campaigns, monkeypatch, fmt):
    import copy
    import xml.etree.ElementTree as ET

    def forbidden(*args, **kwargs):
        raise AssertionError("rendering must not resolve/plan/contact")

    monkeypatch.setattr(api, "plan", forbidden)
    monkeypatch.setattr("chimeraforge.bench.trace.get_backend", forbidden)
    for name, kind, data, count, rows, members in complete_campaigns:
        before = copy.deepcopy(data)
        report = api.render_trace_report(
            data, kind=kind, format=fmt, title='<script> & " \u6f22' * 3
        )
        assert data == before
        assert "no pooled" in report.content
        assert "ci/manual-fleet" not in report.content and "member-0.invalid" not in report.content
        assert "private-fixture-" not in report.content and "private prompt" not in report.content
        assert "<script>" not in report.content and "\r" not in report.content
        if fmt == "markdown":
            assert report.content.count("## Execution ") == count
            assert f"## Execution {count}/{count}" in report.content
        else:
            assert report.content.count('data-row="') == count * rows
            assert report.content.count('data-member="') == count * members
            assert report.content.count('data-execution="') == count
        if fmt == "svg":
            root = ET.fromstring(report.content)
            ids = [e.attrib["id"] for e in root.iter() if "id" in e.attrib]
            assert len(ids) == len(set(ids)) == count + 1
            assert all(
                e.attrib["aria-labelledby"] in ids
                for e in root.iter()
                if "aria-labelledby" in e.attrib
            )
            panels = root.findall("{*}g[@data-execution]")
            assert len(panels) == count
            previous_bottom = 0
            for panel in panels:
                child = panel.find("{*}svg")
                assert child is not None
                top = int(child.attrib["y"])
                bottom = top + int(child.attrib["height"])
                assert previous_bottom <= top < bottom <= int(root.attrib["viewBox"].split()[3])
                previous_bottom = bottom
            if name == "fleet-mixed":
                first, missing = panels[0], panels[-1]
                text = " ".join(first.itertext())
                assert "Tokens=0" in text and "zero_assigned" in text
                assert "declared rows=0" in " ".join(missing.itertext())
                assert all(
                    e.attrib["data-state"] == "unavailable"
                    for e in missing.findall(".//{*}g[@data-row]")
                )
                assert "attempted=unavailable" in " ".join(missing.itertext())
            if name == "serial-failed":
                assert "failed" in panels[0].attrib["data-execution-state"]
                assert "native exit: unavailable" in " ".join(panels[0].itertext())


@pytest.mark.parametrize("fmt", ["html", "svg", "markdown"])
def test_campaign_exact_complete_export_cap(complete_campaigns, monkeypatch, tmp_path, fmt):
    from chimeraforge.report import trace

    _, kind, data, *_ = complete_campaigns[-1]
    report = api.render_trace_report(data, kind=kind, format=fmt)
    exact = len(report.content.encode("utf-8"))
    monkeypatch.setattr(trace, "MAX_OUTPUT_BYTES", exact)
    assert api.render_trace_report(data, kind=kind, format=fmt).content == report.content
    monkeypatch.setattr(trace, "MAX_OUTPUT_BYTES", exact - 1)
    with pytest.raises(api.PlanError, match="output profile"):
        api.render_trace_report(data, kind=kind, format=fmt)
    target = tmp_path / "held-output"
    target.write_bytes(b"held")
    with pytest.raises(api.PlanError):
        report.save(target)
    assert target.read_bytes() == b"held"


@pytest.mark.parametrize("fleet", [False, True])
def test_late_invalid_full_input_refuses_before_render(complete_campaigns, monkeypatch, fleet):
    import copy

    _, kind, data, *_ = complete_campaigns[2 if fleet else 0]
    invalid = copy.deepcopy(data)
    invalid["executions" if fleet else "replicas"][-1]["index"] = 0

    def forbidden(*args, **kwargs):
        raise AssertionError("render started before complete native admission")

    monkeypatch.setattr("chimeraforge.report.trace_formats.svg", forbidden)
    with pytest.raises(api.PlanError):
        api.render_trace_report(invalid, kind=kind)


@pytest.mark.parametrize("fleet", [False, True])
def test_oversize_typed_campaign_admitted_before_copy(stopped_campaigns, monkeypatch, fleet):
    import copy

    source = stopped_campaigns[int(fleet)]
    source._data["unexpected"] = ["x" * 1024] * 20000

    def forbidden(*args, **kwargs):
        raise AssertionError("deep copy happened before bounded native admission")

    monkeypatch.setattr(copy, "deepcopy", forbidden)
    with pytest.raises(api.PlanError, match="bounded"):
        api.render_trace_report(source, kind="fleet-trace-campaign" if fleet else "trace-campaign")


def test_saved_source_alias_and_runtime_guards_survive_copies(complete_campaigns, tmp_path):
    import copy
    from dataclasses import asdict, replace
    import json

    _, kind, data, *_ = complete_campaigns[-1]
    source = tmp_path / "campaign.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    before = source.read_bytes()
    report = api.render_trace_report(source, kind=kind)
    alias = tmp_path / "alias"
    os.link(source, alias)
    assert set(asdict(report)) == {"content", "kind", "format"}
    assert str(source) not in json.dumps(asdict(report))
    for current in (report, copy.copy(report), copy.deepcopy(report), replace(report)):
        for path in (source, alias):
            with pytest.raises(api.PlanError):
                current.save(path)
    assert source.read_bytes() == before


def test_long_unicode_campaign_title_retains_native_wrapping(stopped_campaigns):
    import xml.etree.ElementTree as ET
    from chimeraforge.report.trace_formats import TITLE_WRAP_CHARS

    title = "\u6f22" * 160
    report = api.render_trace_report(
        stopped_campaigns[0], kind="trace-campaign", format="svg", title=title
    )
    root = ET.fromstring(report.content)
    lines = [e.text for e in root.findall("{*}text") if e.text and set(e.text) == {"\u6f22"}]
    assert "".join(lines) == title and max(map(len, lines)) <= TITLE_WRAP_CHARS
    first_panel = root.find("{*}g[@data-execution]")
    assert first_panel is not None
    first_svg = first_panel.find("{*}svg")
    assert first_svg is not None
    assert int(first_svg.attrib["y"]) > max(
        float(e.attrib["y"]) for e in root.findall("{*}text")[:-1]
    )


def test_native_chat_campaign_descriptors_are_admitted_without_private_text():
    async def produce():
        stopped = asyncio.Event()
        stopped.set()
        return await api.replay_trace_campaign(
            [
                api.ChatTraceRequest(
                    "chat",
                    (
                        api.ChatMessage("system", "PRIVATE SYSTEM"),
                        api.ChatMessage("user", "PRIVATE USER"),
                    ),
                    8,
                    0,
                    0.25,
                )
            ],
            model="private",
            replicates=3,
            stop_event=stopped,
        )

    report = api.render_trace_report(asyncio.run(produce()), kind="trace-campaign", format="svg")
    assert report.content.count('data-execution="') == 3
    assert report.content.count('data-row="') == 3
    assert "PRIVATE SYSTEM" not in report.content and "PRIVATE USER" not in report.content
