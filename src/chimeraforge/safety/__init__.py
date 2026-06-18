"""Live safety screening — refusal-rate measurement against a running model.

The planner's safety gate (``chimeraforge.planner``) makes deployment
*decisions* from bundled TR134/TR142 data. This package *measures*: it runs
refusal-probe prompts against a live model and classifies refusals, so a
(model, quant) the bundled table does not cover can still be screened before
deployment. Exposed via ``chimeraforge safety`` (the ``[safety]`` extra).
"""

from chimeraforge.safety.classifier import classify_refusal, refusal_pattern_count
from chimeraforge.safety.runner import SafetyScreenResult, run_safety_screen

__all__ = [
    "SafetyScreenResult",
    "classify_refusal",
    "refusal_pattern_count",
    "run_safety_screen",
]
