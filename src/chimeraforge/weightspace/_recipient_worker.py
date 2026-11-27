"""Isolated, data-only linear classifier worker. Expects verified local paths over stdin."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def predict(request: dict) -> dict:
    import numpy as np
    import psutil
    from safetensors.numpy import load_file

    transform, labels = request["transform"], request["labels"]
    counts = dict.fromkeys(transform["vocabulary"], 0)
    text = request["text"].lower() if transform["lowercase"] else request["text"]
    for word in text.split():
        if word in counts:
            counts[word] += 1
    weights = load_file(Path(request["weights"]))
    if set(weights) != {"weight", "bias"}:
        raise ValueError("recipient requires exactly weight and bias")
    matrix, bias = weights["weight"], weights["bias"]
    if matrix.shape != (len(labels), len(counts)) or bias.shape != (len(labels),):
        raise ValueError("recipient shapes do not match transform and ordered labels")
    actual = []
    for name, array in sorted(weights.items()):
        if array.dtype != np.dtype("<f4") or not np.isfinite(array).all():
            raise ValueError("linear recipient requires finite F32 tensors")
        actual.append(
            {
                "name": name,
                "dtype": "F32",
                "shape": list(array.shape),
                "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
            }
        )
    if actual != request["tensors"]:
        raise ValueError("logical weights differ from recipient tensor declarations")
    logits = matrix @ np.array(list(counts.values()), dtype=np.float32) + bias
    if not np.isfinite(logits).all():
        raise ValueError("non-finite recipient logits")
    idx = int(np.argmax(logits))
    return {
        "label": labels[idx],
        "class_index": idx,
        "logits": logits.tolist(),
        "worker_rss_bytes": psutil.Process().memory_info().rss,
    }


if __name__ == "__main__":
    try:
        result = predict(json.loads(sys.stdin.buffer.read()))
    except ImportError:
        print(json.dumps({"error": "install chimeraforge[weightspace] for recipient inference"}))
        sys.exit(1)
    except Exception as exc:
        # Keep a structured public error even for a native SafeTensors format failure.
        print(json.dumps({"error": f"recipient execution failed: {exc}"}))
        sys.exit(1)
    print(json.dumps(result))
