"""Closed finite load cells and separately bounded held whole-campaign inputs."""

from __future__ import annotations

from collections.abc import Mapping
import copy
from dataclasses import dataclass, field
import hashlib
import math
import os
from pathlib import Path
from typing import NoReturn

from chimeraforge.bench.gate import FACTS
from chimeraforge.bench.gate_inputs import MAX_POLICY_BYTES, MAX_TOTAL_BYTES, finite, held_json
from chimeraforge.bench.trace_campaign import MAX_CAMPAIGN_REQUESTS, MAX_REPLICATES
from chimeraforge.bench.trace_campaign_inputs import MAX_CAMPAIGN_BYTES, load_campaign
from chimeraforge.bench.trace_gate import _known_fact
from chimeraforge.bench.trace_gate_inputs import TARGETS, validate_descriptor
from chimeraforge.bench.trace_workload import (
    MAX_CONCURRENCY,
    MAX_TIMEOUT_SECONDS,
    MAX_TRACE_REQUESTS,
)
from chimeraforge.planner.replay import digest

MAX_CASES_BYTES = 1024 * 1024
MAX_CELLS = 16
MAX_CELL_NAME_CHARS = 80
MAX_CAMPAIGN_TOTAL_BYTES = MAX_TOTAL_BYTES
SCHEDULE_ROUNDOFF_ULPS = 4
CASE_FIELDS = {
    "schema_version",
    "kind",
    "model",
    "backend",
    "concurrency",
    "expected_replicates",
    "request_timeout_seconds",
    "trace_timeout_seconds",
    "campaign_timeout_seconds",
    "ordered_descriptors",
    "cells",
}
POLICY_FIELDS = {"schema_version", "kind", "targets", "fixed_controls", "require_cache_evidence"}
DESCRIPTOR_FIELDS = {"request_id", "prompt_sha256", "prompt_bytes", "max_output_tokens"}
TIMEOUTS = ("request_timeout_seconds", "trace_timeout_seconds", "campaign_timeout_seconds")


def fail(message: str) -> NoReturn:
    from chimeraforge.api import PlanError

    raise PlanError("invalid trace envelope input: " + message)


def source_path(source: object) -> Path | None:
    return Path(os.path.abspath(source)) if isinstance(source, (str, Path)) else None


def _held(source: object, limit: int) -> tuple[dict, dict, Path | None]:
    from chimeraforge.api import PlanError

    try:
        data, raw, path = held_json(source, limit)
        return data, {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}, path
    except (PlanError, ValueError, TypeError, OverflowError, RecursionError):
        fail("malformed bounded declaration JSON")


def _closed(data: object, fields: set[str], kind: str) -> None:
    if (
        type(data) is not dict
        or set(data) != fields
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["kind"] != kind
    ):
        fail("unsupported closed declaration shape")


def cases_from(source: object) -> tuple[dict, dict, Path | None]:
    data, receipt, path = _held(source, MAX_CASES_BYTES)
    _closed(data, CASE_FIELDS, "chimeraforge.trace-envelope-cases")
    if any(
        type(data[name]) is not str or not data[name].strip() or len(data[name]) > 512
        for name in ("model", "backend")
    ):
        fail("serving identity is required")
    for name, maximum in (
        ("concurrency", MAX_CONCURRENCY),
        ("expected_replicates", MAX_REPLICATES),
    ):
        if type(data[name]) is not int or not 1 <= data[name] <= maximum:
            fail("invalid concurrency or replicate population")
    if any(
        not finite(data[name], minimum=0) or not 0 < data[name] <= MAX_TIMEOUT_SECONDS
        for name in TIMEOUTS
    ):
        fail("timeouts must be bounded finite positive seconds")
    rows = data["ordered_descriptors"]
    if (
        type(rows) is not list
        or not 2 <= len(rows) <= MAX_TRACE_REQUESTS
        or len(rows) * data["expected_replicates"] > MAX_CAMPAIGN_REQUESTS
    ):
        fail("invalid declared whole-campaign request population")
    if any(type(row) is not dict or set(row) != DESCRIPTOR_FIELDS for row in rows):
        fail("descriptors must exclude arrivals and contain only native commitments")
    cells = data["cells"]
    if type(cells) is not list or not 1 <= len(cells) <= MAX_CELLS:
        fail("declare 1-16 finite load cells")
    names, intervals = set(), set()
    for cell in cells:
        if type(cell) is not dict or set(cell) != {"name", "arrival_interval_seconds"}:
            fail("unsupported load cell fields")
        name, interval = cell["name"], cell["arrival_interval_seconds"]
        if (
            type(name) is not str
            or not name.strip()
            or len(name) > MAX_CELL_NAME_CHARS
            or name in names
        ):
            fail("load-cell names must be nonempty, unique and at most 80 characters")
        if not finite(interval, minimum=0) or interval <= 0 or interval in intervals:
            fail("load intervals must be unique finite positive seconds")
        try:
            last = float(len(rows) - 1) * float(interval)
            rate = 1.0 / float(interval)
        except (OverflowError, ZeroDivisionError):
            fail("load schedule or reciprocal rate is unrepresentable")
        if (
            not math.isfinite(last)
            or last >= data["trace_timeout_seconds"]
            or not math.isfinite(rate)
            or rate <= 0
        ):
            fail("schedule must finish before the trace deadline with a finite positive rate")
        seen: set[str] = set()
        for index, row in enumerate(rows):
            validate_descriptor({**row, "arrival_offset_s": float(index) * float(interval)}, seen)
        names.add(name)
        intervals.add(interval)
    return data, receipt, path


