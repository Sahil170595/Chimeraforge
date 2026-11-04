"""The installed consumer uses the same complete source API/OSCLI arc."""

from __future__ import annotations

import os

from test_campaign_report import campaign_consumer as campaign_consumer
from test_fleet_monitor import make_native_fleet


def test_native_campaign_consumer_actual_os_cli_without_backend_contact(
    tmp_path, campaign_consumer
):
    saved, _ = make_native_fleet(tpot_slo=1000)
    path = tmp_path / "plan.json"
    saved.save(path)
    handoff = tmp_path / "parent-documents"
    receipt = campaign_consumer.accept(
        tmp_path / "reports", dict(os.environ), path, handoff=handoff
    )
    assert len(receipt["controls"]) == 12
    assert receipt["late_invalid_no_publication"]
    assert len(list(handoff.iterdir())) == 16
    for case in ("serial-complete", "serial-failed", "fleet-complete", "fleet-mixed"):
        for fmt in ("html", "svg"):
            assert (handoff / f"campaign-{case}-api.{fmt}").read_bytes() == (
                handoff / f"campaign-{case}-cli.{fmt}"
            ).read_bytes()
