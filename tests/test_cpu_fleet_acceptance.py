"""Adverse native-canary facts remain failures; these unit controls run no model."""

from __future__ import annotations

import pytest

from test_ci_acceptance import load_script


def report():
    return {
        "native_trace": {
            "requests": [
                {
                    "state": "completed",
                    "native": {"tokens_generated": 4},
                    "output_cap_state": "within_cap",
                    "times": {"start_s": i // 3, "terminal_s": i // 3 + 0.5},
                }
                for i in range(6)
            ]
        }
    }


def test_positive_cap_and_global_interval_controls():
    script = load_script("ci_cpu_fleet")
    actual = script.replay_controls(report())
    assert actual["positive_within_cap_rows"] == 6
    assert actual["peak_client_generation_intervals"] == actual["concurrency_limit"] == 3
    assert actual["physical_server_inflight"] == "unverified"


@pytest.mark.parametrize("fault", ["zero", "overcap", "unknown", "cap_state", "overconcurrency"])
def test_adverse_native_facts_cannot_qualify(fault):
    script = load_script("ci_cpu_fleet")
    data = report()
    rows = data["native_trace"]["requests"]
    if fault == "zero":
        rows[0]["native"]["tokens_generated"] = 0
    elif fault == "overcap":
        rows[0]["native"]["tokens_generated"] = 16
    elif fault == "unknown":
        rows[0]["native"]["tokens_generated"] = None
    elif fault == "cap_state":
        rows[0]["output_cap_state"] = "exceeded"
    else:
        for row in rows:
            row["times"] = {"start_s": 0, "terminal_s": 1}
    with pytest.raises(AssertionError):
        script.replay_controls(data)