def policy_from(source: object) -> tuple[dict, dict, Path | None]:
    data, receipt, path = _held(source, MAX_POLICY_BYTES)
    _closed(data, POLICY_FIELDS, "chimeraforge.trace-envelope-policy")
    targets = data["targets"]
    if (
        type(targets) is not dict
        or set(targets) != set(TARGETS)
        or not any(value is not None for value in targets.values())
        or any(
            value is not None and (not finite(value, minimum=0) or value <= 0)
            for value in targets.values()
        )
    ):
        fail("declare exact supported targets with at least one active positive target")
    fixed = data["fixed_controls"]
    if (
        type(fixed) is not dict
        or not set(fixed) <= FACTS
        or type(data["require_cache_evidence"]) is not bool
    ):
        fail("fixed controls and cache evidence policy are unsupported")
    for name, value in fixed.items():
        observation = (
            {name: value} if "." not in name else {name.split(".")[0]: {name.split(".")[1]: value}}
        )
        known = _known_fact(observation, name)
        if known is None or digest(known) != digest(value):
            fail("fixed control needs a known supported typed expectation")
    return data, receipt, path


def match_campaign(loaded: dict, cases: dict, cell: dict, policy: dict) -> None:
    manifest = loaded["data"]["manifest"]
    controls = manifest["controls"]
    if (
        any(
            controls[name] != cases[name] for name in ("model", "backend", "concurrency", *TIMEOUTS)
        )
        or manifest["population"]["replicates"] != cases["expected_replicates"]
        or controls["targets"] != policy["targets"]
    ):
        fail("campaign controls or targets disagree with the named load cell")
    observed = manifest["ordered_descriptors"]
    declared = cases["ordered_descriptors"]
    if len(observed) != len(declared):
        fail("campaign descriptor population disagrees with declaration")
    for index, (actual, wanted) in enumerate(zip(observed, declared)):
        if {name: actual[name] for name in DESCRIPTOR_FIELDS} != wanted:
            fail("campaign request commitments disagree with declaration")
        expected = float(index) * float(cell["arrival_interval_seconds"])
        value = float(actual["arrival_offset_s"])
        tolerance = SCHEDULE_ROUNDOFF_ULPS * max(math.ulp(value), math.ulp(expected))
        if abs(value - expected) > tolerance:
            fail("campaign arrivals disagree with the named uniform schedule")


@dataclass(frozen=True)
class HeldEnvelope:
    cases: dict
    policy: dict
    campaigns: dict[str, dict] = field(repr=False)
    inputs: dict
    budgets: dict
    protected_paths: tuple[Path, ...] = field(repr=False)


def load_inputs(cases: object, campaigns: Mapping, policy: object) -> HeldEnvelope:
    if source_path(cases) is not None and source_path(cases) == source_path(policy):
        fail("distinct input roles cannot share one declaration path")
    declared, case_receipt, case_path = cases_from(cases)
    chosen, policy_receipt, policy_path = policy_from(policy)
    if not isinstance(campaigns, Mapping):
        fail("campaigns must be a mapping of declared cell names")
    sources = dict(campaigns)
    names = {cell["name"] for cell in declared["cells"]}
    if not set(sources) <= names:
        fail("campaign mapping contains an undeclared cell")
    held: dict[Path, dict] = {}
    loaded: dict[str, dict] = {}
    remaining = MAX_CAMPAIGN_TOTAL_BYTES
    declaration_paths = {path for path in (case_path, policy_path) if path is not None}
    protected = list(declaration_paths)
    for cell in declared["cells"]:
        name = cell["name"]
        if name not in sources:
            continue
        source = sources[name]
        path = source_path(source)
        if path in declaration_paths:
            fail("campaign path aliases a declaration input")
        if path is not None and path in held:
            cached = held[path]
            if cached["size_bytes"] > remaining:
                fail("declared campaign occurrences exceed 32 MiB budget")
            remaining -= cached["size_bytes"]
            loaded[name] = copy.deepcopy(cached)
        else:
            if remaining <= 0:
                fail("declared campaign occurrences exceed 32 MiB budget")
            snapshot = load_campaign(source, limit=min(MAX_CAMPAIGN_BYTES, remaining))
            remaining -= snapshot["size_bytes"]
            if path is not None:
                held[path] = snapshot
            loaded[name] = snapshot
        item = loaded[name]
        match_campaign(item, declared, cell, chosen)
        protected.extend(
            ([item["path"]] if item["path"] is not None else []) + list(item["protected_paths"])
        )
    return HeldEnvelope(
        declared,
        chosen,
        loaded,
        {
            "cases": case_receipt,
            "policy": policy_receipt,
            "campaigns": {
                name: {key: value[key] for key in ("sha256", "size_bytes", "fingerprint")}
                for name, value in loaded.items()
            },
        },
        {
            "cases": {"limit_bytes": MAX_CASES_BYTES, "charged_bytes": case_receipt["size_bytes"]},
            "policy": {
                "limit_bytes": MAX_POLICY_BYTES,
                "charged_bytes": policy_receipt["size_bytes"],
            },
            "campaigns": {
                "per_campaign_limit_bytes": MAX_CAMPAIGN_BYTES,
                "declared_total_limit_bytes": MAX_CAMPAIGN_TOTAL_BYTES,
                "charged_bytes": MAX_CAMPAIGN_TOTAL_BYTES - remaining,
            },
            "scope": (
                "separate declaration budgets and charged campaign occurrences; "
                "not a transport/output limit"
            ),
        },
        tuple(dict.fromkeys(protected)),
    )
