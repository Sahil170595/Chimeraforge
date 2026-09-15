"""Capture the two external ground truths the quality gate is tested against.

P8.4. Both are primary sources, fetched with a URL and a date, because both exist
to check the bundled corpus against something that is not the bundled corpus.

1. **A real `lm-evaluation-harness` results file.** The reader in
   `planner/qualityfile.py` parses `results -> task -> "metric,filter"` pairs,
   and the case worth pinning is that `"..._stderr,none"` is legitimately the
   **string** `"N/A"` when a metric's stderr cannot be computed. A hand-written
   fixture would encode my belief about the schema rather than the schema.

2. **llama.cpp's published perplexity / KL-divergence table for Llama-3-8B.**
   Every k-quant delta there is strictly positive and monotone in bit width, and
   no quant beats FP16. It is a *different metric* from the bundled composite, so
   it can **falsify** the corpus's ordering -- and it does -- but it may never
   supply a composite score. The correct consequence of the contradiction is that
   the offending cells stop claiming a difference, not that they get repopulated
   from llama.cpp.

Re-run to refresh:

    python scripts/fetch_quality_fixtures.py
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import sys
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "quality"
MANIFEST = OUT_DIR / "MANIFEST.json"

# A real lm-eval run, chosen because it exercises the awkward parts of the
# schema: several tasks, `n-samples` with original/effective, and two metrics
# whose stderr came back as the string "N/A".
LM_EVAL_URL = (
    "https://raw.githubusercontent.com/pfnet-research/japanese-lm-fin-harness/"
    "main/models/openai/gpt-4o-2024-08-06/result-default.json"
)
LLAMACPP_URL = (
    "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/perplexity/README.md"
)

# The scoreboard row shape: | quant | imatrix | size | PPL | dPPL | KLD | ... |
_ROW = re.compile(
    # The k-quant rows spell the K in upper case (q4_K_M), and they are exactly
    # the ones the planner ladders over -- a lower-case-only class silently
    # captured 6 legacy rows and dropped every k-quant.
    r"^\|\s*(?P<quant>[A-Za-z0-9_]+)\s*\|\s*(?P<imatrix>[^|]*?)\s*\|\s*(?P<size>[\d.]+)\s*\|"
    r"\s*(?P<ppl>[\d.]+)\s*(?:±|\+/-)\s*(?P<ppl_err>[\d.]+)\s*\|"
    r"\s*(?P<dppl>-?[\d.]+)\s*(?:±|\+/-)\s*(?P<dppl_err>[\d.]+)\s*\|",
    re.M,
)


def fetch(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "chimeraforge-fixture-capture"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        print(f"  SKIP {url}: {exc}", file=sys.stderr)
        return None


def parse_llamacpp(markdown: str) -> list[dict]:
    """The Llama-3-8B scoreboard, without its imatrix variants.

    Only the `None` imatrix rows are kept: an importance-matrix quant is a
    different artifact from the plain one, and mixing the two would put two
    different things under one bit width.
    """
    rows: list[dict] = []
    for m in _ROW.finditer(markdown):
        if m.group("imatrix").strip() != "None":
            continue
        rows.append(
            {
                "quant": m.group("quant"),
                "size_gib": float(m.group("size")),
                "ppl": float(m.group("ppl")),
                "ppl_err": float(m.group("ppl_err")),
                "delta_ppl": float(m.group("dppl")),
                "delta_ppl_err": float(m.group("dppl_err")),
            }
        )
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    captured_at = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    entries = []

    body = fetch(LM_EVAL_URL)
    if body:
        (OUT_DIR / "lm_eval_results.json").write_text(body, encoding="utf-8")
        entries.append(
            {
                "file": "lm_eval_results.json",
                "source_url": LM_EVAL_URL,
                "captured_at": captured_at,
                "covers": (
                    "lm-evaluation-harness results schema, verbatim: "
                    "`results -> task -> 'metric,filter'`, `n-samples` with "
                    "original/effective, and stderr values that are the string 'N/A'"
                ),
            }
        )
        print("  OK   lm-eval results")

    md = fetch(LLAMACPP_URL)
    if md:
        rows = parse_llamacpp(md)
        if not rows:
            print("  SKIP llama.cpp: scoreboard table did not parse", file=sys.stderr)
        else:
            (OUT_DIR / "llamacpp_ppl_llama3_8b.json").write_text(
                json.dumps(
                    {
                        "model": "Llama-3-8B",
                        "corpus": "Wikitext-2 test set",
                        "metric": "perplexity and KL divergence vs FP16",
                        "note": (
                            "A DIFFERENT metric from the bundled composite. It can "
                            "falsify an ordering; it can never supply a composite score."
                        ),
                        "source_url": LLAMACPP_URL,
                        "captured_at": captured_at,
                        "rows": rows,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            entries.append(
                {
                    "file": "llamacpp_ppl_llama3_8b.json",
                    "source_url": LLAMACPP_URL,
                    "captured_at": captured_at,
                    "covers": (
                        f"{len(rows)} non-imatrix rows: monotone in bit width, no quant above FP16"
                    ),
                }
            )
            print(f"  OK   llama.cpp scoreboard ({len(rows)} rows)")

    if not entries:
        return 1
    MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "captured_at": captured_at,
                "method": "HTTP GET of each source's raw file",
                "fixtures": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
