"""Fixed benchmark prompts for reproducible inference measurements.

Three tiers of prompt length to exercise different aspects of the
serving pipeline: TTFT isolation (short), balanced benchmarking
(medium), and context handling (long).
"""

from __future__ import annotations

# Short (~20 tokens input) -- isolates TTFT
PROMPT_SHORT = "Explain what a neural network is in one sentence."

# Medium (~60 tokens input) -- balanced benchmark
PROMPT_MEDIUM = (
    "You are a helpful assistant. Explain the key differences between "
    "supervised learning and unsupervised learning. Include two examples "
    "of each approach and describe when you would use one over the other."
)

# Long (~200 tokens input) -- tests context handling
PROMPT_LONG = (
    "You are a technical writer creating documentation for a software team. "
    "Write a comprehensive guide covering the following topics:\n"
    "1. What is continuous integration and why is it important?\n"
    "2. How to set up a basic CI pipeline with automated testing.\n"
    "3. Best practices for writing testable code.\n"
    "4. Common pitfalls and how to avoid them.\n"
    "5. Metrics to track for CI pipeline health.\n"
    "Include specific examples and actionable recommendations."
)

DEFAULT_PROMPT = PROMPT_MEDIUM
