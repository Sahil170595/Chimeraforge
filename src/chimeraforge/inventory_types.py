"""A queried inventory view and saved-baseline arithmetic, without allocation claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

MemoryBasis = Literal["batch-one", "selected-batch"]
MemoryComparison = Literal[
    "at_least_saved_baseline",
    "below_saved_baseline",
    "unknown",
    "at_least_selected_batch_estimate",
    "below_selected_batch_estimate",
]

UNASSESSED = (
    "physical_identity",
    "independent_memory_pools",
    "partition_topology",
    "cuda_process_visibility",
    "hardware_equivalence",
    "engine_compatibility",
    "runtime_peak",
    "allocation",
    "deployment_eligibility",
)


class InventoryCheckError(ValueError):
    """Malformed original source, options or selector declarations."""


@dataclass(frozen=True)
class InventoryDevice:
    ordinal: str
    uuid: str
    name: str
    memory_total_mib: str | None
    memory_free_mib: str | None
    driver_version: str
    mig_mode_raw: str


@dataclass(frozen=True)
class InventoryBaseline:
    saved_gib: str | None
    lower_gib: str | None
    upper_gib: str | None
    basis: Literal["saved_modeled_batch1_per_gpu", "unsupported"]
    saved_effective_batch: int
    reason: str | None = None


@dataclass(frozen=True)
class SelectedBatchBaseline:
    saved_batch1: InventoryBaseline
    saved_effective_batch: int
    saved_context_length: int | None
    kv_quant: str | None
    tensor_parallel: int
    pipeline_parallel: int
    per_sequence_increment_gib: str | None = None
    selected_lower_gib: str | None = None
    selected_upper_gib: str | None = None
    status: Literal["estimated", "unsupported"] = "unsupported"
    reason: str | None = None
    formula_id: str | None = None
    basis: Literal["saved_b1_plus_selected_batch_increment"] = (
        "saved_b1_plus_selected_batch_increment"
    )
    interval_scope: Literal["saved_decimal_serialization_only"] = "saved_decimal_serialization_only"
    increment_scope: Literal["full_saved_context_per_active_sequence"] = (
        "full_saved_context_per_active_sequence"
    )
    unassessed_residency: tuple[str, ...] = (
        "idle_sessions",
        "prefix_pools",
        "runtime_workspace",
        "runtime_peak",
    )


@dataclass(frozen=True)
class InventorySlot:
    replica_index: int
    device_index: int
    selector: str
    selector_state: Literal["present", "absent", "unknown"]
    device: InventoryDevice | None = None
    free_comparison: MemoryComparison = "unknown"
    total_comparison: MemoryComparison = "unknown"
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class InventoryObservation:
    state: Literal["complete", "unknown", "not_started"]
    command: tuple[str, ...]
    started_at: str | None = None
    finished_at: str | None = None
    returncode: int | None = None
    reason: str | None = None
    devices: tuple[InventoryDevice, ...] = ()
    stdout_sha256: str | None = None
    cleanup_state: Literal["completed", "not_started", "failed"] = "not_started"


@dataclass(frozen=True)
class InventoryCaptureObservation:
    """A supplied CSV view without native query or process provenance."""

    state: Literal["complete", "unknown", "not_started"]
    reason: str | None = None
    devices: tuple[InventoryDevice, ...] = ()
    capture_sha256: str | None = None
    source: Literal["supplied_nvidia_smi_csv"] = "supplied_nvidia_smi_csv"


@dataclass(frozen=True)
class InventoryCheck:
    tool_version: str
    plan_fingerprint: str
    candidate_index: int
    baseline: InventoryBaseline | SelectedBatchBaseline
    observation: InventoryObservation | InventoryCaptureObservation
    slots: tuple[InventorySlot, ...]
    schema_version: int = 1
    scope: Literal[
        "queried_inventory_and_saved_b1_memory",
        "queried_inventory_and_selected_batch_memory",
        "supplied_inventory_and_saved_b1_memory",
        "supplied_inventory_and_selected_batch_memory",
    ] = "queried_inventory_and_saved_b1_memory"
    deployment_ready: None = None
    unassessed: tuple[str, ...] = UNASSESSED

    @property
    def exit_code(self) -> int:
        if self.observation.state != "complete" or (
            isinstance(self.observation, InventoryObservation)
            and self.observation.cleanup_state != "completed"
        ):
            return 4
        if any(
            slot.selector_state == "absent"
            or slot.free_comparison in ("below_saved_baseline", "below_selected_batch_estimate")
            for slot in self.slots
        ):
            return 5
        if not self.slots or any(
            slot.selector_state != "present"
            or slot.free_comparison
            not in ("at_least_saved_baseline", "at_least_selected_batch_estimate")
            for slot in self.slots
        ):
            return 4
        return 0

    @property
    def outcome(self) -> Literal["pass", "unknown", "mismatch"]:
        return "pass" if self.exit_code == 0 else "mismatch" if self.exit_code == 5 else "unknown"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(exit_code=self.exit_code, outcome=self.outcome)
        data["declared_coverage"] = {
            "expected": len(self.slots),
            **{
                key: sum(slot.selector_state == key for slot in self.slots)
                for key in ("present", "absent", "unknown")
            },
        }
        return data
