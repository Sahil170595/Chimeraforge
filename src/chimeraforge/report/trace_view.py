"""Closed presentation facts: no raw identities, diagnostics or metadata."""

from __future__ import annotations

from chimeraforge.bench.trace import BUILTIN_TPOT_BASES

ROW_STATES = {"completed", "failed", "partial", "cancelled", "not_started"}
SLO_STATES = {"pass", "breach", "unknown", "not_completed", "not_requested"}
BINDING_STATES = {"matched", "mismatch", "unavailable"}
TIMES = ("scheduled_s", "arrival_s", "start_s", "first_output_s", "terminal_s")
TIMINGS = ("scheduler_lag_ms", "client_queue_ms", "latency_ms", "first_output_ms", "tpot_ms")


def fixed(value: object, choices: set[str], fallback: str = "unavailable") -> str:
    return value if type(value) is str and value in choices else fallback


def projection(held: dict, kind: str) -> dict:
    data = held["data"]
    native = data if kind == "trace" else data["native_trace"]
    assignment = {}
    members = []
    if kind == "fleet-trace":
        for ordinal, slot in enumerate(data["slots"], 1):
            indices = [index + 1 for index in slot["row_indices"]]
            assignment.update({index: ordinal for index in indices})
            groups = [
                *slot["binding"]["summary"].values(),
                *slot["binding"]["token_lengths"].values(),
            ]
            members.append(
                {
                    "ordinal": ordinal,
                    "state": fixed(
                        slot["state"], {"error", "zero_assigned", "completed", "incomplete"}
                    ),
                    "rows": indices,
                    "slo": fixed(
                        slot["slo"]["state"],
                        {"not_requested", "breach", "incomplete", "unavailable", "observed_pass"},
                    ),
                    "bindings": {
                        s: sum(row["state"] == s for row in groups) for s in sorted(BINDING_STATES)
                    },
                    "latency": fixed(slot["latency_evidence"], {"available", "unavailable"}),
                }
            )
    rows = []
    for ordinal, row in enumerate(native["requests"], 1):
        rows.append(
            {
                "ordinal": ordinal,
                "member": assignment.get(ordinal),
                "state": fixed(row["state"], ROW_STATES),
                "times": {key: row["times"][key] for key in TIMES},
                "timing": {key: row["timing"][key] for key in TIMINGS},
                "tokens": row["native"]["tokens_generated"],
                "cap": fixed(row["output_cap_state"], {"within_cap", "exceeded", "unknown"}),
                "basis": fixed(row["mean_tpot_basis"], BUILTIN_TPOT_BASES),
                "slo": {
                    key: fixed(row["slo"][key], SLO_STATES)
                    for key in ("latency_ms", "first_output_ms", "tpot_ms", "joint")
                },
            }
        )
    cleanup = native["resource_cleanup"] if kind == "trace" else data["cleanup"]
    return {
        "kind": kind,
        "sha256": held["sha256"],
        "size_bytes": held["size_bytes"],
        "byte_basis": held["byte_basis"],
        "fingerprint": held["fingerprint"],
        "execution": "completed" if native["exit_code"] == 0 else "incomplete",
        "configuration": "not_evaluated"
        if kind == "trace"
        else fixed(data["configuration_status"], {"mismatch", "unverified"}),
        "cleanup": fixed(cleanup.get("state"), {"started", "completed", "incomplete"}),
        "exit_code": data["exit_code"],
        "clock": "planned only"
        if native["clock"]["origin"] is None
        else "observed global relative clock",
        "counts": {
            key: native["execution"][key] for key in ("planned", "attempted", *sorted(ROW_STATES))
        },
        "concurrency": native["execution"]["concurrency"],
        "targets": {
            key: native["targets"][key] for key in ("latency_ms", "first_output_ms", "tpot_ms")
        },
        "goodput": {
            key: native["goodput"][key]
            for key in (
                "qualification",
                "qualified_requests",
                "horizon_seconds",
                "requests_per_second",
            )
        },
        "joint": {key: native["goodput"]["joint_outcomes"][key] for key in sorted(SLO_STATES)},
        "members": members,
        "rows": rows,
    }
