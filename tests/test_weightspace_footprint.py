"""Independently enumerated serving footprint ledgers."""

import hashlib
import json

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from chimeraforge.weightspace import ManifestError, estimate_footprint


def inventory(root, files, tensors, metadata=None):
    records = []
    for path, role, phases, data in files:
        (root / path).write_bytes(data)
        records.append(
            {
                "path": path,
                "role": role,
                "phases": phases,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    path = root / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema": "weightspace-manifest/v1",
                "codec": {"id": "dense-v1", "exact": True, "parameters": {}},
                "identities": {"target": "a" * 64},
                "files": records,
                "tensors": tensors,
                "metadata": metadata or {},
            }
        )
    )
    return path


def tensor(name, shape):
    return {"name": name, "shape": shape, "dtype": "F32", "sha256": "a" * 64}


def test_materialization_vs_standalone_and_aliases(tmp_path):
    raw = [tensor("a", [2, 3]), tensor("b", [2, 3])]
    path = inventory(
        tmp_path,
        [
            ("base", "base", ["decode"], b"12345"),
            ("archive", "payload", ["decode"], b"abc"),
            ("mirror", "base", ["decode"], b"12345"),
            ("donor", "donor", ["build"], b"training"),
        ],
        raw,
        {"tensor_aliases": {"b": "a"}},
    )
    f = estimate_footprint(path).to_dict()
    assert f["cold_transfer_bytes"] == 8
    assert f["unique_on_disk_bytes"] == 16
    assert f["materialized_weight_bytes"] == 24
    assert f["staging_bytes"] == 32
    assert f["additional_transfer_bytes"] == 8
    assert f["runtime_workspace_bytes"] is None
    cache = hashlib.sha256(b"12345").hexdigest()
    assert estimate_footprint(path, cached_sha256=[cache]).additional_transfer_bytes == 3
    path = inventory(tmp_path, [("weights", "recipient", ["load", "inference"], b"abc")], raw)
    assert estimate_footprint(path).staging_bytes == 3
    assert estimate_footprint(path).materialized_weight_bytes == 48


def test_inference_decoder_unknown_and_explicit_bound(tmp_path):
    files = [("rec", "recipient", ["inference"], b"abc"), ("dec", "decoder", ["inference"], b"aux")]
    path = inventory(tmp_path, files, [tensor("a", [])])
    result = estimate_footprint(path)
    assert result.auxiliary_resident_bytes is None
    assert result.unknown_auxiliaries == ("dec",)
    path = inventory(tmp_path, files, [tensor("a", [])], {"resident_bytes": {"dec": 12}})
    assert estimate_footprint(path).auxiliary_resident_bytes == 12
    run = CliRunner().invoke(app, ["weightspace", "footprint", str(path)])
    assert run.exit_code == 0 and json.loads(run.output)["auxiliary_resident_bytes"] == 12


@pytest.mark.parametrize("aliases", [{"a": "a"}, {"a": "missing"}, {"a": "b", "b": "a"}])
def test_unsupported_alias_graph(tmp_path, aliases):
    path = inventory(
        tmp_path,
        [("rec", "recipient", ["inference"], b"123")],
        [tensor("a", [2]), tensor("b", [2])],
        {"tensor_aliases": aliases},
    )
    with pytest.raises(ManifestError):
        estimate_footprint(path)
