"""Held signed envelopes and receiver trust inputs with separate bounded budgets."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
from typing import Any, cast

from chimeraforge.bench.gate import MAX_REPLICATES, RegressionPolicy, policy_from
from chimeraforge.bench.gate_inputs import MAX_POLICY_BYTES
from chimeraforge.plan_bundle import _read
from chimeraforge import signed_contribution as signed
from chimeraforge.signed_payload import (
    MAX_ENVELOPE_BYTES,
    MAX_KEY_BYTES,
    MAX_PAYLOAD_BYTES,
    MAX_TRUSTED_KEYS,
    fail,
    held_json,
    public_text,
)

MAX_TOTAL_ENVELOPE_BYTES = 32 * 1024 * 1024


def _path(source: object) -> Path | None:
    return Path(os.path.abspath(source)) if isinstance(source, (str, Path)) else None


def _paths(paths: object) -> bool:
    return type(paths) is tuple and all(
        isinstance(path, Path) and path.is_absolute() for path in paths
    )


@dataclass(frozen=True)
class HeldGate:
    policy: RegressionPolicy
    arms: dict[str, list[dict[str, Any]]]
    keys: tuple[bytes, ...]
    paths: tuple[Path, ...]
    budgets: dict


def hold(
    baseline: list,
    candidate: list,
    *,
    trusted_keys: tuple[bytes | str | Path, ...],
    policy: RegressionPolicy | dict | str | Path,
) -> HeldGate:
    if any(
        type(arm) is not list or not 1 <= len(arm) <= MAX_REPLICATES
        for arm in (baseline, candidate)
    ):
        fail("signed gate requires 1-16 declared envelopes per arm")
    if type(trusted_keys) is not tuple or len(trusted_keys) > MAX_TRUSTED_KEYS:
        fail("signed gate requires an explicit tuple of at most16 receiver keys")
    data, policy_raw, paths = held_json(
        asdict(cast(RegressionPolicy, policy)) if type(policy) is RegressionPolicy else policy,
        MAX_POLICY_BYTES,
    )
    chosen, _ = policy_from(data)
    for controls in (chosen.fixed_controls, chosen.baseline_treatment, chosen.candidate_treatment):
        if any(type(value) is str and not public_text(value) for value in controls.values()):
            fail("signed gate policy requires public observed control expectations")
    protected = list(paths)
    cache: dict[Path, dict] = {}
    arms: dict[str, list[dict]] = {"baseline": [], "candidate": []}
    total = 0
    for name, sources in (("baseline", baseline), ("candidate", candidate)):
        for index, source in enumerate(sources):
            path = _path(source)
            if path is not None and path in cache:
                size = cache[path]["size_bytes"]
                if total + size > MAX_TOTAL_ENVELOPE_BYTES:
                    fail("signed gate envelope occurrence budget exceeded")
                total += size
                item = copy.deepcopy(cache[path])
            else:
                limit = min(MAX_ENVELOPE_BYTES, MAX_TOTAL_ENVELOPE_BYTES - total)
                if limit <= 0:
                    fail("signed gate envelope occurrence budget exceeded")
                envelope, raw, envelope_paths = signed.load(source, limit=limit)
                if not _paths(envelope_paths):
                    fail()
                signed._decode(envelope)
                item = {
                    "envelope": envelope,
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "paths": envelope_paths,
                }
                total += len(raw)
                if path is not None:
                    cache[path] = item
            protected.extend(item["paths"])
            arms[name].append({**item, "index": index})
    key_cache: dict[Path, bytes] = {}
    keys: list[bytes] = []
    key_charge = 0
    for source in trusted_keys:
        key_raw: object
        path = _path(source)
        if path is not None:
            if path not in key_cache:
                key_cache[path] = _read(path, MAX_KEY_BYTES)
            key_raw = key_cache[path]
            protected.append(path)
        else:
            key_raw = source
        if type(key_raw) is not bytes or not 0 < len(key_raw) <= MAX_KEY_BYTES:
            fail("signed gate requires bounded nonempty receiver key bytes")
        keys.append(key_raw)
        key_charge += len(key_raw)
    return HeldGate(
        chosen,
        arms,
        tuple(keys),
        tuple(dict.fromkeys(protected)),
        {
            "envelopes": {
                "per_envelope_limit_bytes": MAX_ENVELOPE_BYTES,
                "total_occurrence_limit_bytes": MAX_TOTAL_ENVELOPE_BYTES,
                "charged_bytes": total,
                "decoded_payload_limit_bytes": MAX_PAYLOAD_BYTES,
            },
            "policy": {"limit_bytes": MAX_POLICY_BYTES, "charged_bytes": len(policy_raw)},
            "keys": {
                "maximum_count": MAX_TRUSTED_KEYS,
                "per_key_limit_bytes": MAX_KEY_BYTES,
                "charged_bytes": key_charge,
            },
            "scope": "32 MiB envelope occurrences; separate policy and receiver-key budgets",
        },
    )
