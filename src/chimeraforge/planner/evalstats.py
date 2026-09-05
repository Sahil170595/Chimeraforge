"""Sample size, minimum detectable effect, and what a 20-item eval can support.

P8.4. The quality gate is the planner's cleanest differentiator -- nobody else
rejects a quantization level on quality before touching hardware -- and it was
built on the corpus's weakest data. The bundled eval is **20 items total** (10
general_knowledge, 5 summarization, 5 code), and the quant deltas derived from it
say Q4_K_M, Q5_K_M, Q6_K and Q8_0 all score *above* FP16. For llama3.2-3b the
lookup returns, every one of them labelled `measured`::

    FP16 0.5376 | Q2_K 0.5819 | Q3_K_S 0.5824 | Q4_K_M 0.6241
    Q5_K_M 0.6247 | Q6_K 0.6261 | Q8_0 0.6277

2-bit beating FP16 by 8% has no plausible mechanism. What it has is a sample
size, and Miller (arXiv:2411.00640, "Adding Error Bars to Evals") gives the
arithmetic for exactly this. Equation 9, transcribed from the paper::

    n = (z_{alpha/2} + z_beta)^2 * (omega^2 + sigma_A^2/K_A + sigma_B^2/K_B) / delta^2

with ``omega^2 = Var(x_A) + Var(x_B) - 2 Cov(x_A, x_B)`` for a paired analysis,
``sigma^2`` the expected conditional (resampling) variance, and ``K`` the samples
drawn per question. Inverted for a fixed ``n`` it gives the minimum detectable
effect.

**At n = 20 the MDE is +-20.9 percentage points.** The corpus's entire measured
quant-delta range -- Q2_K -10.4pp through Q4_K_M +1.8pp -- is a 14.2pp spread
sitting *inside* the noise floor. Not one of the six deltas is distinguishable
from zero, including the Q2_K value that happens to point the right way.
Detecting a real 2pp difference would take about 2,180 paired questions.

This is not a ChimeraForge peculiarity. Red Hat AI's published card for
Meta-Llama-3.1-8B-Instruct-FP8-dynamic reports 156.0% recovery on GPQA (3.7 ->
5.7) with no error bars anywhere on it. Being the tool that reports the interval
is the differentiator; the artifact itself is industry-standard.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

SOURCE = "Miller 2024, arXiv:2411.00640 Eq. 9"

# Conventional two-sided significance and 80% power -- the levels Miller's own
# worked example uses, so the implementation is checkable against a published
# number rather than against itself.
DEFAULT_ALPHA = 0.05
DEFAULT_POWER = 0.80

# omega^2 for a paired comparison of two models whose per-question scores are
# uniform on [0, 1] and correlated at 0.5. Miller's Section 4.2 states the paired
# analysis takes the estimator variance "from 1/6 to 1/9 in absolute terms", and
# Section 5's worked example uses 1/9 directly.
#
# It is an ASSUMPTION, not a measurement of this corpus: the bundled data stores
# per-cell means, not per-item scores, so the real omega^2 cannot be computed
# from it. Named here so a reader can see which number is doing the work, and
# overridable by any caller that does have per-item data.
OMEGA_SQ_UNIFORM_PAIRED = 1.0 / 9.0

# The bundled composite. A score against a different metric is not comparable to
# one against this, and mixing them would fabricate a comparison, so the name
# travels with every cell.
BUNDLED_METRIC = "chimeraforge-composite-v1"
BUNDLED_EVAL_N = 20
BUNDLED_EVAL_SOURCE = "TR125"


def _z(p: float) -> float:
    """The (1-p)th percentile of the standard normal."""
    return statistics.NormalDist().inv_cdf(1.0 - p)


def sample_size(
    delta: float,
    omega_sq: float = OMEGA_SQ_UNIFORM_PAIRED,
    sigma_a_sq: float = 0.0,
    sigma_b_sq: float = 0.0,
    k_a: int = 1,
    k_b: int = 1,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> float:
    """Questions needed to detect a mean difference ``delta``. Miller Eq. 9.

    Reproduces the paper's worked example exactly: with ``sigma_A^2 = sigma_B^2 =
    0``, ``omega^2 = 1/9``, ``delta = 0.03``, ``alpha = 0.05`` and 80% power it
    returns 969, which is the figure printed in Section 5.
    """
    if delta <= 0:
        return math.inf
    z_sum = _z(alpha / 2.0) + _z(1.0 - power)
    variance = omega_sq + sigma_a_sq / max(k_a, 1) + sigma_b_sq / max(k_b, 1)
    return z_sum**2 * variance / delta**2


def minimum_detectable_effect(
    n: int,
    omega_sq: float = OMEGA_SQ_UNIFORM_PAIRED,
    sigma_a_sq: float = 0.0,
    sigma_b_sq: float = 0.0,
    k_a: int = 1,
    k_b: int = 1,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> float:
    """The smallest difference ``n`` questions can resolve. Eq. 9, inverted.

    Returns a mean-score difference, not a percentage. ``inf`` for a
    non-positive ``n``, so an unsized cell can never look precise.
    """
    if n <= 0:
        return math.inf
    z_sum = _z(alpha / 2.0) + _z(1.0 - power)
    variance = omega_sq + sigma_a_sq / max(k_a, 1) + sigma_b_sq / max(k_b, 1)
    return z_sum * math.sqrt(variance / n)


@dataclass(frozen=True)
class QualityCell:
    """One quality score, inseparable from what it can support.

    A bare float invites a comparison the data cannot bear. Every field here
    exists to stop one:

    * ``n`` and ``mde`` say how big a difference this cell could even detect;
    * ``metric`` stops a score against `lm-evaluation-harness` MMLU being
      compared with one against the bundled composite -- different scales, and
      averaging or ranking across them would manufacture a result;
    * ``source`` says where it came from.
    """

    score: float
    n: int
    metric: str = BUNDLED_METRIC
    source: str = BUNDLED_EVAL_SOURCE
    omega_sq: float = OMEGA_SQ_UNIFORM_PAIRED

    @property
    def mde(self) -> float:
        """Smallest difference this cell's sample size can resolve."""
        return minimum_detectable_effect(self.n, omega_sq=self.omega_sq)

    @property
    def mde_pp(self) -> float:
        return self.mde * 100.0

    @property
    def lower(self) -> float:
        return max(0.0, self.score - self.mde)

    @property
    def upper(self) -> float:
        return min(1.0, self.score + self.mde)

    def indistinguishable_from(self, other: float) -> bool:
        """True when this cell cannot tell its score apart from ``other``."""
        return abs(self.score - other) <= self.mde

    def overlaps(self, other: QualityCell) -> bool:
        """True when two cells' intervals overlap -- so ranking them is ranking noise.

        Comparing across metrics is refused rather than answered: an MMLU score
        and the bundled composite are different scales, and an overlap test
        between them would be arithmetic on incomparable numbers.
        """
        if self.metric != other.metric:
            return True
        return self.lower <= other.upper and other.lower <= self.upper


