"""TR133 — Predictive Capacity Planner.

Operationalizes findings from 14 completed TRs (~70,000 measurements) into a
CLI tool that recommends optimal model + quantization + backend configurations
for a given deployment scenario.

Usage:
    python -m research.tr133.run -v          # Fit models + validate
    python -m research.tr133.plan --help     # CLI capacity planner
"""
