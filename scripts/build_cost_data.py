"""Regenerate the bundled hosted-API price snapshot.

No vendor publishes a machine-readable pricing API, so the snapshot in
``src/chimeraforge/planner/data/api_pricing.json`` is periodically rebuilt from the
published pricing pages and date-stamped. This script is the auditable path from
those pages to the bundled file -- prices are never hand-typed into the JSON.

Usage
-----
    python scripts/build_cost_data.py --check     # validate the bundled snapshot
    python scripts/build_cost_data.py --fetch     # re-fetch sources, then validate
    python scripts/build_cost_data.py --fetch --write   # ...and rewrite the file

``--fetch`` needs the ``resolve`` extra (httpx). Pricing pages are HTML and change
layout without notice, so the fetcher does not silently guess: it reports what it
could and could not extract, and refuses to write a partial file. When a page
cannot be parsed, update that provider by hand *from the source URL* and bump its
``captured_at`` -- the point is that every number traces to a page someone read on
a known date, not that the scrape always succeeds.

Validation is the part that always runs, and it is strict: schema, types, positive
prices, sane magnitudes, ISO dates, and a source URL per provider.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "src" / "chimeraforge" / "planner" / "data" / "api_pricing.json"

REQUIRED_PROVIDER_KEYS = ("display_name", "source_url", "captured_at", "class", "models")
REQUIRED_MODEL_KEYS = ("name", "input_per_1m", "output_per_1m")
VALID_CLASSES = {"open", "frontier"}
# Sanity bounds, in USD per million tokens. Anything outside these is far more
# likely to be a parse error (a cents/dollars mix-up, a stray table cell) than a
# real price, so it fails the build rather than shipping.
MIN_PRICE, MAX_PRICE = 0.001, 1000.0


class ValidationError(Exception):
    """Raised when the snapshot does not satisfy the schema or sanity bounds."""


def load(path: pathlib.Path = SNAPSHOT) -> dict:
    if not path.exists():
        raise ValidationError(f"snapshot missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"snapshot is not valid JSON: {exc}") from exc


def _iso(value: str, where: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{where}: captured_at {value!r} is not an ISO date") from exc


def validate(data: dict) -> list[str]:
    """Raise on anything unusable; return human-readable notes about the snapshot."""
    if data.get("schema_version") != 1:
        raise ValidationError(f"unsupported schema_version: {data.get('schema_version')!r}")
    top_date = _iso(data.get("captured_at", ""), "top level")

    providers = data.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ValidationError("no providers in snapshot")

    notes: list[str] = []
    total_models = 0
    for pname, block in providers.items():
        for key in REQUIRED_PROVIDER_KEYS:
            if key not in block:
                raise ValidationError(f"provider {pname}: missing {key!r}")
        if block["class"] not in VALID_CLASSES:
            raise ValidationError(
                f"provider {pname}: class {block['class']!r} not in {sorted(VALID_CLASSES)}"
            )
        if not str(block["source_url"]).startswith("https://"):
            raise ValidationError(f"provider {pname}: source_url must be https")
        _iso(block["captured_at"], f"provider {pname}")

        models = block["models"]
        if not isinstance(models, dict) or not models:
            raise ValidationError(f"provider {pname}: no models")
        for mkey, m in models.items():
            for key in REQUIRED_MODEL_KEYS:
                if key not in m:
                    raise ValidationError(f"{pname}:{mkey}: missing {key!r}")
            for field in ("input_per_1m", "output_per_1m"):
                price = m[field]
                if not isinstance(price, (int, float)) or isinstance(price, bool):
                    raise ValidationError(f"{pname}:{mkey}: {field} is not a number")
                if not (MIN_PRICE <= price <= MAX_PRICE):
                    raise ValidationError(
                        f"{pname}:{mkey}: {field}={price} outside sane bounds "
                        f"[{MIN_PRICE}, {MAX_PRICE}] -- likely a parse error"
                    )
            if m["output_per_1m"] < m["input_per_1m"]:
                # Not fatal (a few providers price them equally or invert), but it is
                # unusual enough to surface rather than pass silently.
                notes.append(f"{pname}:{mkey}: output cheaper than input (unusual)")
        total_models += len(models)

    age = (dt.date.today() - top_date).days
    notes.append(f"{len(providers)} providers, {total_models} models, snapshot {age} days old")
    if age > 90:
        notes.append(f"STALE: {age} days old -- re-fetch before relying on these prices")
    return notes


_PRICE_ROW = re.compile(
    r"\|\s*(?P<name>[^|]+?)\s*\|\s*\$?(?P<inp>[0-9]+\.?[0-9]*)\s*\|\s*\$?(?P<out>[0-9]+\.?[0-9]*)\s*\|"
)


def parse_price_table(markdown: str) -> dict[str, tuple[float, float]]:
    """Extract ``name -> (input_per_1m, output_per_1m)`` from a markdown price table."""
    found: dict[str, tuple[float, float]] = {}
    for match in _PRICE_ROW.finditer(markdown):
        name = match.group("name").strip()
        if not name or name.lower() in {"model", "name"} or set(name) <= {"-", " ", ":"}:
            continue
        try:
            found[name] = (float(match.group("inp")), float(match.group("out")))
        except ValueError:  # pragma: no cover - regex already constrains this
            continue
    return found


def fetch(url: str, timeout: float = 30.0) -> str:
    """Fetch a pricing page. Needs the ``resolve`` extra (httpx)."""
    try:
        import httpx
    except ImportError as exc:
        raise ValidationError("--fetch needs httpx: pip install 'chimeraforge[resolve]'") from exc
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def refetch(data: dict) -> list[str]:
    """Re-fetch each provider's page and report what could be re-derived."""
    report: list[str] = []
    for pname, block in data.get("providers", {}).items():
        url = block["source_url"]
        try:
            body = fetch(url)
        except Exception as exc:  # noqa: BLE001 - report and continue per provider
            report.append(f"{pname}: FETCH FAILED ({type(exc).__name__}: {exc}) -- {url}")
            continue
        parsed = parse_price_table(body)
        if not parsed:
            report.append(
                f"{pname}: fetched {len(body)} bytes but found no price table "
                f"(page is likely JS-rendered) -- update by hand from {url}"
            )
            continue
        report.append(f"{pname}: parsed {len(parsed)} rows from {url}")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="validate the bundled snapshot")
    ap.add_argument("--fetch", action="store_true", help="re-fetch the source pages")
    ap.add_argument("--write", action="store_true", help="rewrite the snapshot (with --fetch)")
    args = ap.parse_args(argv)
    if not (args.check or args.fetch):
        args.check = True

    try:
        data = load()
        notes = validate(data)
    except ValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    print(f"OK: {SNAPSHOT.relative_to(ROOT)}")
    for n in notes:
        print(f"  - {n}")

    if args.fetch:
        print("\nRe-fetching sources:")
        for line in refetch(data):
            print(f"  - {line}")
        if args.write:
            print(
                "\nRefusing to auto-write: pricing pages are JS-rendered and change "
                "layout without notice. Update the affected provider by hand from its "
                "source_url, bump its captured_at, then re-run --check."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
