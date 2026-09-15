"""Capture the `config.json` of every hybrid / linear-attention family we parse.

The layer-pattern and recurrent-state readers in `planner/hybrid.py` exist to
handle six different per-family spellings of the same idea. Testing them against
hand-written dicts would test my reading of those configs rather than the configs
themselves, so the fixtures are the real files, fetched from the vendor's own
repo, with the URL and the capture date stored beside them.

Re-run to refresh:

    python scripts/fetch_hybrid_configs.py

Mirrors `build_cost_data.py`: primary sources only, provenance travels with the
value, and the whole set is regenerable rather than hand-typed. A repo that has
gone gated (401) is reported and skipped rather than silently dropped -- Jamba
1.5/1.7 are gated, so the ungated `ai21labs/Jamba-v0.1` carries that family's
`attn_layer_period` / `attn_layer_offset` spelling.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "hybrid_configs"
MANIFEST = OUT_DIR / "MANIFEST.json"
RAW = "https://huggingface.co/{repo}/raw/main/config.json"

# Each entry names WHY it is in the set: the key shape it is the fixture for.
REPOS: dict[str, str] = {
    "nvidia/NVIDIA-Nemotron-Nano-9B-v2": "hybrid_override_pattern (Nemotron-H), Mamba-2 geometry",
    "ibm-granite/granite-4.0-h-small": "layer_types spelled mamba/attention, Mamba-2",
    "Qwen/Qwen3-Next-80B-A3B-Instruct": "full_attention_interval, gated DeltaNet",
    "Qwen/Qwen3.5-9B": "text_config wrapper + layer_types + mamba_ssm_dtype float32",
    "google/gemma-4-31B-it": "text_config wrapper, SWA not hybrid (negative case)",
    "moonshotai/Kimi-Linear-48B-A3B-Instruct": "linear_attn_config.full_attn_layers, KDA",
    "MiniMaxAI/MiniMax-Text-01": "attn_type_list with interleaved 0/1",
    "MiniMaxAI/MiniMax-M2": "attn_type_list that is all-1 (negative case)",
    "ai21labs/Jamba-v0.1": "attn_layer_period + attn_layer_offset, Mamba-1",
    "tiiuae/Falcon-H1-34B-Instruct": "PARALLEL hybrid: mamba keys, no pattern (must not shrink)",
    "Qwen/Qwen2.5-1.5B-Instruct": "dense GQA control: nothing here may change it",
}


def fetch(repo: str) -> dict | None:
    req = urllib.request.Request(
        RAW.format(repo=repo), headers={"User-Agent": "chimeraforge-fixture-capture"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        print(f"  SKIP {repo}: {exc}", file=sys.stderr)
        return None


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    captured_at = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    entries = []
    for repo, why in REPOS.items():
        config = fetch(repo)
        if config is None:
            continue
        name = repo.replace("/", "_") + ".json"
        (OUT_DIR / name).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        entries.append(
            {
                "repo": repo,
                "file": name,
                "source_url": RAW.format(repo=repo),
                "captured_at": captured_at,
                "covers": why,
            }
        )
        print(f"  OK   {repo} -> {name}")

    if len(entries) != len(REPOS):
        print(
            f"captured {len(entries)} of {len(REPOS)} repos; "
            "the manifest records only what was actually fetched",
            file=sys.stderr,
        )
    MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "captured_at": captured_at,
                "method": "HTTP GET of each repo's raw config.json on the Hugging Face Hub",
                "configs": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {MANIFEST}")
    return 0 if entries else 1


if __name__ == "__main__":
    raise SystemExit(main())
