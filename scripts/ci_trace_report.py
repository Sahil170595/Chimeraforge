"""Whole native trace diagnostics: software fixtures, never serving measurements."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import cast

TITLE = '<img src="https://title.invalid/x" onerror="alert(1)"> & \u03bb diagnostics'
UNICODE_TITLE = '<img src="https://title.invalid/x">' + "\u6f22" * 160

SOURCE_FILES = (
    "src/chimeraforge/report/trace.py",
    "src/chimeraforge/report/trace_inputs.py",
    "src/chimeraforge/report/trace_view.py",
    "src/chimeraforge/report/trace_formats.py",
    "src/chimeraforge/commands/report.py",
    "src/chimeraforge/api.py",
    "scripts/ci_trace_report.py",
    "scripts/ci_trace_report_browser.py",
    "src/chimeraforge/bench/trace.py",
    "src/chimeraforge/bench/trace_gate_inputs.py",
    "src/chimeraforge/bench/gate_inputs.py",
    "src/chimeraforge/bench/fleet_trace_receipt.py",
    "src/chimeraforge/bench/fleet_trace_types.py",
    "src/chimeraforge/planner/replay.py",
    "scripts/ci_fleet_trace_gate.py",
    "scripts/ci_installed_acceptance.py",
    "scripts/ci_distributions.py",
)


def fixtures(saved: Path) -> tuple[dict, dict, dict]:
    """Native constructors and strict readers qualify schema; statuses/times are synthetic."""
    import copy
    from chimeraforge import api
    from chimeraforge.bench import trace
    from chimeraforge.bench.fleet_trace_inputs import prepare
    from chimeraforge.bench.fleet_trace_receipt import make_report, native_projection
    from chimeraforge.bench.trace_gate_inputs import load_trace
    from chimeraforge.bench.trace_workload import TraceRequest, TraceSLO, load_workload
    from ci_fleet_trace_gate import synthetic

    original = synthetic(saved, duration=0.1)
    index = original["plan"]["candidate_index"]
    cap = original["controls"]["output_cap_tokens"]
    requests = [TraceRequest(f"private-fixture-{i}", "private prompt", cap, 0) for i in range(6)]
    members = tuple(api.FleetEndpoint(row["id"], row["url"]) for row in original["endpoints"])
    routes = [api.TraceRoute(row.request_id, members[i % 2].id) for i, row in enumerate(requests)]
    prepared = prepare(
        saved,
        requests,
        members,
        routes,
        candidate_index=index,
        model=None,
        concurrency=3,
        request_timeout=300,
        trace_timeout=600,
        cleanup_timeout=2,
        stop_event=None,
    )
    rows = trace._initial_rows(requests)
    for index, state in enumerate(
        ("completed", "failed", "partial", "cancelled", "not_started", "completed")
    ):
        row = rows[index]
        row.update(state=state, endpoint_id=routes[index].endpoint_id)
        if state != "not_started":
            row["times"].update(arrival_s=0, terminal_s=0)
        if state in {"completed", "failed", "partial"}:
            row["times"]["start_s"] = 0
        if state in {"completed", "partial"}:
            row["times"]["first_output_s"] = 0
        if state in {"failed", "partial"}:
            row["error"] = {"stage": "generation", "type": "TimeoutError"}
        if state == "completed":
            row["native"].update(tokens_generated=0, prompt_tokens=0, cached_prompt_tokens=0)
    rows[-1]["times"].update(arrival_s=0.1, start_s=0.2, first_output_s=0.3, terminal_s=0.5)
    native = trace._report(
        requests,
        rows,
        workload=prepared.plan.workload,
        targets=prepared.plan.slos,
        model=prepared.plan.served_model,
        backend_name="vllm",
        base_url=None,
        concurrency=3,
        request_timeout=300,
        trace_timeout=600,
        cleanup={"state": "completed"},
        observation={},
        stop_reason="cancelled",
        error=None,
        elapsed=1,
        origin=1000,
    )
    resources = [
        {"before": slot["serving_before"], "after": slot["serving_after"], "error": None}
        for slot in original["slots"]
    ]
    fleet = make_report(prepared, native, resources, copy.deepcopy(original["cleanup"]))
    assert len(api.load_fleet_trace(fleet).to_dict()["slots"]) == 3
    ordinary = native_projection(native)
    assert load_trace(ordinary)["data"] == ordinary
    _, workload, _ = load_workload(requests)
    planned = trace._report(
        requests,
        trace._initial_rows(requests),
        workload=workload,
        targets=TraceSLO(),
        model="private planned model",
        backend_name="vllm",
        base_url=None,
        concurrency=3,
        request_timeout=300,
        trace_timeout=600,
        cleanup={"state": "completed"},
        observation={},
        stop_reason=None,
        error={"stage": "preflight", "type": "RuntimeError"},
        elapsed=0,
        origin=None,
    )
    assert load_trace(planned)["data"] == planned
    return fleet, ordinary, planned


def long_integer_trace() -> dict:
    """Valid finite native integer facts, not observed physical runtimes."""
    from chimeraforge import api
    from chimeraforge.bench import trace
    from chimeraforge.bench.trace_workload import TraceSLO, load_workload
    from chimeraforge.bench.trace_gate_inputs import load_trace

    requests = [api.TraceRequest(f"private-long-{i}", "private", 4, 0) for i in range(2)]
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
    return cast(dict, data)


def accept(work: Path, env: dict, saved: Path, *, handoff: Path | None = None) -> dict:
    from chimeraforge import api
    from chimeraforge.bench.fleet_trace_types import FleetTraceReplay
    from chimeraforge.bench.trace import TraceReplay

    work.mkdir(parents=True, exist_ok=True)
    fleet, ordinary, planned = fixtures(saved)
    controls = []
    for kind, data in (("trace", ordinary), ("fleet-trace", fleet)):
        source = work / (kind + ".json")
        source.write_text(json.dumps(data), encoding="utf-8")
        before = source.read_bytes()
        for fmt in ("html", "svg", "markdown"):
            output = work / (kind + "." + fmt)
            rendered = api.render_trace_report(source, kind=kind, format=fmt, title=TITLE)
            rendered.save(output)
            assert output.read_bytes() == rendered.content.encode("utf-8")
            assert (
                ('data-row="6"' in rendered.content)
                if fmt != "markdown"
                else ("| 6 |" in rendered.content)
            )
            for private in (
                "private-fixture-",
                "ci/manual-fleet",
                "member-0.invalid",
                "private prompt",
            ):
                assert private not in rendered.content
            cli = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "chimeraforge",
                    "report",
                    "--kind",
                    kind,
                    "--input",
                    str(source),
                    "--format",
                    fmt,
                    "--title",
                    TITLE,
                    "--output",
                    str(output),
                ],
                cwd=work,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=60,
            )
            assert (
                cli.returncode == 0
                and cli.stdout == output.read_bytes() == rendered.content.encode("utf-8")
            )
            assert b"Traceback" not in cli.stderr
            if handoff is not None and kind == "fleet-trace" and fmt in {"html", "svg"}:
                handoff.mkdir(parents=True, exist_ok=True)
                (handoff / ("api." + fmt)).write_bytes(rendered.content.encode("utf-8"))
                (handoff / ("cli." + fmt)).write_bytes(cli.stdout)
            controls.append({"kind": kind, "format": fmt, "api_cli_raw_byte_parity": True})
        assert source.read_bytes() == before
        try:
            rendered.save(source)
        except api.PlanError:
            pass
        else:
            raise AssertionError("held source alias was accepted")
    for kind, typed in (("trace", TraceReplay(ordinary)), ("fleet-trace", FleetTraceReplay(fleet))):
        text = api.render_trace_report(typed, kind=kind, format="markdown").content
        assert "unavailable" in text and "cancelled" in text and "not_started" in text
        assert "0.0" in text or "| 0 |" in text
    assert "planned only" in api.render_trace_report(planned, format="markdown").content
    adverse = []
    for name, invalid in (
        ("plan-envelope", {"kind": "plan-trace", "native_trace": ordinary}),
        ("fingerprint", {**ordinary, "fingerprint": "0" * 64}),
    ):
        try:
            api.render_trace_report(invalid)
        except api.PlanError:
            adverse.append(name)
        else:
            raise AssertionError("malformed presentation input accepted")
    source = work / "trace.json"
    before = source.read_bytes()
    refused = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "chimeraforge",
            "report",
            "--kind",
            "trace",
            "--input",
            str(source),
            "--output",
            str(source),
        ],
        cwd=work,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
    )
    assert refused.returncode == 2 and not refused.stdout and source.read_bytes() == before
    adverse.append("raw-cli-source-alias")
    from chimeraforge.report import trace as renderer

    held_limit = renderer.MAX_OUTPUT_BYTES
    try:
        renderer.MAX_OUTPUT_BYTES = 1
        try:
            api.render_trace_report(fleet, kind="fleet-trace")
        except api.PlanError:
            adverse.append("lowered-whole-output-bound")
        else:
            raise AssertionError("whole output bound ignored")
    finally:
        renderer.MAX_OUTPUT_BYTES = held_limit
    edges = []
    for name, data, title in (
        ("long", long_integer_trace(), "Long integer diagnostics"),
        ("unicode", planned, UNICODE_TITLE),
    ):
        source = work / ("edge-" + name + ".json")
        source.write_text(json.dumps(data), encoding="utf-8")
        artifact = api.render_trace_report(source, format="svg", title=title)
        output = work / ("edge-" + name + ".svg")
        artifact.save(output)
        cli = subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "chimeraforge",
                "report",
                "--kind",
                "trace",
                "--input",
                str(source),
                "--format",
                "svg",
                "--title",
                title,
                "--output",
                str(output),
            ],
            cwd=work,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=60,
        )
        assert cli.returncode == 0 and cli.stdout == output.read_bytes() == artifact.content.encode(
            "utf-8"
        )
        if handoff is not None:
            (handoff / ("edge-" + name + "-api.svg")).write_bytes(artifact.content.encode("utf-8"))
            (handoff / ("edge-" + name + "-cli.svg")).write_bytes(cli.stdout)
        edges.append(
            {
                "case": name,
                "rows": len(data["requests"]),
                "members": 0,
                "api_cli_raw_byte_parity": True,
            }
        )
    return {
        "controls": controls,
        "adverse_controls": adverse,
        "edge_controls": edges,
        "original_members": len(fleet["slots"]),
        "requests": len(fleet["native_trace"]["requests"]),
        "row_states": len({r["state"] for r in fleet["native_trace"]["requests"]}),
        "zero_assigned_members": 1,
        "planned_only_retained": True,
        "source_aliases_refused": True,
        "raw_cli_byte_parity": True,
        "scope": "synthetic native statuses and timings; no traffic or browser execution",
    }


def record(path: Path, checkout: Path) -> None:
    import os
    import tempfile
    from chimeraforge import api

    assert api.__file__ is not None and Path(api.__file__).resolve().is_relative_to(
        (checkout / "src" / "chimeraforge").resolve()
    )
    with tempfile.TemporaryDirectory(prefix="cf-trace-report-record-") as directory:
        work = Path(directory)
        saved = work / "plan.json"
        api.plan(
            api.PlanRequest(
                models=["ci/manual-fleet"],
                overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                hardware="RTX 4090 24GB",
                platform="linux",
                tensor_parallel=2,
                request_rate=128,
                latency_slo=10000,
                tpot_slo=1000,
                quality_target=0,
                budget=1e8,
                allow_network=False,
            )
        ).save(saved)
        result = accept(work, dict(os.environ), saved)
    result.update(
        captured_at=datetime.now(timezone.utc).isoformat(),
        source_profile="editable source; installed and browser proofs separate",
        source_sha256={
            name: hashlib.sha256((checkout / name).read_bytes()).hexdigest()
            for name in SOURCE_FILES
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    record(args.record, args.checkout)
