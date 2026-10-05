"""Parse generated configs with real host tools; never start an inference engine."""

import json
import os
import shutil
import subprocess
import sys

import pytest

from test_deploy import artifact, export
from chimeraforge.planner.resolver import SOURCE_OLLAMA

TOOL_TIMEOUT_S = 30


def _missing_tool(message):
    if os.environ.get("CHIMERAFORGE_DEPLOY_ACCEPTANCE") == "1":
        pytest.fail(message)
    pytest.skip(message)


def _run(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=TOOL_TIMEOUT_S)


@pytest.mark.parametrize("backend", ["vllm", "sglang", "tgi", "ollama"])
def test_docker_compose_config_accepts_export(tmp_path, backend):
    docker = shutil.which("docker")
    if docker is None:
        _missing_tool("Docker CLI unavailable; Linux hosted CI validates Compose exports")
    version = _run([docker, "compose", "version"])
    if version.returncode:
        _missing_tool("Docker Compose unavailable: " + version.stderr)
    if backend == "ollama":
        saved = artifact(
            backend=backend,
            model="ollama:qwen2.5:7b-instruct-q4_K_M",
            source=SOURCE_OLLAMA,
            quant="Q4_K_M",
            native_quant="Q4_K_M",
        )
    else:
        saved = artifact(backend=backend, model="org/model${UNSET};$(id)%u")
    result = export(saved, format="compose", image="example/engine:1.2.3")
    path = tmp_path / "compose.json"
    path.write_text(result.content, encoding="utf-8")
    for name, content in result.files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    parsed = _run([docker, "compose", "--file", str(path), "config", "--format", "json"])
    assert parsed.returncode == 0, parsed.stderr
    data = json.loads(parsed.stdout)
    service = data["services"]["inference"]
    assert service["image"] == "example/engine:1.2.3"
    assert service["deploy"]["resources"]["reservations"]["devices"][0]["count"] == 1
    assert "UNSET" not in parsed.stderr
    if backend != "ollama":
        assert any("${UNSET}" in arg and "$(id)%u" in arg for arg in service["command"])


def test_systemd_analyze_accepts_escaped_argv(tmp_path):
    analyze = shutil.which("systemd-analyze")
    if analyze is None:
        _missing_tool("systemd-analyze unavailable; Linux hosted CI validates native units")
    result = export(
        artifact(model='org/model${UNSET}%u;"\\quoted'),
        format="systemd",
        executable="/usr/bin/true",
    )
    path = tmp_path / "chimeraforge-acceptance.service"
    path.write_text(result.content, encoding="utf-8")
    checked = _run([analyze, "verify", "--man=no", "--generators=no", str(path)])
    assert checked.returncode == 0, checked.stderr


def test_macos_plutil_accepts_launch_agent(tmp_path):
    plutil = shutil.which("plutil")
    if sys.platform != "darwin" or plutil is None:
        pytest.skip("plutil validation runs on macOS hosted CI")
    saved = artifact(
        backend="ollama",
        model="ollama:qwen2.5:7b-instruct-q4_K_M",
        source=SOURCE_OLLAMA,
        quant="Q4_K_M",
        native_quant="Q4_K_M",
        platform="macos",
    )
    result = export(saved, format="launchd", executable="/usr/bin/true")
    path = tmp_path / "org.chimeraforge.inference.plist"
    path.write_text(result.content, encoding="utf-8")
    checked = _run([plutil, "-lint", str(path)])
    assert checked.returncode == 0, checked.stderr
