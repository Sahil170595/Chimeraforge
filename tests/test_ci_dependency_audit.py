"""Exercise the existing audit command's inventory, without advisory network calls."""

import importlib.util
import subprocess
import sys

import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest


def _fixture(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "scripts/ci_dependency_audit.py"
    assert source.is_file(), "whole-lock audit helper is absent"
    spec = importlib.util.spec_from_file_location("dependency_audit_fixture", source)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname="chimeraforge"\nversion="0.82.0"\n')
    lock = root / "uv.lock"
    lock.write_text(
        "version=1\nrevision=5\n"
        '[[package]]\nname="chimeraforge"\nversion="0.82.0"\nsource={editable="."}\n'
        '[[package]]\nname="filelock"\nversion="3.20.3"\nsource={registry="https://pypi.org/simple"}\n'
        '[[package]]\nname="filelock"\nversion="4.2.1"\nsource={registry="https://pypi.org/simple"}\n'
        '[[package]]\nname="retained-package"\nversion="1.0"\nsource={registry="https://pypi.org/simple"}\n'
    )
    helper.__file__ = str(root / "scripts/ci_dependency_audit.py")
    monkeypatch.setattr(
        helper.importlib.metadata,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": name}, version=version)
            for name, version in (
                ("chimeraforge", "0.82.0"),
                ("filelock", "4.2.1"),
                ("retained-package", "1.0"),
            )
        ],
    )
    batches = []
    helper.observed_calls = []

    def audit(argv, **kwargs):
        helper.observed_calls.append((argv, kwargs))
        batches.append(Path(argv[-1]).read_text().splitlines())
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(helper.subprocess, "run", audit)
    return helper, lock, batches


def test_every_universal_version_is_audited_alongside_installed(tmp_path, monkeypatch):
    helper, _, batches = _fixture(tmp_path, monkeypatch)
    helper.main()
    pairs = {pin for batch in batches for pin in batch}
    assert "filelock==4.2.1" in pairs and "retained-package==1.0" in pairs
    assert "filelock==3.20.3" in pairs
    assert len(batches) == 2
    assert all(len({pin.split("==")[0] for pin in batch}) == len(batch) for batch in batches)


@pytest.mark.parametrize("failed_layer", [1, 2])
@pytest.mark.parametrize("status", [1, 2])
def test_every_layer_attempted_and_any_native_failure_is_fatal(
    tmp_path, monkeypatch, failed_layer, status
):
    helper, _, batches = _fixture(tmp_path, monkeypatch)
    original = helper.subprocess.run

    def fail(argv, **kwargs):
        original(argv, **kwargs)
        return subprocess.CompletedProcess(argv, status if len(batches) == failed_layer else 0)

    monkeypatch.setattr(helper.subprocess, "run", fail)
    with pytest.raises(SystemExit, match="1"):
        helper.main()
    assert len(batches) == 2
    for argv, kwargs in helper.observed_calls:
        assert all(flag in argv for flag in ("--strict", "--disable-pip", "--no-deps"))
        assert "--dry-run" not in argv and kwargs["check"] is False


def test_launch_failure_still_attempts_remaining_layer(tmp_path, monkeypatch):
    helper, _, batches = _fixture(tmp_path, monkeypatch)
    original = helper.subprocess.run

    def fail(argv, **kwargs):
        result = original(argv, **kwargs)
        if len(batches) == 1:
            raise OSError("fictional launch failure")
        return result

    monkeypatch.setattr(helper.subprocess, "run", fail)
    with pytest.raises(SystemExit, match="1"):
        helper.main()
    assert len(batches) == 2


def test_installed_only_pairs_dedup_roles_and_preserve_versions(tmp_path, monkeypatch):
    helper, _, batches = _fixture(tmp_path, monkeypatch)
    original = list(helper.importlib.metadata.distributions())
    monkeypatch.setattr(
        helper.importlib.metadata,
        "distributions",
        lambda: original + [SimpleNamespace(metadata={"Name": "other-package"}, version="1.0+cpu")],
    )
    inventory = helper._inventory()
    assert inventory[("filelock", "4.2.1")] == {"installed", "lock"}
    assert ("chimeraforge", "0.82.0") not in inventory
    helper.main()
    assert sum(pin == "filelock==4.2.1" for batch in batches for pin in batch) == 1
    assert "other-package==1.0+cpu" in {pin for batch in batches for pin in batch}


