"""Generate the public F32 linear-recipient example in an operator-supplied directory."""

import json
from pathlib import Path
import struct
import sys

from build_example import safetensors, sha


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def build(root):
    root.mkdir(parents=True, exist_ok=True)
    bias = struct.pack("<2f", 0.5, -0.5)
    weight = struct.pack("<4f", 1.0, 0.0, 2.0, -1.0)
    tensors = [
        {"name": "bias", "dtype": "F32", "shape": [2], "sha256": sha(bias)},
        {"name": "weight", "dtype": "F32", "shape": [2, 2], "sha256": sha(weight)},
    ]
    target = sha(json_bytes(tensors))
    transform = json_bytes(
        {"schema": "word-count-v1", "lowercase": True, "vocabulary": ["alpha", "beta"]}
    )
    labels = json_bytes({"schema": "ordered-labels-v1", "labels": ["first", "second"]})
    files = []
    for name, role, data in [
        (
            "weights.safetensors",
            "recipient",
            safetensors([("bias", "F32", [2], bias), ("weight", "F32", [2, 2], weight)]),
        ),
        ("transform.json", "transform", transform),
        ("labels.json", "labels", labels),
    ]:
        (root / name).write_bytes(data)
        files.append(
            dict(
                path=name,
                role=role,
                phases=["load", "inference"],
                size_bytes=len(data),
                sha256=sha(data),
            )
        )
    manifest = {
        "schema": "weightspace-manifest/v1",
        "codec": {"id": "linear-recipient-v1", "exact": True, "parameters": {}},
        "identities": {
            "target": target,
            "recipient": target,
            "classes": sha(labels),
            "transform": sha(transform),
        },
        "tensors": tensors,
        "files": files,
    }
    (root / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
