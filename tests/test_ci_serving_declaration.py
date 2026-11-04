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
