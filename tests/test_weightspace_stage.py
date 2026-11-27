import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from chimeraforge.weightspace import ManifestError, current_bundle, stage_bundle, verify_bundle
from chimeraforge.weightspace import staging


def source(root, suffix=b""):
    root.mkdir(exist_ok=True)
    files = []
    for name, role, phases in [
        ("weights", "recipient", ["load", "inference"]),
        ("config", "config", ["load"]),
        ("donor", "donor", ["build"]),
    ]:
        data = name.encode() + suffix
        (root / name).write_bytes(data)
        files.append(
            dict(
                path=name,
                role=role,
                phases=phases,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    path = root / "bundle.json"
    path.write_text(
        json.dumps(
            dict(
                schema="weightspace-manifest/v1",
                codec=dict(id="dense-v1", exact=True, parameters={}),
                identities=dict(target="1" * 64),
                files=files,
                tensors=[],
            )
        )
    )
    return path


def test_stage_only_runtime_closure_and_repeat(tmp_path):
    src = source(tmp_path / "in")
    out = tmp_path / "deploy"
    decision = stage_bundle(src, out)
    staged = current_bundle(out)
    assert staged.parent == Path(decision.directory)
    assert {p.name for p in staged.parent.iterdir()} == {"weights", "config", "manifest.json"}
    assert [f.role for f in verify_bundle(staged).files] == ["recipient", "config"]
    assert stage_bundle(src, out).manifest_sha256 == decision.manifest_sha256
    assert len(list((out / "generations").iterdir())) == 1


def test_last_copy_failure_preserves_previous(tmp_path, monkeypatch):
    src = source(tmp_path / "in")
    out = tmp_path / "deploy"
    first = stage_bundle(src, out)
    pointer = (out / "current.json").read_bytes()
    source(src.parent, b"changed")
    original = staging._copy_verified

    def interrupt(source, target, item):
        if item.role == "config":
            raise OSError("simulated last copy failure")
        original(source, target, item)

    monkeypatch.setattr(staging, "_copy_verified", interrupt)
    with pytest.raises(ManifestError):
        stage_bundle(src, out)
    assert (out / "current.json").read_bytes() == pointer
    assert verify_bundle(current_bundle(out)).manifest_sha256 == first.manifest_sha256


def test_stage_concurrent_writers(tmp_path):
    a = source(tmp_path / "a")
    b = source(tmp_path / "b", b"b")
    out = tmp_path / "deploy"
    with ThreadPoolExecutor(3) as pool:
        produced = list(pool.map(lambda p: stage_bundle(p, out), [a, a, b]))
    assert verify_bundle(current_bundle(out)).manifest_sha256 in {
        r.manifest_sha256 for r in produced
    }
    assert len(list((out / "generations").iterdir())) == 2


def test_cannot_stage_a_decode_only_model_or_reuse_unrelated_directory(tmp_path):
    src = source(tmp_path / "in")
    out = tmp_path / "other"
    out.mkdir()
    (out / "keep").write_bytes(b"unchanged")
    with pytest.raises(ManifestError):
        stage_bundle(src, out)
    assert (out / "keep").read_bytes() == b"unchanged"
    m = json.loads(src.read_bytes())
    for member in m["files"]:
        member["phases"] = ["decode"]
    src.write_text(json.dumps(m))
    with pytest.raises(ManifestError, match="runtime"):
        stage_bundle(src, tmp_path / "new")


@pytest.mark.parametrize("extra", ["stale.txt", "unsigned", "empty/nested"])
def test_rejects_extra_entries_in_published_generation(tmp_path, extra):
    source_path = source(tmp_path / "source")
    store = tmp_path / "store"
    root = Path(stage_bundle(source_path, store).directory)
    member = root / extra
    if extra.endswith(".txt"):
        member.write_bytes(b"operator data")
    else:
        member.mkdir(parents=True)
    pointer = (store / "current.json").read_bytes()
    with pytest.raises(ManifestError, match="unexpected"):
        current_bundle(store)
    with pytest.raises(ManifestError, match="unexpected"):
        stage_bundle(source_path, store)
    assert member.exists() and (store / "current.json").read_bytes() == pointer


def test_metadata_companion_cannot_turn_a_delta_into_a_runnable_model(tmp_path):
    store = tmp_path / "store"
    src = source(tmp_path / "src")
    previous = stage_bundle(src, store)
    m = json.loads(src.read_bytes())
    m["codec"]["id"] = "xor-bytes-v1"
    for member in m["files"]:
        if member["role"] == "recipient":
            member.update(role="payload", phases=["decode"])
    src.write_text(json.dumps(m))
    with pytest.raises(ManifestError, match="weights"):
        stage_bundle(src, store)
    assert current_bundle(store).parent == Path(previous.directory)
