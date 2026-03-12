"""Setup script for TR124 Phase 2: pull Ollama models at required quantization levels.

Usage:
    python research/tr124/phase2/setup_ollama.py [--dry-run] [--ollama-url URL]

Pulls required Ollama model tags for the Phase 2 quantization matrix.
Each base model needs Q4_K_M (default) and Q8_0 variants.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
import subprocess
import sys
import time
import urllib.request

logger = logging.getLogger("tr124.phase2.setup")

# Tags required for Phase 2 config.yaml
REQUIRED_TAGS = [
    "llama3.2:1b",
    "llama3.2:1b-q8_0",
    "llama3.2:3b",
    "llama3.2:3b-q8_0",
    "qwen2.5:1.5b",
    "qwen2.5:1.5b-q8_0",
    "phi:2.7b",
    "phi:2.7b-q8_0",
]


@dataclass
class PullResult:
    tag: str
    success: bool
    message: str
    elapsed_s: float = 0.0


def list_local_models(url: str) -> set[str]:
    """Get set of model tags already pulled locally."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return {m["name"] for m in data.get("models", [])}
    except Exception as e:
        logger.error("Cannot reach Ollama at %s: %s", url, e)
        return set()


def pull_model(tag: str, dry_run: bool = False) -> PullResult:
    """Pull an Ollama model tag via CLI."""
    if dry_run:
        return PullResult(tag=tag, success=True, message="dry-run: would pull")

    logger.info("Pulling %s ...", tag)
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            ["ollama", "pull", tag],
            capture_output=True,
            text=True,
            timeout=600,
        )
        elapsed = time.perf_counter() - t0
        if result.returncode == 0:
            return PullResult(
                tag=tag,
                success=True,
                message=f"pulled in {elapsed:.0f}s",
                elapsed_s=elapsed,
            )
        return PullResult(
            tag=tag, success=False, message=result.stderr.strip(), elapsed_s=elapsed
        )
    except Exception as e:
        return PullResult(
            tag=tag, success=False, message=str(e), elapsed_s=time.perf_counter() - t0
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Setup Ollama models for TR124 Phase 2"
    )
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be pulled without pulling",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    local = list_local_models(args.ollama_url)
    if not local and not args.dry_run:
        logger.error("No local models found. Is Ollama running?")
        return 1

    logger.info("Found %d local Ollama models", len(local))

    results = []
    for tag in REQUIRED_TAGS:
        already = any(tag in m or f"{tag}:latest" in m for m in local)
        if already:
            logger.info("SKIP %s: already pulled", tag)
            results.append(
                PullResult(tag=tag, success=True, message="already available")
            )
            continue
        results.append(pull_model(tag, dry_run=args.dry_run))

    # Summary
    ok = sum(1 for r in results if r.success)
    fail = sum(1 for r in results if not r.success)
    print(f"\n{'='*60}")
    print(f"Phase 2 Setup: {ok} OK, {fail} FAILED of {len(results)} tags")
    print(f"{'='*60}")
    for r in results:
        status = "OK  " if r.success else "FAIL"
        print(f"  [{status}] {r.tag:30s} {r.message}")

    if fail > 0:
        print(f"\n{fail} model(s) failed. The runner will skip unavailable models.")

    return 1 if fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
