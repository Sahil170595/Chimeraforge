"""Local systemd intent from declarations without optimizer or engine execution."""

from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from chimeraforge import api
from chimeraforge.cli import app
from typer.testing import CliRunner


def declaration(backend="vllm", **changes):
    return api.declare_serving(
        replace(
            api.ServingRequest(
                model="org/model",
                revision="a" * 40,
                backend=backend,
                image="example/engine:1",
                tensor_parallel=2,
                pipeline_parallel=2,
                context_length=8192,
                batch_size=8,
                kv_quant="q8",
                prefix_caching=True,
                max_num_batched_tokens=512 if backend == "vllm" else None,
            ),
            **changes,
        )
    )


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_native_declaration_unit_export_verify_without_saved_plan(tmp_path, backend):
    held = declaration(backend)
    out = tmp_path / "serving.service"
    rendered = api.export_serving_declaration(
        held, format="systemd", executable="/usr/bin/true", gpu_devices=list("0123")
    )
    out.write_bytes(rendered.content.encode("utf-8"))
    assert rendered.format == "systemd" and rendered.backend == backend
    assert rendered.content.startswith("# Serving declaration " + held.fingerprint + "\n")
    assert "# Saved plan" not in rendered.content and not rendered.files
    assert 'Environment="CUDA_VISIBLE_DEVICES=0,1,2,3"' in rendered.content
    assert '"--host" "127.0.0.1"' in rendered.content
    assert ('"--port" "8000"' if backend == "vllm" else '"--port" "30000"') in rendered.content
    assert (
        'ExecStart="/usr/bin/true" "serve"'
        if backend == "vllm"
        else 'ExecStart="/usr/bin/true" "-m" "sglang.launch_server"'
    ) in rendered.content
    assert '"--revision" "' + "a" * 40 + '"' in rendered.content
    checked = api.verify_serving_declaration(
        held, out, format="systemd", executable="/usr/bin/true", gpu_devices=list("0123")
    )
    assert checked.exit_code == 0 and checked.change_count == 0
    assert checked.source_kind == "artifact_snapshot"


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_actual_os_cli_systemd_uses_original_declaration_and_independent_intent(tmp_path, backend):
    held = declaration(backend)
    source, out = tmp_path / "operator.json", tmp_path / "serving.service"
    held.save(source)
    original = source.read_bytes()
    flags = ["--declaration", str(source), "--format", "systemd", "--executable", "/usr/bin/true"]
    for device in "0123":
        flags += ["--gpu-device", device]

    def cli(operation, *extra, expected=0):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "chimeraforge.cli",
                "serving",
                operation,
                *flags,
                *extra,
                "--json",
            ],
            cwd=tmp_path,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        assert result.returncode == expected and not result.stderr
        return json.loads(result.stdout)

    assert cli("export", "--out", str(out))["status"] == "exported"
    assert cli("verify", "--config", str(out))["exit_code"] == 0
    out.write_bytes(out.read_bytes() + b"# changed\n")
    drift = cli("verify", "--config", str(out), expected=5)
    assert drift["changes"] == [{"path": "/unit", "category": "content", "count": 1}]
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"executable": "relative"},
        {"executable": "C:\\engine.exe"},
        {"executable": "/bad\nExecStart=evil"},
        {"executable": "/bad\\engine"},
        {"executable": " /engine"},
        {"executable": "/bad\0engine"},
    ],
)
def test_executable_requires_explicit_lexical_posix_path(tmp_path, options):
    with pytest.raises(api.ServingDeclarationError):
        api.export_serving_declaration(
            declaration(), format="systemd", gpu_devices=list("0123"), **options
        )


@pytest.mark.parametrize(
    "options",
    [
        {"host_port": 9001},
        {"replica_gpu_devices": [list("0123")]},
        {"replica_host_ports": [8000]},
        {"kubernetes": api.KubernetesOptions()},
    ],
)
def test_systemd_rejects_foreign_controls_before_declaration_receive(monkeypatch, options):
    from chimeraforge import serving_export

    def forbidden(*args, **kwargs):
        raise AssertionError("source must not be read for incompatible options")

    monkeypatch.setattr(serving_export, "receive", forbidden)
    with pytest.raises(api.ServingDeclarationError):
        api.export_serving_declaration(
            "PRIVATE-missing.json",
            format="systemd",
            executable="/usr/bin/true",
            gpu_devices=list("0123"),
            **options,
        )


@pytest.mark.parametrize(
    "devices",
    [
        None,
        [],
        list("012"),
        list("01234"),
        list("0012"),
        ["0", "1", "2", "GPU-16a23983-e73e-0945-2095-cdeb50696982"],
    ],
)
def test_single_unit_requires_exact_uniform_explicit_device_namespace(devices):
    with pytest.raises(api.ServingDeclarationError):
        api.export_serving_declaration(
            declaration(), format="systemd", executable="/usr/bin/true", gpu_devices=devices
        )


