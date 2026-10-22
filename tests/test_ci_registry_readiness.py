"""Public-file visibility and categorical resolver diagnostics remain separate evidence."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest


def script():
    path = Path(__file__).parents[1] / "scripts" / "ci_registry_runtime.py"
    spec = importlib.util.spec_from_file_location("registry_readiness_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_file_visibility_does_not_claim_native_resolution(monkeypatch, capsys):
    module = script()
    requests = []

    def fetch(request, timeout):
        requests.append((request.full_url, request.get_header("Accept"), timeout))
        return io.BytesIO(b"{}")

    monkeypatch.setattr(module, "urlopen", fetch)
    monkeypatch.setattr(module, "public_files_ready", lambda *args: True)
    monkeypatch.setattr(module.time, "monotonic", lambda: 1)
    module.wait_for_public_files("0.66.0", 8)
    assert len(requests) == 2 and [row[2] for row in requests] == [7, 7]
    assert requests[1][1] == module.UV_SIMPLE_ACCEPT
    event = json.loads(capsys.readouterr().out)["pypi_index_readiness"]
    assert event["files_ready"] is True and "resolver_ready" not in event
    assert not hasattr(module, "public_resolution_ready")


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503])
def test_http_errors_other_than_404_are_terminal(monkeypatch, code):
    module = script()

    def fetch(request, timeout):
        raise HTTPError(request.full_url, code, "private-response-sentinel", {}, None)

    monkeypatch.setattr(module, "urlopen", fetch)
    with pytest.raises(HTTPError) as caught:
        module.wait_for_public_files("0.66.0", module.time.monotonic() + 10)
    assert caught.value.code == code


def test_404_visibility_retry_stays_within_shared_deadline(monkeypatch):
    module = script()
    now = [0.0]
    budgets = []

    def fetch(request, timeout):
        budgets.append(timeout)
        now[0] += 0.2
        raise HTTPError(request.full_url, 404, "not yet indexed", {}, None)

    monkeypatch.setattr(module, "urlopen", fetch)
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(module.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    with pytest.raises(TimeoutError, match="deadline"):
        module.wait_for_public_files("0.66.0", 2)
    assert budgets == [2, 1.8] and now[0] == 2


def test_late_http_success_cannot_escape_deadline(monkeypatch):
    module = script()
    now = [0.0]

    def fetch(*args, **kwargs):
        now[0] += 0.6
        return io.BytesIO(b"{}")

    monkeypatch.setattr(module, "urlopen", fetch)
    monkeypatch.setattr(module, "public_files_ready", lambda *args: True)
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    with pytest.raises(TimeoutError, match="deadline"):
        module.wait_for_public_files("0.66.0", 1)


@pytest.mark.parametrize(
    "clause,shape,names",
    [
        ("there is no version of chimeraforge==0.61.0", "singleton", ["chimeraforge"]),
        ("there are no versions of chimeraforge", "plural", ["chimeraforge"]),
        ("there is no version of chimeraforge[mcp]==0.61.0", "extra", ["chimeraforge"]),
        ("there are no versions of mcp", "none", ["mcp"]),
        ("there are no versions of private-package-sentinel", "none", []),
    ],
)
def test_resolution_context_logs_only_public_aggregate_facts(clause, shape, names):
    module = script()
    error = (
        f"No solution found. Because {clause}; requires Python >=3.13. "
        "https://owner:secret@private.test/path?token=secret private-response-sentinel"
    )
    context = module.resolution_context(error, "0.61.0", {"chimeraforge", "mcp"})
    assert context["no_solution"] is True and context["root_absence_shape"] == shape
    assert context["missing_public_packages"] == names
    assert context["cause_hints"] == ["requires_python"]
    encoded = json.dumps(context)
    assert "secret" not in encoded and "private" not in encoded and "https" not in encoded


@pytest.mark.parametrize(
    "error,hint",
    [
        ("No compatible wheel tags", "wheel_tag"),
        ("Invalid metadata from upstream", "invalid_metadata"),
        ("HTTP status code 503 for private-response-sentinel", "http_status"),
        (
            "An index URL (https://private.test) could not be queried (401 Unauthorized)",
            "http_status",
        ),
        ("An index (https://private.test) returned a 403 Forbidden error", "http_status"),
        ("requires-python >=3.13", "requires_python"),
        (
            "The Python interpreter uses a Python version "
            "that is not supported by your dependencies",
            "requires_python",
        ),
        ("we only found wheels with the following Python ABI tags", "wheel_tag"),
        ("we only found wheels with the following Python implementation tags", "wheel_tag"),
        (
            "Metadata for mcp (v1.30) could not be parsed: private-response-sentinel",
            "invalid_metadata",
        ),
        (
            "Metadata for mcp (v1.30) could not be fetched; "
            "the server returned: 503 private-response-sentinel",
            "http_status",
        ),
        ("private-response-sentinel", "unknown"),
    ],
)
def test_resolution_hint_categories_are_bounded(error, hint):
    module = script()
    context = module.resolution_context(error, "0.61.0", {"chimeraforge"})
    assert context["cause_hints"] == [hint]
    assert "private-response-sentinel" not in json.dumps(context)
