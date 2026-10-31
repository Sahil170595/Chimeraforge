"""Installed consumer composition uses actual source producers, not a native cluster."""

from __future__ import annotations

import os

from test_ci_acceptance import load_script
from test_kubernetes_export import native_plans as native_plans


def test_source_consumer_runs_both_engines_and_complete_junit(native_plans, tmp_path):
    script = load_script("ci_kubernetes_inspection")
    source = tmp_path / "source.json"
    native_plans[3][0].save(source)
    result = script.accept(tmp_path, dict(os.environ), source)
    assert len(result["controls"]) == 18
    assert {row["api_exit"] for row in result["controls"]} == {0, 4, 5}
    assert all(row["resources"] == 6 and row["junit_cases"] == 10 for row in result["controls"])
    assert result["raw_cli_byte_parity"] and result["owned_processes_closed"]
    assert result["source_unchanged"]
    assert result["loaded_modules_before"] is result["loaded_modules_after"] is None
