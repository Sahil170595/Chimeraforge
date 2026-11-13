"""Run the same exporter consumer used by installed artifact acceptance."""

import importlib
import os
from pathlib import Path

import pytest

from test_fleet_monitor import make_native_fleet


@pytest.mark.parametrize("tpot", [None, 1000])
def test_exporter_consumer_real_api_http_and_os_cli(tpot, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    consumer = importlib.import_module("ci_fleet_exporter")
    saved, indices = make_native_fleet(tpot_slo=tpot)
    path = tmp_path / "native.json"
    saved.save(path)
    result = consumer.accept(tmp_path, dict(os.environ), path, indices["vllm"])
    assert result["api"]["scrape_backend_requests"] == 0
    assert result["os_cli"]["scrape_backend_requests"] == 0
    assert (
        result["api"]["readiness_http_codes"]
        == result["secure_api"]["readiness_http_codes"]
        == [200, 503]
    )
    assert result["os_cli"]["readiness_http_code"] == 200
    assert all(
        result[mode]["readiness_backend_requests"] == 0 for mode in ("api", "secure_api", "os_cli")
    )
    assert result["source_bytes_held"] and result["late_invalid_precontact"]
