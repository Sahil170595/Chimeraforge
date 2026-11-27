import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from chimeraforge.weightspace import ManifestError, stage_bundle, verify_recipient

np = pytest.importorskip("numpy")
safetensors = pytest.importorskip("safetensors.numpy")


def write_json(path, value):
    path.write_bytes(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample(root):
    root.mkdir()
    weights = {
        "weight": np.array([[1.0, 0.0], [2.0, -1.0]], dtype="<f4"),
        "bias": np.array([0.5, -0.5], dtype="<f4"),
    }
    records = [
        dict(
            name=k, dtype="F32", shape=list(v.shape), sha256=hashlib.sha256(v.tobytes()).hexdigest()
        )
        for k, v in sorted(weights.items())
    ]
    model_id = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    safetensors.save_file(weights, root / "recipient.safetensors")
    transform = write_json(
        root / "transform.json",
        dict(schema="word-count-v1", vocabulary=["alpha", "beta"], lowercase=True),
    )
    labels = write_json(
        root / "labels.json", dict(schema="ordered-labels-v1", labels=["first", "second"])
    )
    (root / "donor").write_bytes(b"training only")
    files = []
    for name, role in [
        ("recipient.safetensors", "recipient"),
        ("labels.json", "labels"),
        ("transform.json", "transform"),
        ("donor", "donor"),
    ]:
        data = (root / name).read_bytes()
        files.append(
            dict(
                path=name,
                role=role,
                phases=["build"] if role == "donor" else ["load", "inference"],
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
            )
        )
    path = root / "manifest.json"
    write_json(
        path,
        dict(
            schema="weightspace-manifest/v1",
            codec=dict(id="linear-recipient-v1", exact=True, parameters={}),
            identities=dict(
                target=model_id, recipient=model_id, classes=labels, transform=transform
            ),
            files=files,
            tensors=records,
        ),
    )
    return path


def test_donor_free_process_runs_real_text(tmp_path):
    src = sample(tmp_path / "source")
    receipt = stage_bundle(src, tmp_path / "stage")
    (src.parent / "donor").unlink()
    path = Path(receipt.directory) / "manifest.json"
    result = verify_recipient(path, "Alpha beta ALPHA alpha")
    assert result.logits == (3.5, 4.5)
    assert result.label == "second" and result.class_index == 1
    assert result.worker_rss_bytes > 0
    assert result.artifact_bytes == sum((path.parent / i).stat().st_size for i in receipt.files)
    run = CliRunner().invoke(
        app, ["weightspace", "verify-recipient", str(path), "--text", "unseen"]
    )
    assert run.exit_code == 0, run.output
    assert json.loads(run.output)["logits"] == [0.5, -0.5]


@pytest.mark.parametrize(
    "change", ["labels", "transform", "identity", "weights", "logical", "foreign", "extra"]
)
def test_refuses_mismatched_recipient(tmp_path, change):
    path = sample(tmp_path / "source")
    m = json.loads(path.read_bytes())
    if change == "labels":
        f = next(f for f in m["files"] if f["role"] == "labels")
        f["sha256"] = write_json(
            path.parent / f["path"], {"schema": "ordered-labels-v1", "labels": ["second", "first"]}
        )
    elif change == "transform":
        (path.parent / "transform.json").unlink()
    elif change == "identity":
        m["identities"]["target"] = "0" * 64
    elif change == "weights":
        m["identities"]["recipient"] = "0" * 64
    elif change == "logical":
        m["tensors"][0]["sha256"] = "1" * 64
    elif change == "foreign":
        m["codec"]["id"] = "other-v1"
    else:
        m["files"][-1]["phases"] = ["inference"]
    write_json(path, m)
    with pytest.raises(ManifestError):
        verify_recipient(path, "alpha")
