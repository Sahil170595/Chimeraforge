"""Provenance classes, and the one place that reads them.

A provenance value is either a bare class string, or a dict carrying the class
plus the anchor that makes the claim self-describing::

    "quality":    "measured"
    "throughput": {"class": "extrapolated", "measured_on": "RTX 4080 12GB",
                   "measured_tps": 95.9, "ratio": 13.83, "basis": "memory bandwidth"}

The dict form exists because ``extrapolated`` is otherwise a bare adjective that
reads, to a skimming reader, as stronger than ``estimated``. Emitting the anchor
alongside it means the label cannot be read as more than it is: a real
measurement, taken somewhere else, scaled by a stated ratio.

Every consumer goes through :func:`prov_class` rather than comparing the raw
value, so adding a class cannot silently change a rendering site's behaviour.
"""

from __future__ import annotations

from typing import Any

# Exact arithmetic over the inputs and the GPU database -- VRAM, KV-cache, GPU
# count, monthly cost. Not a prediction, and not a measurement: filing it under
# `measured` cites the TR benchmark corpus as the source of a number that corpus
# never measured.
PROV_DERIVED = "derived"
# A row from the bundled corpus, on the rig that corpus was measured on.
PROV_MEASURED = "measured"
# A real measurement transported to hardware it was not taken on. Any
# bandwidth_ratio != 1.0 lands here -- no threshold, because any threshold would
# be chosen to make the output look better.
PROV_EXTRAPOLATED = "extrapolated"
# A first-principles model: roofline, FP16 baseline + quant delta, family prior.
PROV_ESTIMATED = "estimated"
# Not screened. Reported as unvalidated rather than filled with a default.
PROV_UNKNOWN = "unknown"

# Best-grounded first. `fleet` takes the worst across the GPU types it used, so a
# class missing from this tuple must sort as the worst rather than the best.
PROVENANCE_ORDER = (
    PROV_DERIVED,
    PROV_MEASURED,
    PROV_EXTRAPOLATED,
    PROV_ESTIMATED,
    PROV_UNKNOWN,
)

# The basis strings an `extrapolated` anchor may name. Free text here would let a
# render site print an unreviewed justification.
BASIS_MEMORY_BANDWIDTH = "memory bandwidth"


def prov_class(value: Any) -> str:
    """The class of a provenance value, whichever form it takes.

    An unrecognised value is ``unknown`` rather than an error: a rendering site
    must never crash on a payload, and must never treat something it cannot
    place as grounded.
    """
    if isinstance(value, str):
        return value if value in PROVENANCE_ORDER else PROV_UNKNOWN
    if isinstance(value, dict):
        return prov_class(value.get("class"))
    return PROV_UNKNOWN


def prov_anchor(value: Any) -> dict[str, Any]:
    """The anchor fields of a provenance value, minus the class. ``{}`` if bare."""
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if k != "class"}


def from_corpus_row(
    *,
    measured_on: str,
    measured_tps: float,
    ratio: float,
    reported_tps: float,
    basis: str = BASIS_MEMORY_BANDWIDTH,
) -> str | dict[str, Any]:
    """Provenance for a throughput that started life as a bundled corpus row.

    Two things can happen to a row between the corpus and the plan, and both have
    to be disclosed or the label overstates what the number is:

    * it is **transported** to another GPU (``ratio != 1.0``), which makes it
      ``extrapolated`` -- no threshold, since any threshold would be picked to
      make the output look better; and
    * it is **clamped** to the memory-bandwidth ceiling, which several bundled
      rows exceed (``llama3.2-3b|ollama|FP16`` implies 142.5% of peak). When the
      clamp binds, the reported number is the ceiling, not the measurement -- so
      an anchor saying ``measured_tps x ratio`` would name a product the caller
      cannot reproduce from the value it is attached to.

    ``measured_tps`` is always the row itself, before either step, so a reader
    can recover what was actually observed. A row that was neither transported
    nor clamped is the measurement, and says so with no anchor to add.
    """
    transported = ratio != 1.0
    # Strictly below, with room for float error: equality means the clamp was
    # present but not binding, which is not a modification worth disclosing.
    clamped = reported_tps < measured_tps * ratio * (1.0 - 1e-9)
    if not transported and not clamped:
        return PROV_MEASURED
    anchor: dict[str, Any] = {
        "class": PROV_EXTRAPOLATED if transported else PROV_MEASURED,
        "measured_on": measured_on,
        "measured_tps": round(measured_tps, 2),
    }
    if transported:
        anchor["ratio"] = round(ratio, 4)
        anchor["basis"] = basis
    if clamped:
        # Named, not silent: the corpus row is above what the memory bus can
        # deliver, so the physical bound is what got reported.
        anchor["clamped_to_bandwidth_ceiling"] = True
        anchor["reported_tps"] = round(reported_tps, 2)
    return anchor


def derived(basis: str) -> dict[str, Any]:
    """A `derived` value naming the arithmetic it came out of."""
    return {"class": PROV_DERIVED, "basis": basis}


def worst(values: list[Any]) -> str:
    """The least-grounded class among ``values``.

    A mix is only as trustworthy as its least-grounded member; reporting the best
    would let one measured GPU launder several estimated ones.
    """
    if not values:
        return PROV_UNKNOWN
    return PROVENANCE_ORDER[max(PROVENANCE_ORDER.index(prov_class(v)) for v in values)]


# Bases a `derived` value may name. Each says which arithmetic produced the
# number, so "derived" is never a bare adjective either.
VRAM_BASIS_REGISTRY = "weights + KV-cache + activations over the registry architecture"
VRAM_BASIS_RESOLVED = "weights + KV-cache + activations over the resolved architecture"
COST_BASIS = "GPU-hours x the dated price snapshot"


# Marks that survive being skim-read. `extrapolated` gets its own mark rather
# than sharing `~` with `estimated`: they are different claims, and collapsing
# them loses the distinction between "a model said so" and "a benchmark said so,
# about another card".
MARK_EXTRAPOLATED = "^"
PROVENANCE_MARK = {
    PROV_DERIVED: "",
    PROV_MEASURED: "",
    PROV_EXTRAPOLATED: MARK_EXTRAPOLATED,
    PROV_ESTIMATED: "~",
    PROV_UNKNOWN: "?",
}
# Rendered wherever marks appear, so a reader never has to guess what a glyph
# claims. A mark with no legend entry is an unexplained assertion.
PROVENANCE_LEGEND = (
    f"{PROVENANCE_MARK[PROV_ESTIMATED]} estimated (modelled)  "
    f"{MARK_EXTRAPOLATED} extrapolated (measured on another GPU)  "
    f"{PROVENANCE_MARK[PROV_UNKNOWN]} unknown (unscreened)"
)


def prov_mark(value: Any) -> str:
    """The skim-readable mark for a provenance value."""
    return PROVENANCE_MARK[prov_class(value)]
