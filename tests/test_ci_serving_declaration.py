"""Run the installed consumer through source CLI; installed origins qualify separately."""

import os

from test_ci_acceptance import load_script


def test_operator_serving_actual_cli_api_and_native_receivers(tmp_path):
    load_script("ci_installed_acceptance")
    actual = load_script("ci_serving_declaration").accept(tmp_path, dict(os.environ))
    assert actual["logical_gpu_slots"] == 12 and actual["replicas"] == 3
    assert actual["owned_CLI_children_joined"] and actual["source_bytes_held"]
    assert actual["optimizer_misuse_refused"] and actual["aliases_and_invalid_layout_refused"]
    assert set(actual["profiles"]) == {"launch", "compose", "kubernetes"}
    assert {row["backend"] for row in actual["systemd"]} == {"vllm", "sglang"}
    assert all(
        row["replicas"] == 1
        and row["TP"] == row["PP"] == 2
        and row["explicit_devices"] == 4
        and row["match_exit"] == 0
        and row["drift_exit"] == row["independent_executable_drift_exit"] == 5
        and row["invalid_exit"] == 1
        and row["source_bytes_held"]
        and not row["service_started"]
        for row in actual["systemd"]
    )
    budget = actual["quote_budget"]
    assert len(budget["actual_cli_observed_snapshot_age"]) == 3
    assert budget["controlled_api_exit_codes"] == [0, 5, 4]
    assert budget["malformed_cli_exit"] == 1 and budget["unknown_cli_exit"] == 4