def resolves_to_baseline(score: float, baseline: float, n: int, omega_sq: float) -> bool:
    """Whether a quantized cell's difference from its FP16 baseline is real.

    ``True`` means it is not: the observed gap is inside what ``n`` items can
    resolve, so the honest report is "no detectable difference", in either
    direction. That covers both halves of the corpus's problem -- the four quants
    scoring *above* FP16 (which no mechanism explains) and Q2_K's -10.4pp (which
    points the right way but is equally inside the noise).

    llama.cpp's published perplexity/KL table for Llama-3-8B is strictly monotone
    in bit width and never puts a quant above FP16. It is a different metric, so
    it can *falsify* this corpus's ordering -- and it does -- but it can never
    supply a composite score to replace one with.
    """
    return abs(score - baseline) <= minimum_detectable_effect(n, omega_sq=omega_sq)


# The context length the bundled quality corpus was measured at. A cell measured
# here does not license a verdict at 64K.
BUNDLED_EVAL_CONTEXT = 2048
# Where the published long-context degradation becomes large enough that a
# short-context measurement stops describing the same thing. arXiv:2505.20276,
# across 9.7K test examples, five quantization methods and five models: "8-bit
# quantization preserves accuracy (~0.8% drop), whereas 4-bit methods lead to
# substantial losses, especially for tasks involving long-context inputs (drops
# of up to 59%)". A single scalar per (model, quant) cannot be right at both 2K
# and 64K, so the gate reports UNKNOWN there rather than extrapolating.
LONG_CONTEXT_THRESHOLD = 65536
LONG_CONTEXT_SOURCE = "arXiv:2505.20276"
# Below this effective width the published long-context losses apply. 8-bit is
# reported as near-lossless, so it is not swept up with the 4-bit cells.
LONG_CONTEXT_AT_RISK_BPW = 8.0


def context_licenses_the_cell(context_length: int, bpw: float) -> bool:
    """Whether a short-context quality measurement still describes this plan.

    False when the plan runs long context on a narrow quant -- the regime where
    the same configuration is near-lossless at 2K and catastrophic at 64K.
    """
    return not (context_length >= LONG_CONTEXT_THRESHOLD and bpw < LONG_CONTEXT_AT_RISK_BPW)
