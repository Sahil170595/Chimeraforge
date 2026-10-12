"""Public index evidence must qualify the real installer's resolution path."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types

import pytest


def script():
    path = Path(__file__).parents[1] / "scripts" / "ci_registry_runtime.py"
    spec = importlib.util.spec_from_file_location("registry_readiness_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_file_visibility_waits_for_native_resolution(monkeypatch):
    module = script()
    requests, resolutions, sleeps = [], [], []

    def fetch(request, *, timeout):
        requests.append(request)
        assert 0 < timeout <= 15
        return io.BytesIO(json.dumps({}).encode())

    def resolve(version, timeout):
        resolutions.append((version, timeout))
        return len(resolutions) == 2

    monkeypatch.setattr(module, "urlopen", fetch)
    monkeypatch.setattr(module, "public_files_ready", lambda *args: True)
    monkeypatch.setattr(module, "public_resolution_ready", resolve, raising=False)
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    module.wait_for_public_files("0.57.0")
    assert len(resolutions) == 2 and len(sleeps) == 1
    simple = [request for request in requests if "/simple/" in request.full_url]
    assert len(simple) == 2
    assert all(
        request.get_header("Accept")
        == (
            "application/vnd.pypi.simple.v1+json, "
            "application/vnd.pypi.simple.v1+html;q=0.2, text/html;q=0.01"
        )
        for request in simple
    )


@pytest.mark.parametrize("status", [0, 1])
def test_native_readiness_uses_sdk_environment_and_dry_run(monkeypatch, status):
    module = script()
    from mcp.client import stdio

    sdk_environment = {"PATH": "approved-path", "HOME": "approved-home"}
    monkeypatch.setattr(stdio, "get_default_environment", lambda: sdk_environment)
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        error = (
            "Because there is no version of chimeraforge==0.57.0 "
            "and you require chimeraforge[mcp]==0.57.0"
        )
        return subprocess.CompletedProcess(command, status, "", error if status else "")

    monkeypatch.setattr(subprocess, "run", run)
    assert module.public_resolution_ready("0.57.0", 7) is (status == 0)
    assert len(calls) == 1
    command, options = calls[0]
    assert command == [
        "uv",
        "pip",
        "install",
        "--dry-run",
        "--reinstall",
        "--no-cache",
        "--python",
        sys.executable,
        "chimeraforge[mcp]==0.57.0",
    ]
    assert options["env"] is sdk_environment
    assert Path(options["cwd"]).resolve() == Path(tempfile.gettempdir()).resolve()
    assert options["timeout"] == 7 and options["capture_output"] is True


@pytest.mark.parametrize(
    "status,error",
    [
        (1, "Because there is no version of mcp==1.30.0 and you require mcp==1.30.0"),
        (
            1,
            "Because there is no version of chimeraforge==0.56.1 "
            "and you require chimeraforge==0.56.1",
        ),
        (1, "Connection failed: private-response-sentinel"),
        (
            2,
            "Because there is no version of chimeraforge==0.57.0 "
            "and you require chimeraforge==0.57.0",
        ),
    ],
)
def test_other_resolver_failures_are_not_index_retries(monkeypatch, status, error):
    module = script()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], status, "", error),
    )
    with pytest.raises(RuntimeError, match="resolution failed") as raised:
        module.public_resolution_ready("0.57.0", 7)
    assert "private-response-sentinel" not in str(raised.value)


def test_resolver_timeout_refuses_readiness(monkeypatch):
    module = script()

    def timed_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timed_out)
    with pytest.raises(subprocess.TimeoutExpired):
        module.public_resolution_ready("0.57.0", 0.01)


def test_candidate_qualifies_same_resolver_before_single_probe(monkeypatch, tmp_path):
    module = script()
    metadata = Path(__file__).parents[1] / "server.json"
    version = json.loads(metadata.read_text())["version"]
    (tmp_path / f"chimeraforge-{version}-py3-none-any.whl").write_bytes(b"candidate fixture")
    calls = []

    def resolve(expected, timeout, *, candidate_dist=None):
        assert expected == version and timeout == 60 and candidate_dist == tmp_path
        calls.append("resolve")
        return True

    def probe(command):
        assert "--find-links" in command
        calls.append("probe")
        return {"version": version}, []

    monkeypatch.setattr(module, "public_resolution_ready", resolve)
    monkeypatch.setitem(sys.modules, "probe_mcp_stdio", types.SimpleNamespace(probe=probe))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_registry_runtime",
            "--metadata",
            str(metadata),
            "--expect-version",
            version,
            "--candidate-dist",
            str(tmp_path),
        ],
    )
    assert module.main() == 0
    assert calls == ["resolve", "probe"]


def test_http_and_resolver_share_one_bounded_deadline(monkeypatch):
    module = script()
    now, budgets = [0.0], []

    def fetch(*args, **kwargs):
        now[0] += 0.2
        return io.BytesIO(b"{}")

    def resolve(version, timeout):
        budgets.append(timeout)
        return False

    def sleep(seconds):
        now[0] += seconds

    monkeypatch.setattr(module, "MAX_INDEX_WAIT_SECONDS", 2)
    monkeypatch.setattr(module, "urlopen", fetch)
    monkeypatch.setattr(module, "public_files_ready", lambda *args: True)
    monkeypatch.setattr(module, "public_resolution_ready", resolve)
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(module.time, "sleep", sleep)
    with pytest.raises(TimeoutError, match="deadline"):
        module.wait_for_public_files("0.57.0")
    assert budgets == [pytest.approx(1.6)] and now[0] == 2


def test_successful_late_resolution_cannot_escape_deadline(monkeypatch):
    module = script()
    now = [0.0]

    def resolve(version, timeout):
        now[0] = 301.0
        return True

    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: io.BytesIO(b"{}"))
    monkeypatch.setattr(module, "public_files_ready", lambda *args: True)
    monkeypatch.setattr(module, "public_resolution_ready", resolve)
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    with pytest.raises(TimeoutError, match="deadline"):
        module.wait_for_public_files("0.57.0")


def test_line_wrapped_exact_release_absence_is_recognized(monkeypatch):
    module = script()
    error = (
        "Because there is no version of chimeraforge==0.57.0 and\n"
        "  you require\n  chimeraforge[mcp]==0.57.0, resolution is unavailable"
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", error),
    )
    assert module.public_resolution_ready("0.57.0", 7) is False


def test_native_failure_diagnostic_identifies_loader_without_raw_body(monkeypatch, capsys):
    module = script()
    error = (
        "error: Failed to inspect Python interpreter\n"
        "error while loading shared libraries: libpython3.12.so.1.0: cannot open shared object file\n"
        "private-response-sentinel"
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "", error),
    )
    with pytest.raises(RuntimeError):
        module.public_resolution_ready("0.57.0", 7)
    output = capsys.readouterr().out
    diagnostic = json.loads(output)["uv_resolution_failure"]
    assert diagnostic["reason"] == "python_shared_library"
    assert diagnostic["library"] == "libpython3.12.so.1.0"
    assert diagnostic["version"] == "0.57.0" and diagnostic["exit_code"] == 2
    assert "private-response-sentinel" not in output