def test_partition_has_minimum_layers_and_no_version_lost(tmp_path, monkeypatch):
    helper, lock, batches = _fixture(tmp_path, monkeypatch)
    with lock.open("a") as stream:
        stream.write(
            '[[package]]\nname="filelock"\nversion="4.2.2"\nsource={registry="https://pypi.org/simple"}\n'
        )
    helper.main()
    assert len(batches) == 3
    assert {pin for batch in batches for pin in batch if pin.startswith("filelock==")} == {
        "filelock==3.20.3",
        "filelock==4.2.1",
        "filelock==4.2.2",
    }


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("version=1", "version=2"),
        ("version=1", "version=true"),
        ("revision=5", "revision=6"),
        ('version="3.20.3"', 'version="not-a-version"'),
        ('version="3.20.3"', ""),
        (
            'source={registry="https://pypi.org/simple"}',
            'source={git="https://example.invalid/repo"}',
        ),
        (
            'source={registry="https://pypi.org/simple"}',
            'source={registry="https://example.invalid/simple"}',
        ),
        ('name="chimeraforge"', 'name="unexpected-root"'),
    ],
)
def test_unknown_schema_source_or_version_refuses_before_audit(tmp_path, monkeypatch, old, new):
    helper, lock, batches = _fixture(tmp_path, monkeypatch)
    lock.write_text(lock.read_text().replace(old, new, 1))
    with pytest.raises((ValueError, TypeError, KeyError)):
        helper.main()
    assert not batches


def test_missing_lock_cannot_be_a_clean_installed_only_audit(tmp_path, monkeypatch):
    helper, lock, batches = _fixture(tmp_path, monkeypatch)
    lock.unlink()
    with pytest.raises(FileNotFoundError):
        helper.main()
    assert not batches


def test_native_auditor_collection_rejects_conflict_but_accepts_layers(tmp_path):
    assert importlib.util.find_spec("pip_audit") is not None
    for index, pins in enumerate(
        ("filelock==3.20.3\nfilelock==4.2.1\n", "filelock==3.20.3\n", "filelock==4.2.1\n")
    ):
        path = tmp_path / f"layer-{index}.txt"
        path.write_text(pins)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--dry-run",
                "--strict",
                "--no-deps",
                "--disable-pip",
                "--progress-spinner",
                "off",
                "-r",
                str(path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        assert (result.returncode != 0) if index == 0 else (result.returncode == 0), result.stdout


def test_supported_python_domain_uses_patched_filelock():
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet

    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert "3.10" not in SpecifierSet(project["project"]["requires-python"])
    assert "3.11" in SpecifierSet(project["project"]["requires-python"])
    for group in ("eval", "dev"):
        requirements = [
            Requirement(value) for value in project["project"]["optional-dependencies"][group]
        ]
        pins = [value for value in requirements if value.name == "filelock"]
        assert len(pins) == 1 and pins[0].marker is None
        assert "4.2.0" not in pins[0].specifier and "4.2.1" in pins[0].specifier
        assert "5.0.0" not in pins[0].specifier
    assert project["tool"]["mypy"]["python_version"] == "3.11"
    assert project["tool"]["ruff"]["target-version"] == "py311"


def test_marker_evaluated_old_profile_drops_dormant_lock_version():
    from packaging.requirements import Requirement

    old = [
        Requirement("filelock==3.20.3; python_version < '3.11'"),
        Requirement("filelock==4.2.1; python_version >= '3.11'"),
    ]
    selected = [value for value in old if value.marker.evaluate({"python_version": "3.12"})]
    assert len(selected) == 1 and str(selected[0].specifier) == "==4.2.1"
    assert len({str(value.specifier) for value in old}) == 2


def test_hosted_matrix_keeps_supported_interpreters_and_portability():
    import yaml

    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-latest"]
    assert matrix["python-version"] == ["3.11", "3.12", "3.13", "3.14"]
    assert matrix["include"] == [
        {"os": "windows-latest", "python-version": "3.11"},
        {"os": "windows-latest", "python-version": "3.14"},
        {"os": "macos-latest", "python-version": "3.14"},
    ]
    commands = [step["run"] for step in workflow["jobs"]["dependencies"]["steps"] if "run" in step]
    assert commands == ["uv run --no-sync python scripts/ci_dependency_audit.py"]
