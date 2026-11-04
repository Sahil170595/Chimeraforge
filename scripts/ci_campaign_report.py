"""Whole saved campaign diagnostics: controlled/synthetic source facts, never inference."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

TITLE = '<img src="https://campaign-title.invalid/x"> & \u03bb campaign'


def mixed_fleet_campaign(saved: Path) -> dict:
    """Use native preparation/report/manifest builders with explicit synthetic clocks."""
    from chimeraforge import api
    from chimeraforge.bench.fleet_campaign import manifest_for
    from chimeraforge.bench.fleet_campaign_types import CAMPAIGN_LIMITS, KIND, canonical_hash
    from chimeraforge.bench.fleet_trace_inputs import prepare
    from ci_trace_report import fixtures

    child, _, _ = fixtures(saved)
    cap = child["controls"]["output_cap_tokens"]
    requests = [
        api.TraceRequest(f"private-fixture-{i}", "private prompt", cap, 0) for i in range(6)
    ]
    members = tuple(api.FleetEndpoint(row["id"], row["url"]) for row in child["endpoints"])
    prepared = prepare(
        saved,
        requests,
        members,
        [api.TraceRoute(row.request_id, members[i % 2].id) for i, row in enumerate(requests)],
        candidate_index=child["plan"]["candidate_index"],
        model=None,
        concurrency=3,
        request_timeout=300,
        trace_timeout=600,
        cleanup_timeout=2,
        stop_event=None,
    )
    manifest = manifest_for(prepared, 3, 90)
    slots = [
        {
            "index": 0,
            "manifest_fingerprint": manifest["fingerprint"],
            "state": "incomplete",
            "execution_complete": False,
            "reason": "native_incomplete",
            "error": None,
            "start_s": 1.0,
            "end_s": 2.1,
            "receipt": child,
        }
    ]
    slots.extend(
        {
            "index": i,
            "manifest_fingerprint": manifest["fingerprint"],
            "state": "not_started",
            "execution_complete": None,
            "reason": "first_incomplete_execution",
            "error": None,
            "start_s": None,
            "end_s": None,
            "receipt": None,
        }
        for i in (1, 2)
    )
    data = {
        "schema_version": 1,
        "kind": KIND,
        "created_at": child["created_at"],
        "tool": child["tool"],
        "manifest": manifest,
        "executions": slots,
        "execution": {"planned": 3, "completed": 0, "incomplete": 1, "failed": 0, "not_started": 2},
        "clock": {
            "basis": "client time.perf_counter monotonic offsets in seconds",
            "origin": 999,
            "elapsed_seconds": 2.2,
        },
        "stop_reason": "first_incomplete_execution",
        "state": "incomplete",
        "configuration_status": child["configuration_status"],
        "exit_code": 1,
        "cleanup": {
            "state": "completed",
            "owned_children": 1,
            "joined_children": 1,
            "owned_waiters": 0,
            "joined_waiters": 0,
        },
        "limits": CAMPAIGN_LIMITS,
    }
    data["fingerprint"] = canonical_hash(data)
    assert api.load_fleet_trace_campaign(data).to_dict() == data
    return data


def cases(saved: Path) -> list[tuple[str, str, dict, int, int, int]]:
    from ci_fleet_trace_campaign import matching_campaign
    from ci_trace_campaign_gate import failed_campaign, protocol_campaign

    return [
        ("serial-complete", "trace-campaign", protocol_campaign((0.12, 0.23, 0.17)), 3, 2, 0),
        ("serial-failed", "trace-campaign", failed_campaign(), 2, 2, 0),
        (
            "fleet-complete",
            "fleet-trace-campaign",
            matching_campaign(saved, [0.1, 0.2, 0.3]),
            3,
            6,
            3,
        ),
        ("fleet-mixed", "fleet-trace-campaign", mixed_fleet_campaign(saved), 3, 6, 3),
    ]


def accept(work: Path, env: dict, saved: Path, *, handoff: Path | None = None) -> dict:
    from chimeraforge import api
    from ci_trace_report import UNICODE_TITLE

    work.mkdir(parents=True, exist_ok=True)
    if handoff is not None:
        handoff.mkdir(parents=True, exist_ok=True)
    controls = []
    for name, kind, data, count, rows, members in cases(saved):
        title = UNICODE_TITLE if name == "serial-failed" else TITLE
        source = work / (name + ".json")
        source.write_text(json.dumps(data), encoding="utf-8")
        before = source.read_bytes()
        for fmt in ("html", "svg", "markdown"):
            artifact = api.render_trace_report(source, kind=kind, format=fmt, title=title)
            output = work / (name + "." + fmt)
            artifact.save(output)
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
                str(source),
                "--format",
                fmt,
                "--title",
                title,
                "--output",
                str(output),
            ]
            child = subprocess.run(
                args,
                cwd=work,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            assert child.returncode == 0, child.stderr.decode("utf-8")
            assert child.stdout == output.read_bytes() == artifact.content.encode("utf-8")
            assert source.read_bytes() == before
            for private in (
                "ci/manual-fleet",
                "private-fixture-",
                "member-0.invalid",
                "private prompt",
                str(source),
            ):
                assert private not in artifact.content
            if fmt != "markdown":
                assert artifact.content.count('data-execution="') == count
                assert artifact.content.count('data-row="') == count * rows
                assert artifact.content.count('data-member="') == count * members
                if handoff is not None:
                    for mode in ("api", "cli"):
                        raw = artifact.content.encode("utf-8") if mode == "api" else child.stdout
                        (handoff / f"campaign-{name}-{mode}.{fmt}").write_bytes(raw)
            controls.append(
                {
                    "case": name,
                    "kind": kind,
                    "format": fmt,
                    "executions": count,
                    "rows_per_execution": rows,
                    "original_members_per_execution": members,
                    "API_OSCLI_saved_bytes_equal": True,
                }
            )
    # A late malformed slot must not emit a partial document or touch its target.
    name, kind, data, *_ = cases(saved)[-1]
    broken = copy.deepcopy(data)
    broken["executions"][-1]["index"] = 0
    path = work / "late-invalid.json"
    path.write_text(json.dumps(broken), encoding="utf-8")
    target = work / "held-output.html"
    target.write_bytes(b"held output")
    child = subprocess.run(
        [
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
            "--output",
            str(target),
        ],
        cwd=work,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    assert child.returncode == 2 and not child.stdout and target.read_bytes() == b"held output"
    return {
        "controls": controls,
        "late_invalid_no_publication": True,
        "source_bytes_held": True,
        "scope": (
            "Native builders/strict receiving with explicit synthetic clocks and statuses; "
            "static API/actualOSCLI only, no backend/engine/browser or performance qualification."
        ),
    }


def record(path: Path, checkout: Path) -> None:
    import os
    import tempfile
    from chimeraforge import __version__
    from chimeraforge import api

    assert not path.exists()
    assert api.__file__ is not None and Path(api.__file__).resolve().is_relative_to(
        (checkout / "src/chimeraforge").resolve()
    )
    names = sorted(
        set(
            subprocess.check_output(
                [
                    "git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "src/chimeraforge",
                ],
                cwd=checkout,
            )
            .decode()
            .splitlines()
        )
        | {
            str(p.relative_to(checkout)).replace("\\", "/")
            for p in (checkout / "scripts").glob("ci_*.py")
        }
        | {
            "pyproject.toml",
            "server.json",
            "uv.lock",
            ".github/workflows/ci.yml",
        }
    )
    before = {name: hashlib.sha256((checkout / name).read_bytes()).hexdigest() for name in names}
    with tempfile.TemporaryDirectory(prefix="cf-campaign-report-") as directory:
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
    assert all(
        hashlib.sha256((checkout / n).read_bytes()).hexdigest() == value
        for n, value in before.items()
    )
    result.update(
        captured_at=datetime.now(timezone.utc).isoformat(),
        tool_version=__version__,
        source_profile="editable source; installed/browser separate",
        source_sha256=before,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    record(args.record, args.checkout)
