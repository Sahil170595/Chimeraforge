"""Installed server readiness distinguishes startup connection failures from request failures."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.fixture
def acceptance(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("ci_local_rest", SCRIPTS / "ci_local_rest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readiness_retries_connection_timeout_before_server_accepts(acceptance):
    process = Mock()
    process.poll.return_value = None
    response = httpx.Response(200, json={"status": "ok"})
    client = Mock()
    client.get.side_effect = [
        httpx.ConnectTimeout("startup"),
        httpx.ConnectError("startup"),
        response,
    ]
    pause = Mock()
    assert (
        acceptance.wait_for_health(client, "http://127.0.0.1:8765", process, sleep=pause)
        is response
    )
    assert pause.call_count == 2


def test_readiness_remains_bounded_and_reports_process_diagnostics(acceptance):
    process = Mock()
    process.poll.return_value = None
    client = Mock()
    client.get.side_effect = httpx.ConnectTimeout("startup")
    with pytest.raises(AssertionError, match="did not become ready"):
        acceptance.wait_for_health(
            client, "http://127.0.0.1:8765", process, clock=Mock(side_effect=[0, 21])
        )
    process.poll.return_value = 2
    process.communicate.return_value = ("", "bind failed")
    with pytest.raises(AssertionError, match="bind failed"):
        acceptance.wait_for_health(client, "http://127.0.0.1:8765", process)


def test_readiness_does_not_retry_a_response_timeout(acceptance):
    process = Mock()
    process.poll.return_value = None
    client = Mock()
    client.get.side_effect = httpx.ReadTimeout("hung server")
    with pytest.raises(httpx.ReadTimeout):
        acceptance.wait_for_health(client, "http://127.0.0.1:8765", process)
