"""The same campaign protocol consumer runs from source and installed distributions."""

from __future__ import annotations

import os

from test_fleet_monitor import native_fleet as native_fleet
from test_ci_acceptance import load_script


def test_real_protocol_campaign_api_cli_and_synthetic_gates(native_fleet, tmp_path):
    for name in (
        "ci_secure_monitor",
        "ci_native_stream",
        "ci_fleet_trace",
        "ci_fleet_trace_gate",
        "ci_installed_acceptance",
    ):
        load_script(name)
    script = load_script("ci_fleet_trace_campaign")
    saved, _ = native_fleet
    source = tmp_path / "plan.json"
    saved.save(source)
    result = script.accept(tmp_path, dict(os.environ), source)
    assert len(result["protocol_controls"]) == 8
    assert [item["api_exit"] for item in result["synthetic_gate_controls"]] == [0, 1, 3]
    assert len(result["tls_alias_controls"]) == 6
    assert len(result["secure_admission"]) == 2
    assert result["fixture_resources"] == "closed"
