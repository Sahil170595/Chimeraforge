"""Actual source consumer and the parent/child handoff boundary."""

from __future__ import annotations

import os
import pytest

from test_ci_acceptance import load_script
from test_fleet_monitor import make_native_fleet


load_script("ci_fleet_trace_gate")
accept = load_script("ci_trace_report").accept


def test_native_api_and_raw_cli_consumer_retains_handoff(tmp_path):
    plan, _ = make_native_fleet(tpot_slo=1000)
    saved = tmp_path / "plan.json"
    plan.save(saved)
    handoff = tmp_path / "parent-owned"
    result = accept(tmp_path / "child-owned", dict(os.environ), saved, handoff=handoff)
    assert len(result["controls"]) == 6
    assert set(p.name for p in handoff.iterdir()) == {
        "api.html",
        "cli.html",
        "api.svg",
        "cli.svg",
        "edge-long-api.svg",
        "edge-long-cli.svg",
        "edge-unicode-api.svg",
        "edge-unicode-cli.svg",
    }
    for fmt in ("html", "svg"):
        assert (handoff / ("api." + fmt)).read_bytes() == (handoff / ("cli." + fmt)).read_bytes()
    assert result["source_aliases_refused"] and result["raw_cli_byte_parity"]


def test_distribution_handoff_is_parent_owned_and_argument_scoped(tmp_path, monkeypatch):
    pytest.importorskip("tomllib", reason="distribution controller runs native Python3.12")
    distribution = load_script("ci_distributions")

    calls = []
    monkeypatch.setattr(distribution, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    wheel = tmp_path / "wheel.whl"
    child = tmp_path / "inner-environment"
    parent = tmp_path / "parent-documents"
    distribution.accept(
        wheel, tmp_path, child, tmp_path / "requirements", "0.86.0", report_handoff=parent
    )
    command = next(
        args
        for args, _ in calls
        if any(str(a).endswith("ci_installed_acceptance.py") for a in args)
    )
    assert command[command.index("--trace-report-handoff") + 1] == parent
    assert not parent.is_relative_to(child)
