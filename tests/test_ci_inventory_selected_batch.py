"""The installed inventory seam must exercise actual producers and all selected slots."""

import os

from test_ci_acceptance import load_script


def test_selected_batch_installed_consumer_without_native_gpu_contact(tmp_path):
    load_script("ci_installed_acceptance")
    script = load_script("ci_inventory_check")
    actual = script.accept_selected_batch(tmp_path, dict(os.environ), hosted_native_absence=False)
    assert actual["literal_addition_mib"] == 784
    assert actual["legacy_default_parity_and_selected_refusal"]
    assert actual["legacy_prediction_equivalence_with_tool_change_retained"]
    assert actual["hosted_cpu_native_absence"] is None
    assert actual["deployment_ready"] is None and actual["all_saved_bytes_held"]
    assert {name: result["api_exit"] for name, result in actual["controls"].items()} == {
        "selected_pass": 0,
        "selected_shortfall": 5,
        "overlap": 4,
        "free_unavailable": 4,
        "missing": 5,
        "malformed": 4,
        "odd_context_pass": 0,
        "all_original_six": 0,
    }
    assert all(value["owned_children_closed"] for value in actual["controls"].values())
