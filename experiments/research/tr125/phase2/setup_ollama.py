"""Setup script for TR125 Phase 2: discover and pull Ollama model tags.

Pulls all 34 Ollama model tags required for the production-grade decision matrix.
4 small models × 7 quant levels (incl FP16) + 1 8B model × 6 quant levels (no FP16).

Usage:
    python research/tr125/phase2/setup_ollama.py [--dry-run] [--check-only]
    python research/tr125/phase2/setup_ollama.py --ollama-url http://localhost:11434
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import subprocess
import sys
import time

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
sys.path.insert(0, str(_REPO))

from research.tr125.shared.utils import (
    OLLAMA_BASE_TAGS,
    OLLAMA_QUANT_SUFFIXES,
    build_ollama_tag,
    list_local_ollama_tags,
)

logger = logging.getLogger("tr125.phase2.setup")

# Skip list: models that won't fit on consumer GPU
SKIP_COMBOS: set[tuple[str, str]] = {
    ("llama3.1-8b", "FP16"),  # ~16GB, exceeds RTX 4080 with overhead
}

# Build 34 required tags: 4 small × 7 + 1 8B × 6
REQUIRED_TAGS: list[tuple[str, str, str]] = []  # (base_name, quant_level, ollama_tag)
for base_name, base_tag in sorted(OLLAMA_BASE_TAGS.items()):
    for quant_level in OLLAMA_QUANT_SUFFIXES:
        if (base_name, quant_level) in SKIP_COMBOS:
            continue
        tag = build_ollama_tag(base_tag, quant_level)
        REQUIRED_TAGS.append((base_name, quant_level, tag))


@dataclass
class TagResult:
    base_model: str
    quant_level: str
    tag: str
    available: bool
    action: str  # "already_local", "pulled", "failed", "skipped"
    message: str
    elapsed_s: float = 0.0


def check_tag_available(tag: str, local_tags: set[str]) -> bool:
    """Check if a tag is available locally (exact or prefix match)."""
    if tag in local_tags:
        return True
    for local in local_tags:
        if (local.startswith(tag) or tag.startswith(local.split(":")[0] + ":")) and (
            tag in local or local == tag
        ):
            return True
    return False


def pull_model(tag: str, dry_run: bool = False) -> tuple[bool, str, float]:
    """Pull an Ollama model tag via CLI.

    Returns: (success, message, elapsed_seconds)
    """
    if dry_run:
        return True, "dry-run: would pull", 0.0

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
            return True, f"pulled in {elapsed:.0f}s", elapsed
        return False, result.stderr.strip()[:200], elapsed
    except subprocess.TimeoutExpired:
        return False, "timeout (600s)", time.perf_counter() - t0
    except FileNotFoundError:
        return False, "ollama CLI not found", 0.0
    except Exception as e:
        return False, str(e)[:200], time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Setup Ollama models for TR125 Phase 2"
    )
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be pulled without pulling",
    )
    parser.add_argument(
        "--check-only", action="store_true", help="Only check availability, don't pull"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Discover local models
    local = list_local_ollama_tags(args.ollama_url)
    if not local and not args.dry_run:
        logger.error("No local models found. Is Ollama running?")
        if args.check_only:
            print("ERROR: Cannot reach Ollama. Start it with 'ollama serve'.")
            return 1

    logger.info("Found %d local Ollama models", len(local))
    if local:
        logger.debug("Local tags: %s", ", ".join(sorted(local)[:30]))

    # Check/pull each required tag
    results: list[TagResult] = []
    for base_name, quant_level, tag in REQUIRED_TAGS:
        available = check_tag_available(tag, local)

        if available:
            results.append(
                TagResult(
                    base_model=base_name,
                    quant_level=quant_level,
                    tag=tag,
                    available=True,
                    action="already_local",
                    message="available",
                )
            )
            continue

        if args.check_only:
            results.append(
                TagResult(
                    base_model=base_name,
                    quant_level=quant_level,
                    tag=tag,
                    available=False,
                    action="skipped",
                    message="not local (check-only mode)",
                )
            )
            continue

        success, message, elapsed = pull_model(tag, dry_run=args.dry_run)
        results.append(
            TagResult(
                base_model=base_name,
                quant_level=quant_level,
                tag=tag,
                available=success,
                action="pulled" if success else "failed",
                message=message,
                elapsed_s=elapsed,
            )
        )

    # Summary
    ok = sum(1 for r in results if r.available)
    fail = sum(1 for r in results if not r.available)

    print(f"\n{'='*70}")
    mode = "CHECK" if args.check_only else ("DRY-RUN" if args.dry_run else "SETUP")
    print(f"TR125 Phase 2 {mode}: {ok} OK, {fail} MISSING of {len(results)} tags")
    print(f"{'='*70}")

    for r in results:
        status = "OK  " if r.available else "MISS"
        print(f"  [{status}] {r.tag:40s} {r.quant_level:8s} {r.message}")

    if fail > 0 and not args.check_only:
        print(f"\n{fail} tag(s) unavailable. The runner will skip missing models.")

    # Write discovery results
    discovery_path = _DIR / "discovered_tags.json"
    discovery = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ollama_url": args.ollama_url,
        "mode": mode.lower(),
        "total": len(results),
        "available": ok,
        "missing": fail,
        "tags": [asdict(r) for r in results],
    }
    discovery_path.write_text(json.dumps(discovery, indent=2), encoding="utf-8")
    logger.info("Wrote discovery results to %s", discovery_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
