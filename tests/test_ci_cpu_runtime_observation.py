"""Runtime diagnostics retain bounded facts without qualifying CPU placement."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_ci_acceptance import load_script


@pytest.fixture
def runtime():
    return load_script("ci_cpu_runtime_observation")


def launch(ngl="0", *, extra=""):
    return (
        "time=2026-10-18T03:36:19.500Z level=INFO source=llama_server.go:436 "
        'msg="starting llama-server" '
        f'cmd="/private/bin/llama-server --model /private/model -ngl {ngl}{extra}"\n'
    )


def startup(*, amx="51.31", gpu="", layers="0/31"):
    return (
        launch()
        + f"load_tensors: offloaded {layers} layers to GPU\n"
        + "load_tensors: CPU_Mapped model buffer size = 100.00 MiB\n"
        + f"load_tensors: AMX model buffer size = {amx} MiB\n"
        + gpu
        + "llama_kv_cache: CPU KV buffer size = 23.50 MiB\n"
        + "sched_reserve: CPU compute buffer size = 2.00 MiB\n"
        + "srv  llama_server: model loaded\n"
    )


def test_amx_is_separate_descriptive_evidence_without_cpu_verdict(runtime):
    report = runtime.runtime_observation(startup().encode())
    assert report["startup_facts_complete"] is True
    (record,) = report["records"]
    assert record["ngl"] == 0 and record["ngl_state"] == "known"
    assert record["offloaded_layers"] == 0 and record["total_layers"] == 31
    assert record["buffer_bytes"] == {"cpu": int(125.5 * 1024**2), "amx": 53802434, "gpu": 0}
    assert {row["backend"] for row in record["buffers"]} == {"cpu", "amx"}
    assert "device" not in report and "cpu_qualified" not in report


@pytest.mark.parametrize("backend", ["CUDA0", "ROCm1", "Vulkan2", "MTL3_Mapped"])
def test_actual_gpu_buffer_stays_positive_alongside_amx(runtime, backend):
    line = f"load_tensors: {backend} model buffer size = 12.25 MiB\n"
    report = runtime.runtime_observation(startup(gpu=line, layers="1/31").encode())
    (record,) = report["records"]
    assert record["buffer_bytes"]["gpu"] == int(12.25 * 1024**2)
    assert record["buffer_bytes"]["amx"] == 53802434
    assert report["startup_facts_complete"] is True


def test_reloads_and_repeated_buffer_lines_never_sum_across_instances(runtime):
    first = startup().replace(
        "srv  llama_server: model loaded\n",
        "sched_reserve: CPU compute buffer size = 3.00 MiB\nsrv  llama_server: model loaded\n",
    )
    report = runtime.runtime_observation((first + startup(amx="2.00")).encode())
    assert [r["index"] for r in report["records"]] == [1, 2]
    assert [r["buffer_bytes"]["amx"] for r in report["records"]] == [53802434, 2097152]
    assert report["records"][0]["buffer_bytes"]["cpu"] == int(126.5 * 1024**2)
    assert len(report["records"][0]["buffers"]) == 4
    assert "buffer_bytes" not in report


@pytest.mark.parametrize(
    "change",
    [
        lambda text: text.replace("AMX", "private-token-/secret"),
        lambda text: text.replace("load_tensors: AMX", "private_label: AMX"),
        lambda text: text.replace("51.31 MiB", "NaN MiB"),
        lambda text: text.replace("51.31 MiB", "-1 MiB"),
        lambda text: text.replace("51.31 MiB", "99999999999999999999999999999999 MiB"),
        lambda text: text.replace("0/31 layers", "32/31 layers"),
        lambda text: text.replace("srv  llama_server: model loaded\n", ""),
        lambda text: text.replace("-ngl 0", "--temperature 0"),
        lambda text: text.replace("-ngl 0", "-ngl 0 -ngl 1"),
        lambda text: text.replace("-ngl 0", "-ngl private-token-/secret"),
        lambda text: text.replace("time=2026", "unrecognized=2026"),
        lambda text: text + "load_tensors: offloaded 1/31 layers to GPU\n",
    ],
)
def test_unknown_or_incomplete_facts_cannot_be_complete_or_leak_text(runtime, change):
    report = runtime.runtime_observation(change(startup()).encode())
    assert report["startup_facts_complete"] is False
    encoded = json.dumps(report)
    assert "private" not in encoded and "secret" not in encoded
    assert "llama-server" not in encoded and "temperature" not in encoded


def test_orphan_startup_facts_and_missing_log_do_not_claim_complete(runtime):
    report = runtime.runtime_observation(startup().split("\n", 1)[1].encode())
    assert report["records"] == []
    assert report["unbound_startup_lines"] > 0
    assert report["startup_facts_complete"] is False
    empty = runtime.runtime_observation(b"")
    assert empty["startup_facts_complete"] is False


def test_binary_truncation_bad_encoding_and_overlong_lines_are_explicit(runtime):
    truncated = runtime.runtime_observation(startup().encode(), truncated=True)
    assert truncated["log_truncated"] is True
    assert truncated["startup_facts_complete"] is False
    invalid = runtime.runtime_observation(startup().encode() + b"\xff\n")
    assert invalid["decode_errors"] is True
    assert invalid["startup_facts_complete"] is False
    long_line = runtime.runtime_observation(
        startup().encode() + b"secret" * runtime.MAX_LINE_BYTES + b"\n"
    )
    assert long_line["overlong_lines"] == 1
    assert long_line["startup_facts_complete"] is False
    assert "secret" not in json.dumps(long_line)
    partial = runtime.runtime_observation(startup().encode().rstrip(b"\n"))
    assert partial["partial_line"] is True
    assert partial["startup_facts_complete"] is False


def test_record_bound_does_not_assign_dropped_reload_buffers_to_prior_record(runtime):
    text = startup() * runtime.MAX_RECORDS + startup(amx="2.00")
    report = runtime.runtime_observation(text.encode())
    assert len(report["records"]) == runtime.MAX_RECORDS
    assert report["record_limit_exceeded"] is True
    assert report["records"][-1]["buffer_bytes"]["amx"] == 53802434
    assert report["startup_facts_complete"] is False


def test_oversized_offload_number_is_incomplete_without_raising(runtime):
    text = startup(layers=("9" * 5000) + "/31")
    report = runtime.runtime_observation(text.encode())
    assert report["startup_facts_complete"] is False
    assert report["records"][0]["offload_state"] == "invalid"


def test_unreadable_reload_boundary_cannot_change_previous_record(runtime):
    text = (
        startup()
        + launch(extra="x" * runtime.MAX_LINE_BYTES)
        + startup(amx="2.00").split("\n", 1)[1]
    )
    report = runtime.runtime_observation(text.encode())
    assert report["overlong_lines"] == 1
    assert report["records"][0]["buffer_bytes"]["amx"] == 53802434
    assert report["unbound_startup_lines"] > 0
    assert report["startup_facts_complete"] is False


def test_buffer_entry_and_total_byte_limits_are_explicit(runtime, monkeypatch):
    monkeypatch.setattr(runtime, "MAX_BUFFER_ENTRIES", 2)
    report = runtime.runtime_observation(startup().encode())
    assert report["records"][0]["buffer_limit_exceeded"] is True
    assert report["startup_facts_complete"] is False
    monkeypatch.setattr(runtime, "MAX_BUFFER_ENTRIES", 256)
    monkeypatch.setattr(runtime, "MAX_MEMORY_BYTES", 2 * 1024**2)
    report = runtime.runtime_observation(startup(amx="1.0").encode())
    assert report["records"][0]["invalid_startup_lines"] > 0
    assert report["startup_facts_complete"] is False


def test_reader_is_bounded_and_never_emits_file_error_details(runtime, monkeypatch):
    reads = []

    class Reader(io.BytesIO):
        def read(self, size=-1):
            assert size >= 0, "unbounded read"
            reads.append(size)
            return super().read(size)

    data = startup().encode() + b"x" * runtime.MAX_LOG_BYTES
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: Reader(data))
    report = runtime.read_runtime_observation(Path("/private/log"))
    assert reads == [runtime.MAX_LOG_BYTES + 1]
    assert report["log_bytes_read"] == runtime.MAX_LOG_BYTES
    assert report["log_truncated"] is True
    assert report["startup_facts_complete"] is False

    def fail(*_args, **_kwargs):
        raise OSError("private-token-/secret")

    monkeypatch.setattr(Path, "open", fail)
    report = runtime.read_runtime_observation(Path("/private/log"))
    assert report["log_state"] == "unavailable"
    assert report["startup_facts_complete"] is False
    assert "private" not in json.dumps(report) and "secret" not in json.dumps(report)


def test_failure_projection_prints_before_bounded_existing_tail(runtime, monkeypatch):
    reads = []

    class Reader(io.BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= runtime.MAX_LOG_BYTES + 1
            reads.append(size)
            return super().read(size)

    data = startup().encode() + b"existing-tail\n"
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: Reader(data))
    output = io.StringIO()
    runtime.print_runtime_failure(Path("/private/log"), stream=output)
    first, tail = output.getvalue().split("\n", 1)
    assert json.loads(first)["cpu_runtime_observation"]["records"][0]["ngl"] == 0
    assert "existing-tail" in tail
    assert len(reads) == 2


@pytest.mark.parametrize("inherited_repack", [None, "1"])
def test_cpu_exclusions_apply_to_copy_for_owned_server_only(runtime, inherited_repack):
    original = {"CUDA_VISIBLE_DEVICES": "0", "PRIVATE": "secret", "OLLAMA_HOST": "local"}
    if inherited_repack is not None:
        original["LLAMA_ARG_REPACK"] = inherited_repack
    result = runtime.cpu_server_environment(original)
    assert result == original | {
        "CUDA_VISIBLE_DEVICES": "-1",
        "ROCR_VISIBLE_DEVICES": "-1",
        "GGML_VK_VISIBLE_DEVICES": "-1",
        "OLLAMA_VULKAN": "0",
        "LLAMA_ARG_REPACK": "0",
    }
    assert original["CUDA_VISIBLE_DEVICES"] == "0"
    assert "OLLAMA_VULKAN" not in original
    assert original.get("LLAMA_ARG_REPACK") == inherited_repack


@pytest.mark.parametrize("outcome", ["success", "accept_failure", "cleanup_failure"])
def test_harness_scopes_server_env_and_emits_success_or_failure_facts(
    runtime, tmp_path, monkeypatch, capsys, outcome
):
    script = load_script("ci_cpu_serving")
    checkpoint = load_script("ci_checkpoint_identity")
    monkeypatch.setattr(checkpoint, "accept", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(script, "assert_installed_origin", lambda *_args: None)
    monkeypatch.setattr(script, "platform", SimpleNamespace(machine=lambda: "x86_64"))
    monkeypatch.setattr(script, "sys", SimpleNamespace(platform="linux", exc_info=sys.exc_info))
    monkeypatch.setattr(
        script,
        "tempfile",
        SimpleNamespace(TemporaryDirectory=lambda **_kwargs: nullcontext(str(tmp_path))),
    )
    monkeypatch.setattr(
        script, "download", lambda _url, destination, _sha: destination.write_bytes(b"fixture")
    )
    monkeypatch.setattr(script, "wait_until_ready", lambda *_args: None)
    calls = []

    def execute(argv, **kwargs):
        calls.append((argv, kwargs))

    def spawn(argv, **kwargs):
        calls.append((argv, kwargs))
        kwargs["stdout"].write(startup())
        return SimpleNamespace(pid=12345, poll=lambda: None, wait=lambda **_kwargs: 0)

    monkeypatch.setattr(
        script,
        "subprocess",
        SimpleNamespace(
            run=execute,
            Popen=spawn,
            STDOUT=subprocess.STDOUT,
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )

    def terminate(*_args):
        if outcome == "cleanup_failure":
            raise RuntimeError("synthetic cleanup failure")

    parent_env = {"CUDA_VISIBLE_DEVICES": "0", "PRIVATE": "secret", "LLAMA_ARG_REPACK": "1"}
    monkeypatch.setattr(script, "os", SimpleNamespace(environ=parent_env, killpg=terminate))
    client = SimpleNamespace(
        get=lambda _endpoint: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"models": [{"size_vram": 0}]},
        )
    )
    monkeypatch.setattr(
        script, "httpx", SimpleNamespace(Client=lambda **_kwargs: nullcontext(client))
    )

    def accept(*_args):
        if outcome == "accept_failure":
            raise AssertionError("synthetic acceptance failure")
        return {"fixture": True}

    monkeypatch.setattr(script, "accept_runtime", accept)
    from chimeraforge import __version__

    argv = ["--expect-version", __version__, "--checkout", str(tmp_path / "checkout")]
    if outcome == "success":
        assert script.main(argv) == 0
    else:
        expected = AssertionError if outcome == "accept_failure" else RuntimeError
        with pytest.raises(expected, match="synthetic"):
            script.main(argv)
    stdout, stderr = capsys.readouterr()
    if outcome != "accept_failure":
        assert json.loads(stdout)["runtime_observation"]["startup_facts_complete"] is True
    if outcome != "success":
        first, tail = stderr.split("\n", 1)
        assert json.loads(first)["cpu_runtime_observation"]["records"][0]["ngl"] == 0
        assert 'msg="starting llama-server"' in tail
    (server_call,) = [kwargs for argv_, kwargs in calls if argv_[-1] == "serve"]
    (create_call,) = [kwargs for argv_, kwargs in calls if "create" in argv_]
    assert server_call["env"]["CUDA_VISIBLE_DEVICES"] == "-1"
    assert server_call["env"]["OLLAMA_VULKAN"] == "0"
    assert server_call["env"]["LLAMA_ARG_REPACK"] == "0"
    assert create_call["env"]["CUDA_VISIBLE_DEVICES"] == "0"
    assert create_call["env"]["LLAMA_ARG_REPACK"] == "1"
    assert "OLLAMA_VULKAN" not in create_call["env"]
    assert parent_env == {"CUDA_VISIBLE_DEVICES": "0", "PRIVATE": "secret", "LLAMA_ARG_REPACK": "1"}
