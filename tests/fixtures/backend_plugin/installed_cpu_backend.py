"""Test-only CPU work and tokenizer; this fixture is not an LLM inference engine."""

from __future__ import annotations

import hashlib
import time

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics


class InstalledCPUBackend(Backend):
    name = "installed-cpu"
    instances = []

    def __init__(self, base_url=None):
        self.base_url = base_url
        self.closed = False
        self.instances.append(self)

    async def health_check(self):
        return True, "test-only CPU fixture"

    async def check_model(self, model):
        return model == "fixture", "Only fixture is available in this test adapter"

    async def get_version(self):
        return "1.0.0-test-fixture"

    async def generate(self, model, prompt, options=None):
        start = time.perf_counter()
        # Count whitespace tokens for this fixture only; exercise actual CPU work.
        tokens = len(prompt.split())
        hashlib.pbkdf2_hmac("sha256", prompt.encode("utf-8"), b"fixture", 2000)
        elapsed_s = time.perf_counter() - start
        return RunMetrics(tokens, tokens / elapsed_s, -1, elapsed_s * 1000, 0, elapsed_s * 1000)

    async def generate_text(self, model, prompt, options=None):
        return "I cannot help with that request."

    async def close(self):
        self.closed = True
