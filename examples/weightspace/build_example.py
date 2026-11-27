"""Build the two-file exact XOR example using only Python's standard library."""

import hashlib
import json
import struct
import sys
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safetensors(items):
    header, blob = {}, bytearray()
    for name, dtype, shape, value in items:
        start = len(blob)
        blob.extend(value)
        header[name] = {"dtype": dtype, "shape": shape, "data_offsets": [start, len(blob)]}
    raw = json.dumps(header, separators=(",", ":")).encode()
    raw += b" " * (-len(raw) % 8)
    return struct.pack("<Q", len(raw)) + raw + blob


def build(root):
    base = struct.pack("<4f", 2**27, -0.0, 2, -1)
    target = struct.pack("<4f", 1, 0, 2, -1)
    bias = struct.pack("<2f", 0.5, -0.5)
    xor = bytes(a ^ b for a, b in zip(base, target))
    tensors = [
        {"name": "bias", "dtype": "F32", "shape": [2], "sha256": sha(bias)},
        {"name": "weight", "dtype": "F32", "shape": [2, 2], "sha256": sha(target)},
    ]
    base_file = safetensors([("bias", "F32", [2], bias), ("weight", "F32", [2, 2], base)])
    delta = safetensors([("weight", "U8", [16], xor)])
    files = []
    for name, data, role in [
        ("base.safetensors", base_file, "base"),
        ("delta.safetensors", delta, "payload"),
    ]:
        (root / name).write_bytes(data)
        files.append(
            dict(path=name, role=role, phases=["decode"], size_bytes=len(data), sha256=sha(data))
        )

    # The model commitment is SHA-256 of canonical sorted JSON tensor records.
    def identity(records):
        return sha(
            json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        )

    manifest = {
        "schema": "weightspace-manifest/v1",
        "codec": {"id": "xor-bytes-v1", "exact": True, "parameters": {}},
        "identities": {
            "base": identity([tensors[0], {**tensors[1], "sha256": sha(base)}]),
            "target": identity(tensors),
        },
        "files": files,
        "tensors": tensors,
        "metadata": {"unchanged": ["bias"]},
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    destination = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).parent
    destination.mkdir(parents=True, exist_ok=True)
    build(destination)
