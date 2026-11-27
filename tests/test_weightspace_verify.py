"""Offline verification through the public library and CLI."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from chimeraforge.weightspace import ManifestError, verify_bundle

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "weightspace"


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "bundle"
    subprocess.run([sys.executable, "-I", str(EXAMPLE / "build_example.py"), str(root)], check=True)
    assert json.loads((root / "manifest.json").read_bytes()) == json.loads(
        (EXAMPLE / "manifest.json").read_bytes()
    )
    return root


def test_public_verify_and_cli(bundle):
    path = bundle / "manifest.json"
    result = verify_bundle(path, bundle).to_dict()
    assert result["status"] == "verified"
    assert result["manifest_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(result["files"]) == 2
    delta = next(f for f in result["files"] if f["role"] == "payload")
    assert delta["size_bytes"] == 88
    assert delta["sha256"] == "174c39321b58d063defa58d3ce2a3b4f1c0af2fdfc209bffc63c6d62663ac250"
    run = CliRunner().invoke(app, ["weightspace", "verify", str(path)])
    assert run.exit_code == 0, run.output
    assert json.loads(run.output) == result


@pytest.mark.parametrize("damage", ["bytes", "size", "missing", "schema", "escape", "case", "bool"])
def test_invalid_bundle_is_rejected(bundle, damage):
    path = bundle / "manifest.json"
    m = json.loads(path.read_text())
    f = m["files"][0]
    payload = bundle / f["path"]
    if damage == "bytes":
        payload.write_bytes(b"x" * f["size_bytes"])
    elif damage == "size":
        f["size_bytes"] += 1
    elif damage == "missing":
        payload.unlink()
    elif damage == "schema":
        m["schema"] = "weightspace-manifest/v2"
    elif damage == "escape":
        f["path"] = "../outside.bin"
    elif damage == "case":
        m["files"].append({**f, "path": f["path"].upper()})
    else:
        f["size_bytes"] = True
    path.write_text(json.dumps(m))
    with pytest.raises(ManifestError):
        verify_bundle(path, bundle)
    assert CliRunner().invoke(app, ["weightspace", "verify", str(path)]).exit_code == 1


def test_duplicate_json_keys(bundle):
    path = bundle / "manifest.json"
    path.write_text('{"schema":"old",' + path.read_text().lstrip()[1:])
    with pytest.raises(ManifestError, match="duplicate"):
        verify_bundle(path)


@pytest.mark.parametrize("value", ["1e400", "9" * 6000])
def test_nonportable_json_number_is_a_public_error(bundle, value):
    path = bundle / "manifest.json"
    path.write_text('{"extra":' + value + "," + path.read_text().lstrip()[1:])
    with pytest.raises(ManifestError):
        verify_bundle(path)
    result = CliRunner().invoke(app, ["weightspace", "verify", str(path)])
    assert result.exit_code == 1
    assert json.loads(result.output)["status"] == "invalid"


def test_independent_manifest_pin(bundle):
    path = bundle / "manifest.json"
    pin = hashlib.sha256(path.read_bytes()).hexdigest()
    assert verify_bundle(path, expected_sha256=pin).manifest_sha256 == pin
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ManifestError, match="manifest SHA-256"):
        verify_bundle(path, expected_sha256=pin)
