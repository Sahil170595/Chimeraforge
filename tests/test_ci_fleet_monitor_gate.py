"""Same installed consumer on the source CLI/API, including actual byte stdout."""

from test_ci_acceptance import load_script
import test_fleet_monitor_receipt as native_receipts

monitor_source = native_receipts.monitor_source


def test_complete_native_passive_gate_consumer(monitor_source, tmp_path):
    import os

    load_script("ci_secure_monitor")
    load_script("ci_installed_acceptance")
    script = load_script("ci_fleet_monitor_gate")
    saved = tmp_path / "plan.json"
    monitor_source[0].save(saved)

    result = script.accept(tmp_path, dict(os.environ), saved)
    assert len(result["controls"]) == len(result["output_aliases"]) == 6
    assert [row["api_gate_exit"] for row in result["controls"]] == [0, 1, 3, 0, 1, 3]
    assert result["source_and_tls_input_bytes_unchanged"]
