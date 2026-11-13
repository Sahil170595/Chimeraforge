"""Run the actual native CLI/controlled transport consumer from source."""

import os

from test_ci_acceptance import load_script


def test_native_chat_actual_cli_all_backends_and_fleet_receiving(tmp_path):
    load_script("ci_installed_acceptance")
    actual = load_script("ci_chat_trace").accept(tmp_path, dict(os.environ))
    assert len(actual["profiles"]) == 8
    assert {r["backend"] for r in actual["profiles"]} == {"ollama", "vllm", "sglang", "tgi"}
    assert all(r["completed"] == 2 for r in actual["profiles"])
    assert actual["fleet"] == {"members": 3, "rows": 6, "native_completed": 6}
    assert actual["native_plan_save_load_chat_completed"] == 2
    assert actual["native_chat_POSTs"] == 24
    assert actual["native_diagnostic_API_CLI_text_equal"]
    assert actual["oversized_stopped_receipt_refused_without_HTTP"]
    assert actual["source_bytes_held"] and actual["late_invalid_precontact"]
    assert actual["unusable_receipt_precontact"] == [
        {"lane": lane, "exit_code": 2, "http_calls": 0}
        for lane in ("ordinary", "plan", "serial-campaign", "fleet", "fleet-campaign")
    ]
    assert actual["owned_HTTP_server_thread_joined"] and actual["owned_CLI_children_joined"]