@pytest.mark.parametrize("format", ["launch", "compose", "kubernetes"])
def test_existing_formats_refuse_executable_override(format):
    with pytest.raises(api.ServingDeclarationError):
        api.export_serving_declaration(declaration(), format=format, executable="/usr/bin/true")


def test_multiple_original_replicas_never_collapse_into_one_unit():
    with pytest.raises(api.ServingDeclarationError):
        api.export_serving_declaration(
            declaration(replicas=2),
            format="systemd",
            executable="/usr/bin/true",
            gpu_devices=list("0123"),
        )


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_all_native_serving_controls_and_literal_executable_escaping(backend):
    held = declaration(backend, dtype="BF16")
    executable = '/not/installed $HOME%u"engine'
    text = api.export_serving_declaration(
        held, format="systemd", executable=executable, gpu_devices=list("0123")
    ).content
    assert 'ExecStart="/not/installed $$HOME%%u\\"engine"' in text
    assert '"--dtype" "bfloat16"' in text
    pairs = (
        [
            ("--tensor-parallel-size", "2"),
            ("--pipeline-parallel-size", "2"),
            ("--max-model-len", "8192"),
            ("--max-num-seqs", "8"),
            ("--max-num-batched-tokens", "512"),
        ]
        if backend == "vllm"
        else [
            ("--tp-size", "2"),
            ("--pp-size", "2"),
            ("--context-length", "8192"),
            ("--max-running-requests", "8"),
            ("--chunked-prefill-size", "-1"),
        ]
    )
    for flag, value in pairs:
        assert f'"{flag}" "{value}"' in text
    kv = "fp8" if backend == "vllm" else "fp8_e5m2"
    assert f'"--kv-cache-dtype" "{kv}"' in text
    assert ('"--enable-prefix-caching"' in text) == (backend == "vllm")
    assert '"--disable-radix-cache"' not in text


def test_unit_export_never_uses_plan_lookup_or_executes_or_probes_engine(tmp_path, monkeypatch):
    held = declaration()
    executable = "/PRIVATE-uninstalled/engine"

    def forbidden(*args, **kwargs):
        raise AssertionError("plan/engine operation forbidden")

    for name in ("plan", "load_plan", "artifact_from_dict"):
        monkeypatch.setattr(api, name, forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    native_stat = Path.stat

    def stat(path, *args, **kwargs):
        if path.as_posix() == executable:
            forbidden()
        return native_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    unit = tmp_path / "unit.service"
    unit.write_bytes(
        api.export_serving_declaration(
            held, format="systemd", executable=executable, gpu_devices=list("0123")
        ).content.encode()
    )
    assert (
        api.verify_serving_declaration(
            held, unit, format="systemd", executable=executable, gpu_devices=list("0123")
        ).exit_code
        == 0
    )


def test_verifier_uses_independent_executable_device_order_and_declaration(tmp_path):
    held = declaration()
    path = tmp_path / "unit.service"
    path.write_bytes(
        api.export_serving_declaration(
            held, format="systemd", executable="/usr/bin/true", gpu_devices=list("0123")
        ).content.encode()
    )
    original = path.read_bytes()
    for source, executable, devices in (
        (held, "/another/engine", list("0123")),
        (held, "/usr/bin/true", list("0132")),
        (declaration(revision="b" * 40), "/usr/bin/true", list("0123")),
    ):
        report = api.verify_serving_declaration(
            source, path, format="systemd", executable=executable, gpu_devices=devices
        )
        assert report.exit_code == 5 and report.to_dict()["changes"] == (
            {"path": "/unit", "category": "content", "count": 1},
        )
    assert path.read_bytes() == original


@pytest.mark.parametrize("raw", [b"", b"[Service]\0\n", b"\xff"])
def test_invalid_unit_content_is_not_reinterpreted(tmp_path, raw):
    path = tmp_path / "PRIVATE.service"
    path.write_bytes(raw)
    with pytest.raises(api.ServingDeclarationError) as error:
        api.verify_serving_declaration(
            declaration(),
            path,
            format="systemd",
            executable="/usr/bin/true",
            gpu_devices=list("0123"),
        )
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("hardlink", [False, True])
def test_alias_and_exclusive_export_keep_declaration_bytes(tmp_path, hardlink):
    held = declaration()
    source = tmp_path / "original.json"
    held.save(source)
    target = tmp_path / "alias.service" if hardlink else source
    if hardlink:
        os.link(source, target)
    original = source.read_bytes()
    args = [
        "serving",
        "export",
        "--declaration",
        str(source),
        "--format",
        "systemd",
        "--executable",
        "/usr/bin/true",
        "--out",
        str(target),
        "--json",
    ]
    for device in "0123":
        args += ["--gpu-device", device]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1 and json.loads(result.stdout)["exit_code"] == 1
    assert source.read_bytes() == original
    if not hardlink:
        other = tmp_path / "existing.service"
        other.write_bytes(b"existing")
        args[args.index("--out") + 1] = str(other)
        assert CliRunner().invoke(app, args).exit_code == 1
        assert other.read_bytes() == b"existing"
