"""Offline inspection of portable weight-space artifacts."""

from .adapter import AdapterAdmission, admit_adapter
from .footprint import Footprint, estimate_footprint
from .manifest import ManifestError, VerifiedBundle, verify_bundle

from .staging import StagedBundle, current_bundle, stage_bundle

__all__ = [
    "StagedBundle",
    "current_bundle",
    "stage_bundle",
    "AdapterAdmission",
    "admit_adapter",
    "Footprint",
    "estimate_footprint",
    "ManifestError",
    "VerifiedBundle",
    "verify_bundle",
]
