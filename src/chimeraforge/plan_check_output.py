"""Bounded JUnit projection of a finalized saved check."""

from __future__ import annotations

from collections.abc import Iterator
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from chimeraforge.api import PlanError
from chimeraforge.bench.fleet_gate_output import MAX_JUNIT_BYTES, _write
from chimeraforge.plan_check import _local_file
from chimeraforge.plan_study import protect_output

LOG = logging.getLogger(__name__)
SUITE_NAME = "chimeraforge.saved-check"
COMPONENTS = {
    "tool",
    "replay_context",
    "corpus",
    "quality",
    "hardware",
    "price",
    "inputs",
    "engine_support",
    "policy_sha256",
    "contributions",
    "grid",
    "installed_bundled_corpus",
    "cloud",
}
CHECKPOINTS = {"pinned_metadata", "requested_ref", "served_weights"}
SKIPPED = {
    "unchanged": "Optional observation",
    "changed": "Optional evidence changed",
    "expired": "Optional evidence expired",
    "unverified": "Optional evidence unverified",
    "not_used": "Not used",
}


def _outcome(row: dict, *, unconditional_change: bool = False) -> tuple[str, str] | None:
    state, required = row["state"], row["required"]
    if type(required) is not bool or state not in SKIPPED:
        raise PlanError("invalid native saved check result")
    if state == "changed" and (required or unconditional_change):
        return "failure", "Native evidence changed"
    if required and state == "expired":
        return "failure", "Required evidence expired"
    if required and state == "unverified":
        return "error", "Required evidence unverified"
    if required and state == "unchanged":
        return None
    return "skipped", SKIPPED[state]


def _cases(report: dict) -> Iterator[tuple[str, tuple[str, str] | None]]:
    for name, row in report["components"].items():
        if name not in COMPONENTS:
            raise PlanError("invalid native saved check component")
        yield f"component.{name}", _outcome(row)
    for ordinal, row in enumerate(report["resolution_view"].values(), 1):
        yield f"resolution.{ordinal}", _outcome(row, unconditional_change=True)
    for ordinal, rows in enumerate(report["checkpoint_view"].values(), 1):
        for name, row in rows.items():
            if name not in CHECKPOINTS:
                raise PlanError("invalid native saved check checkpoint")
            yield f"checkpoint.{ordinal}.{name}", _outcome(row, unconditional_change=True)
    comparison = report["comparison"]
    if comparison is None:
        yield "comparison", ("skipped", "Comparison unavailable")
    elif comparison["changed"] is True:
        yield "comparison", ("failure", "Native comparison changed")
    elif comparison["changed"] is False:
        yield "comparison", None
    else:
        raise PlanError("invalid native saved check comparison")
    yield "performance", _outcome(report["performance"])


def materialize(report: dict) -> bytes:
    suite = ET.Element("testsuite", name=SUITE_NAME)
    counts = {"failure": 0, "error": 0, "skipped": 0}
    remaining = MAX_JUNIT_BYTES
    for name, outcome in _cases(report):
        case = ET.SubElement(suite, "testcase", classname=SUITE_NAME, name=name)
        if outcome is not None:
            tag, message = outcome
            counts[tag] += 1
            ET.SubElement(case, tag, message=message)
        remaining -= len(ET.tostring(case, encoding="utf-8"))
        if remaining < 0:
            raise PlanError("complete saved check JUnit exceeds its byte limit")
    code = report["exit_code"]
    if type(code) is not int or code != int(bool(counts["failure"] or counts["error"])):
        raise PlanError("saved check JUnit disagrees with native exit")
    suite.set("tests", str(len(suite)))
    suite.set("failures", str(counts["failure"]))
    suite.set("errors", str(counts["error"]))
    suite.set("skipped", str(counts["skipped"]))
    raw: bytes = ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"
    if len(raw) > MAX_JUNIT_BYTES:
        raise PlanError("complete saved check JUnit exceeds its byte limit")
    return raw


def plan_input_paths(report: dict) -> Iterator[Path]:
    """Protect host-native file roles the existing check observed or retained."""
    for name in ("corpus", "quality"):
        row = report["components"].get(name, {})
        for key in ("before", "after", "current_source"):
            value = row.get(key)
            if isinstance(value, dict):
                receipt = value.get("input", value)
                if isinstance(receipt, dict) and receipt.get("kind") == "file":
                    path = _local_file(receipt)
                    if path is not None:
                        yield path


def protect_junit(path: Path, inputs: tuple[Path, ...]) -> None:
    try:
        protect_output(path, inputs)
        if path.exists() and not path.is_file():
            raise ValueError("expected a file destination")
    except (OSError, ValueError, RuntimeError) as exc:
        LOG.info("Saved check JUnit destination refused (%s)", type(exc).__name__)
        raise PlanError("invalid or unsafe saved check JUnit destination") from None


def publish_junit(report: dict, path: Path, inputs: tuple[Path, ...]) -> None:
    protect_junit(path, inputs)
    raw = materialize(report)
    try:
        _write(path, raw)
    except PlanError as exc:
        LOG.info("Saved check JUnit publication refused (%s)", type(exc).__name__)
        raise PlanError("cannot publish saved check JUnit") from None
