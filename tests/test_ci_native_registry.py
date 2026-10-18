"""The native launch, rather than a second resolver, qualifies registry readiness."""

from __future__ import annotations

import importlib.util
import asyncio
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
VERSION = json.loads((SCRIPTS.parent / "server.json").read_text())["version"]


def helper():
    spec = importlib.util.spec_from_file_location(
        "native_registry_test", SCRIPTS / "ci_registry_runtime.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def absence():
    # Exact uv 0.12.23 diagnostic observed in the failed 0.66 registry job.
    return (
        "error: No solution found when resolving tool dependencies\n"
        f"  cause: Because there is no version of chimeraforge=={VERSION} and you require "
        f"chimeraforge=={VERSION}, we can conclude that your requirements are unsatisfiable.\n"
    )


def run_native(tmp_path, source, payload=b""):
    child = tmp_path / "native.py"
    child.write_text(source, encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    command = [sys.executable, "-B", str(child)]
    result = subprocess.run(
        helper().native_runner_command(command, VERSION, receipt),
        input=payload,
        capture_output=True,
        timeout=15,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return result, helper().read_native_receipt(receipt, command)


def test_native_absence_is_not_pip_dry_run_readiness(tmp_path):
    result, receipt = run_native(
        tmp_path, f"import sys\nsys.stderr.write({absence()!r})\nsys.exit(1)\n"
    )
    assert result.returncode == 1 and result.stdout == result.stderr == b""
    assert helper().retryable_native_absence(receipt)


@pytest.mark.parametrize(
    "suffix", ["private-response-sentinel", "\nHTTP status 503", "\nrequires Python >=9"]
)
def test_extra_stderr_never_retries_or_leaks(tmp_path, suffix):
    result, receipt = run_native(
        tmp_path, f"import sys\nsys.stderr.write({absence() + suffix!r})\nsys.exit(1)\n"
    )
    assert not helper().retryable_native_absence(receipt)
    assert b"private-response" not in result.stderr
    assert "private-response" not in json.dumps(receipt)


@pytest.mark.parametrize("raw", [b"\xff", b"{}\n", b"trailing"])
def test_any_raw_stdout_forbids_retry(tmp_path, raw):
    result, receipt = run_native(
        tmp_path,
        f"import sys\nsys.stdout.buffer.write({raw!r})\n"
        f"sys.stderr.write({absence()!r})\nsys.exit(1)\n",
    )
    assert result.stdout == raw and receipt["stdout_bytes"] == len(raw)
    assert not helper().retryable_native_absence(receipt)


@pytest.mark.parametrize("exit_code", [0, 2, 17])
def test_other_native_exits_forbid_retry(tmp_path, exit_code):
    _, receipt = run_native(
        tmp_path, f"import sys\nsys.stderr.write({absence()!r})\nsys.exit({exit_code})\n"
    )
    assert not helper().retryable_native_absence(receipt)


def test_stderr_overflow_forbids_retry(tmp_path):
    _, receipt = run_native(
        tmp_path,
        f"import sys\nsys.stderr.write({absence()!r} + 'x' * 100000)\nsys.exit(1)\n",
    )
    assert receipt["stderr_overflow"] and not helper().retryable_native_absence(receipt)


def test_stdin_and_stdout_are_byte_exact(tmp_path):
    payload = b'\x00\xff\r\n{"jsonrpc":"2.0"}\ntrailing'
    result, receipt = run_native(
        tmp_path, "import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n", payload
    )
    assert result.stdout == payload and result.stderr == b""
    assert receipt["native_exit"] == 0 and receipt["stdout_bytes"] == len(payload)


@pytest.mark.parametrize(
    "contents",
    [None, b"{}", b"not json", b"x" * 20000],
    ids=["missing", "empty", "json", "oversized"],
)
def test_missing_or_malformed_receipt_is_terminal(tmp_path, contents):
    path = tmp_path / "receipt.json"
    if contents is not None:
        path.write_bytes(contents)
    with pytest.raises(RuntimeError, match="receipt"):
        helper().read_native_receipt(path, ["uvx"])


def test_two_proven_absences_then_one_application(monkeypatch, tmp_path):
    module = helper()
    marker = tmp_path / "count"
    child = tmp_path / "native.py"
    child.write_text(
        "from pathlib import Path\nimport sys\n"
        f"p=Path({str(marker)!r})\nn=int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n+1))\n"
        f"if n < 2:\n sys.stderr.write({absence()!r})\n sys.exit(1)\n"
        "sys.stdout.write('application-started')\n",
        encoding="utf-8",
    )
    command = [sys.executable, "-B", str(child)]
    attempts = []

    def probe(wrapped, timeout):
        attempts.append(timeout)
        result = subprocess.run(wrapped, capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError("SDK connection closed")
        assert result.stdout == b"application-started"
        return {"version": VERSION}, ["offline-tools"]

    monkeypatch.setitem(sys.modules, "probe_mcp_stdio", types.SimpleNamespace(probe=probe))
    monkeypatch.setattr(module, "INDEX_POLL_SECONDS", 0)
    info, tools = module.probe_registry(command, VERSION, time.monotonic() + 15, retry_absence=True)
    assert info["version"] == VERSION and tools == ["offline-tools"]
    assert marker.read_text() == "3" and len(attempts) == 3
    assert attempts[0] > attempts[1] > attempts[2]


def test_application_failure_is_never_retried(monkeypatch, tmp_path):
    module = helper()
    count = []

    def probe(wrapped, timeout):
        count.append(1)
        subprocess.run(wrapped, capture_output=True, check=False, timeout=timeout)
        raise AssertionError("tool failed private-response-sentinel")

    monkeypatch.setitem(sys.modules, "probe_mcp_stdio", types.SimpleNamespace(probe=probe))
    with pytest.raises(RuntimeError, match="registry"):
        module.probe_registry(
            [sys.executable, "-c", "print('application-started')"],
            VERSION,
            time.monotonic() + 10,
            retry_absence=True,
        )
    assert count == [1]


def test_candidate_absence_does_not_retry(monkeypatch):
    module = helper()
    count = []

    def probe(wrapped, timeout):
        count.append(1)
        subprocess.run(wrapped, capture_output=True, check=False, timeout=timeout)
        raise RuntimeError("closed")

    monkeypatch.setitem(sys.modules, "probe_mcp_stdio", types.SimpleNamespace(probe=probe))
    with pytest.raises(RuntimeError, match="registry"):
        module.probe_registry(
            [sys.executable, "-c", f"import sys;sys.stderr.write({absence()!r});sys.exit(1)"],
            VERSION,
            time.monotonic() + 10,
            retry_absence=False,
        )
    assert count == [1]


def test_sdk_failure_without_complete_control_receipt_is_terminal(monkeypatch):
    module = helper()
    calls = []

    def probe(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("private-provider-sentinel")

    monkeypatch.setitem(sys.modules, "probe_mcp_stdio", types.SimpleNamespace(probe=probe))
    with pytest.raises(RuntimeError, match="control receipt"):
        module.probe_registry(["uvx"], VERSION, time.monotonic() + 10, retry_absence=True)
    assert calls == [1]


def test_supervisor_rejects_completed_receipt_for_another_argv(monkeypatch):
    module = helper()
    calls = []

    def probe(wrapped, timeout):
        calls.append(1)
        subprocess.run(wrapped, capture_output=True, timeout=timeout)
        path = Path(wrapped[wrapped.index("--receipt") + 1])
        receipt = json.loads(path.read_text())
        receipt["command_sha256"] = module.command_digest(["different-command"])
        path.write_text(json.dumps(receipt))
        raise RuntimeError("connection closed")

    monkeypatch.setitem(sys.modules, "probe_mcp_stdio", types.SimpleNamespace(probe=probe))
    with pytest.raises(RuntimeError, match="control receipt"):
        module.probe_registry(
            [sys.executable, "-c", f"import sys;sys.stderr.write({absence()!r});sys.exit(1)"],
            VERSION,
            time.monotonic() + 10,
            retry_absence=True,
        )
    assert calls == [1]


def test_supervisor_preserves_cancellation(monkeypatch):
    module = helper()

    def probe(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setitem(sys.modules, "probe_mcp_stdio", types.SimpleNamespace(probe=probe))
    with pytest.raises(asyncio.CancelledError):
        module.probe_registry(["uvx"], VERSION, time.monotonic() + 10, retry_absence=True)


@pytest.mark.parametrize("late_success", [False, True])
def test_native_attempt_cannot_escape_total_deadline(monkeypatch, late_success):
    module = helper()
    now = [1.0]
    budgets = []

    def probe(command, timeout):
        budgets.append(timeout)
        now[0] = 9
        if late_success:
            return {"version": VERSION}, []
        raise TimeoutError

    monkeypatch.setitem(sys.modules, "probe_mcp_stdio", types.SimpleNamespace(probe=probe))
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    with pytest.raises(TimeoutError, match="deadline"):
        module.probe_registry(["uvx"], VERSION, 8, retry_absence=True)
    assert budgets == [7]


@pytest.mark.parametrize("mode", ["public", "candidate"])
def test_main_shares_deadline_and_keeps_native_command(monkeypatch, tmp_path, mode):
    module = helper()
    metadata_path = SCRIPTS.parent / "server.json"
    now = [1.0]
    calls = []
    args = ["ci_registry_runtime", "--metadata", str(metadata_path), "--expect-version", VERSION]
    candidate = None
    if mode == "public":
        args.append("--wait-pypi")
    else:
        candidate = tmp_path
        (candidate / f"chimeraforge-{VERSION}-py3-none-any.whl").write_bytes(b"inventory")
        args += ["--candidate-dist", str(candidate)]

    def visible(version, deadline):
        calls.append(("files", version, deadline))
        now[0] += 12

    def probe(command, version, deadline, *, retry_absence):
        calls.append(("native", command, deadline, retry_absence))
        return {"version": VERSION}, []

    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(module, "wait_for_public_files", visible)
    monkeypatch.setattr(module, "probe_registry", probe)
    assert module.main() == 0
    expected = module.registry_command(json.loads(metadata_path.read_text()), VERSION, candidate)
    if mode == "public":
        assert calls == [("files", VERSION, 301), ("native", expected, 301, True)]
    else:
        assert calls == [("native", expected, 121, False)]


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_exit", True),
        ("stdout_bytes", -1),
        ("stderr_bytes", 0),
        ("stderr_overflow", True),
        ("root_absent", "yes"),
        ("command_sha256", "wrong"),
        ("schema", 2),
    ],
)
def test_control_receipt_rejects_type_and_identity_drift(tmp_path, field, value):
    module = helper()
    _, receipt = run_native(tmp_path, f"import sys;sys.stderr.write({absence()!r});sys.exit(1)")
    receipt[field] = value
    path = tmp_path / "altered.json"
    path.write_text(json.dumps(receipt))
    with pytest.raises(RuntimeError, match="receipt"):
        module.read_native_receipt(path, [sys.executable, "-B", str(tmp_path / "native.py")])


@pytest.mark.parametrize(
    "field,value",
    [
        ("root_absent", False),
        ("reaped", False),
        ("drained", False),
        ("stream_error", True),
        ("stderr_overflow", True),
    ],
)
def test_incomplete_native_evidence_forbids_retry(tmp_path, field, value):
    _, receipt = run_native(tmp_path, f"import sys;sys.stderr.write({absence()!r});sys.exit(1)")
    receipt[field] = value
    assert not helper().retryable_native_absence(receipt)


@pytest.mark.parametrize(
    "error",
    [
        absence().replace("tool dependencies", "dependencies"),
        absence() + " hint: requires Python >=3.13",
        "HTTP status code 503\n" + absence(),
        absence().replace(f"chimeraforge=={VERSION}", "mcp==1.30.0"),
        absence().replace(f"chimeraforge=={VERSION}", f"chimeraforge[mcp]=={VERSION}"),
        absence().split("cause: ")[1],
        absence().replace("unsatisfiable.", "unavailable."),
    ],
)
def test_only_complete_pinned_native_absence_matches(error):
    assert not helper().native_root_absence(error, VERSION)


def test_exact_registry_and_candidate_argv(tmp_path):
    module = helper()
    metadata = json.loads((SCRIPTS.parent / "server.json").read_text())
    expected = ["uvx", "--no-cache", "--with", f"chimeraforge[mcp]=={VERSION}"]
    assert module.registry_command(metadata, VERSION) == expected + [
        f"chimeraforge@{VERSION}",
        "mcp",
    ]
    (tmp_path / f"chimeraforge-{VERSION}-py3-none-any.whl").write_bytes(b"test inventory only")
    assert module.registry_command(metadata, VERSION, tmp_path) == expected + [
        "--find-links",
        str(tmp_path.resolve()),
        f"chimeraforge@{VERSION}",
        "mcp",
    ]


def test_real_offline_mcp_application_is_qualified_once(monkeypatch):
    pytest.importorskip("mcp")
    monkeypatch.syspath_prepend(str(SCRIPTS))
    command = [
        sys.executable,
        "-B",
        "-c",
        (
            f"import sys;sys.path.insert(0, {str(SCRIPTS.parent / 'src')!r});"
            "from chimeraforge.mcp_server import main;main()"
        ),
    ]
    info, tools = helper().probe_registry(
        command, VERSION, time.monotonic() + 25, retry_absence=True
    )
    assert info["version"] == VERSION and len(tools) == 5


def test_real_sdk_native_absence_twice_then_one_offline_application(monkeypatch, tmp_path):
    pytest.importorskip("mcp")
    monkeypatch.syspath_prepend(str(SCRIPTS))
    module = helper()
    monkeypatch.setattr(module, "INDEX_POLL_SECONDS", 0)
    marker = tmp_path / "launch-count"
    child = tmp_path / "native.py"
    child.write_text(
        "from pathlib import Path\nimport sys\n"
        f"p=Path({str(marker)!r})\nn=int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n+1))\n"
        f"if n < 2:\n sys.stderr.write({absence()!r})\n sys.exit(1)\n"
        f"sys.path.insert(0, {str(SCRIPTS.parent / 'src')!r})\n"
        "from chimeraforge.mcp_server import main\nmain()\n",
        encoding="utf-8",
    )
    info, tools = module.probe_registry(
        [sys.executable, "-B", str(child)],
        VERSION,
        time.monotonic() + 25,
        retry_absence=True,
    )
    assert info["version"] == VERSION and len(tools) == 5
    assert marker.read_text() == "3"


@pytest.mark.parametrize("stage", ["initialize", "tool"])
def test_real_sdk_application_failure_never_retries(monkeypatch, tmp_path, stage):
    pytest.importorskip("mcp")
    monkeypatch.syspath_prepend(str(SCRIPTS))
    marker = tmp_path / "launch-count"
    child = tmp_path / "native.py"
    source = (
        "from pathlib import Path\nimport json,sys\n"
        f"p=Path({str(marker)!r})\np.write_text(p.read_text()+'x' if p.exists() else 'x')\n"
        "sys.stderr.write('private-response-sentinel')\n"
    )
    if stage == "initialize":
        source += (
            "request=json.loads(sys.stdin.buffer.readline())\n"
            "print(json.dumps({'jsonrpc':'2.0','id':request['id'],"
            "'error':{'code':-32603,'message':'private-response-sentinel'}}),flush=True)\n"
        )
    else:
        source += (
            "from mcp.server.fastmcp import FastMCP\nserver=FastMCP('offline-failure')\n"
            "def invalid(): return {'ok':False}\n"
            "for name in ['chimeraforge_plan','chimeraforge_resolve_model',"
            "'chimeraforge_compare_api','chimeraforge_suggest','chimeraforge_list_hardware']:\n"
            " server.add_tool(invalid,name=name)\nserver.run()\n"
        )
    child.write_text(source, encoding="utf-8")
    output = io.StringIO()
    with redirect_stdout(output), pytest.raises(RuntimeError, match="registry"):
        helper().probe_registry(
            [sys.executable, "-B", str(child)],
            VERSION,
            time.monotonic() + 15,
            retry_absence=True,
        )
    assert marker.read_text() == "x"
    assert "private-response-sentinel" not in output.getvalue()


@pytest.mark.parametrize("stage", ["resolution", "application"])
@pytest.mark.parametrize("cancel", [False, True], ids=["deadline", "cancellation"])
def test_sdk_cancellation_reaps_native_child_and_descendant(tmp_path, monkeypatch, stage, cancel):
    pytest.importorskip("mcp")
    psutil = pytest.importorskip("psutil")
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import probe_mcp_stdio

    marker = tmp_path / "started.json"
    child = tmp_path / "native.py"
    prefix = (
        "import asyncio,json,os,subprocess,sys,time\nfrom pathlib import Path\n"
        "descendant=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'])\n"
        f"marker=Path({str(marker)!r})\n"
    )
    mark = "marker.write_text(json.dumps([os.getpid(),descendant.pid]))\n"
    if stage == "resolution":
        source = prefix + mark + "time.sleep(60)\n"
    else:
        source = prefix + (
            "from mcp.server.fastmcp import FastMCP\nserver=FastMCP('offline-cancel')\n"
            "@server.tool(name='chimeraforge_list_hardware')\nasync def hardware():\n "
            + mark
            + " await asyncio.sleep(60)\n"
            "def unused(): return {}\n"
            "for name in ['chimeraforge_plan','chimeraforge_resolve_model',"
            "'chimeraforge_compare_api','chimeraforge_suggest']:\n"
            " server.add_tool(unused,name=name)\n"
            "server.run()\n"
        )
    child.write_text(source, encoding="utf-8")
    receipt_path = tmp_path / "receipt.json"
    command = [sys.executable, "-B", str(child)]
    wrapped = helper().native_runner_command(command, VERSION, receipt_path)

    async def exercise():
        task = asyncio.create_task(probe_mcp_stdio.exercise(wrapped, 20))
        limit = time.monotonic() + 10
        while not marker.exists() and not task.done() and time.monotonic() < limit:
            await asyncio.sleep(0.02)
        assert marker.exists(), "native fixture did not reach the expected stage"
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(task, 0.1)

    asyncio.run(exercise())
    pids = json.loads(marker.read_text())
    alive = [pid for pid in pids if psutil.pid_exists(pid)]
    assert alive == [], f"SDK-owned native process tree survived shutdown: {alive}"
    assert not receipt_path.exists(), "cancelled/unreaped launch must not provide a retry receipt"
