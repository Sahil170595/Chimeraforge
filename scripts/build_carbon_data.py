"""Build and validate the bundled grid carbon-intensity snapshot.

The planner reports energy (kWh, $) but not emissions. Emissions per token are
that energy times the carbon intensity of the grid it is drawn from, which is a
property of the region, not the model -- so it comes from a dataset, pinned and
date-stamped here, never from memory.

Source
------
Our World in Data ``energy-data``, column ``carbon_intensity_elec``: lifecycle
greenhouse-gas emissions per kWh of electricity generated, in gCO2e/kWh. OWID's
codebook attributes the column to Ember's Yearly Electricity Data. OWID data is
CC BY 4.0; Ember releases its content under CC-BY-4.0. Both require attribution,
which the snapshot carries and the planner prints.

The CSV is read at a pinned commit so a rebuild is byte-for-byte reproducible;
pass ``--commit`` to move the pin forward.

Usage
-----
    python scripts/build_carbon_data.py --write              # at the pinned commit
    python scripts/build_carbon_data.py --write --commit SHA # move the pin
    python scripts/build_carbon_data.py --check              # bundled == rebuild

Method
------
For each ISO-3166 alpha-3 country, the latest year with a value. OWID's aggregate
rows (``OWID_*`` codes, and rows without a code) are excluded: a continent is not
a grid. The year travels with each value, because coverage is uneven -- the
newest year has far fewer countries than the one before it.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATASET = ROOT / "src" / "chimeraforge" / "planner" / "data" / "carbon_intensity.json"

SCHEMA_VERSION = 1
REPO = "owid/energy-data"
# Pinned OWID energy-data commit (2026-04-27). Move with --commit.
DEFAULT_COMMIT = "7e387a16f70a510e433f8aac7efeac6faa1e5059"
CSV_NAME = "owid-energy-data.csv"
CODEBOOK_NAME = "owid-energy-codebook.csv"
COLUMN = "carbon_intensity_elec"
RAW_URL = "https://raw.githubusercontent.com/{repo}/{commit}/{name}"
BLOB_URL = "https://github.com/{repo}/blob/{commit}/{name}"
COMMIT_API = "https://api.github.com/repos/{repo}/commits/{commit}"
LICENSE = "CC BY 4.0 (Our World in Data); Ember content CC-BY-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
FETCH_TIMEOUT_S = 60

ISO3 = re.compile(r"^[A-Z]{3}$")
# Validation bounds. The dirtiest real grids sit near 1000 gCO2e/kWh (lignite and
# oil); anything past this is a unit or parsing error, not a grid.
MAX_GCO2E_PER_KWH = 1500.0
MIN_YEAR = 2000
# Coverage floor: the source carries ~200 countries; far fewer means a broken read.
MIN_REGIONS = 150
# Grids that must be present, so a silently truncated read fails here.
ANCHORS = ("USA", "CHN", "IND", "DEU", "FRA", "GBR", "JPN", "BRA")


class BuildError(RuntimeError):
    """The snapshot cannot be built or does not validate."""


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "chimeraforge-build"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        return resp.read()


def _ascii(text: str) -> str:
    """The repo is ASCII-only; the codebook writes CO2 with a subscript two."""
    return text.replace("₂", "2").encode("ascii", "replace").decode("ascii")


ZERO_EXCLUSION = (
    "source reports 0 gCO2e/kWh; a lifecycle intensity is never zero (every "
    "generator has construction and supply-chain emissions), so the value is not the "
    "quantity the column defines -- plan with --carbon-intensity instead"
)


def split_excluded(regions: dict[str, dict]) -> tuple[dict[str, dict], dict[str, str]]:
    """Drop values that cannot be the stated quantity, recording why."""
    kept, excluded = {}, {}
    for iso, r in regions.items():
        if r["gco2e_per_kwh"] <= 0:
            excluded[iso] = f"{r['name']} ({r['year']}): {ZERO_EXCLUSION}"
        else:
            kept[iso] = r
    return kept, excluded


def parse_regions(csv_text: str) -> dict[str, dict]:
    """Latest non-empty ``carbon_intensity_elec`` per ISO-3 country."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or COLUMN not in reader.fieldnames:
        raise BuildError(f"column {COLUMN!r} missing from the CSV")
    regions: dict[str, dict] = {}
    for row in reader:
        iso = (row.get("iso_code") or "").strip()
        raw = (row.get(COLUMN) or "").strip()
        if not ISO3.match(iso) or not raw:
            continue
        year = int(row["year"])
        if iso in regions and regions[iso]["year"] >= year:
            continue
        regions[iso] = {
            "name": _ascii(row["country"].strip()),
            "year": year,
            "gco2e_per_kwh": round(float(raw), 3),
        }
    return dict(sorted(regions.items()))


def parse_definition(codebook_text: str) -> dict[str, str]:
    """The codebook row for the column: description, unit and upstream source."""
    for row in csv.DictReader(io.StringIO(codebook_text)):
        if row.get("column") == COLUMN:
            return {
                "title": _ascii(row["title"]),
                "description": _ascii(row["description"]),
                "unit": _ascii(row["unit"]),
                "upstream": _ascii(row["source"]),
            }
    raise BuildError(f"{COLUMN!r} not in the codebook")


def validate(data: dict, today: dt.date) -> None:
    """Fail loudly on anything a planner number could not stand behind."""
    regions = data.get("regions") or {}
    if len(regions) < MIN_REGIONS:
        raise BuildError(f"only {len(regions)} regions (< {MIN_REGIONS}); a broken read?")
    missing = [a for a in ANCHORS if a not in regions]
    if missing:
        raise BuildError(f"anchor grids missing: {missing}")
    for iso, r in regions.items():
        if not ISO3.match(iso):
            raise BuildError(f"{iso!r} is not an ISO-3 code")
        if not r.get("name"):
            raise BuildError(f"{iso}: no name")
        if not isinstance(r.get("year"), int) or not MIN_YEAR <= r["year"] <= today.year:
            raise BuildError(f"{iso}: year {r.get('year')!r} out of range")
        v = r.get("gco2e_per_kwh")
        if not isinstance(v, (int, float)) or not 0 < v <= MAX_GCO2E_PER_KWH:
            raise BuildError(f"{iso}: {v!r} gCO2e/kWh out of range")
    src = data.get("source") or {}
    for key in ("url", "commit", "commit_date", "license", "attribution", "unit"):
        if not src.get(key):
            raise BuildError(f"source.{key} missing")
    if "kilowatt-hour" not in src["unit"]:
        raise BuildError(f"unexpected unit {src['unit']!r}")
    json.dumps(data).encode("ascii")  # raises on non-ASCII


def build(commit: str, today: dt.date) -> dict:
    csv_text = _fetch(RAW_URL.format(repo=REPO, commit=commit, name=CSV_NAME)).decode("utf-8")
    codebook = _fetch(RAW_URL.format(repo=REPO, commit=commit, name=CODEBOOK_NAME)).decode("utf-8")
    meta = json.loads(_fetch(COMMIT_API.format(repo=REPO, commit=commit)))
    definition = parse_definition(codebook)
    regions, excluded = split_excluded(parse_regions(csv_text))
    newest = max(r["year"] for r in regions.values())
    data = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": today.isoformat(),
        "source": {
            "dataset": f"Our World in Data energy-data, column {COLUMN}",
            "url": BLOB_URL.format(repo=REPO, commit=meta["sha"], name=CSV_NAME),
            "commit": meta["sha"],
            "commit_date": meta["commit"]["committer"]["date"][:10],
            "title": definition["title"],
            "definition": definition["description"],
            "unit": definition["unit"],
            "upstream": definition["upstream"],
            "attribution": (
                "Ember - Yearly Electricity Data; processed by Our World in Data "
                "(energy-data). " + definition["upstream"]
            ),
            "license": LICENSE,
            "license_url": LICENSE_URL,
            "method": (
                "Latest year with a value per ISO-3166 alpha-3 country; OWID aggregate "
                "regions excluded. Annual-average, location-based, lifecycle intensity "
                "of generation."
            ),
            "newest_year": newest,
        },
        "regions": regions,
        "excluded": excluded,
    }
    validate(data, today)
    return data


def _text(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the bundled file differs")
    ap.add_argument("--write", action="store_true", help="regenerate the bundled file")
    ap.add_argument("--commit", default=None, help=f"OWID commit (default {DEFAULT_COMMIT[:7]})")
    args = ap.parse_args()
    if args.check == args.write:
        ap.error("pass exactly one of --check / --write")
    today = dt.date.today()
    if args.check:
        bundled = json.loads(DATASET.read_text(encoding="utf-8"))
        rebuilt = build(args.commit or bundled["source"]["commit"], today)
        # captured_at is the day of the read, not part of the data.
        rebuilt["captured_at"] = bundled["captured_at"]
        if rebuilt != bundled:
            print(f"{DATASET.name} differs from a rebuild; run --write", file=sys.stderr)
            return 1
        print(f"{DATASET.name} matches a rebuild at {rebuilt['source']['commit'][:7]}")
        return 0
    data = build(args.commit or DEFAULT_COMMIT, today)
    DATASET.write_text(_text(data), encoding="ascii")
    src = data["source"]
    print(
        f"wrote {DATASET.name}: {len(data['regions'])} regions, newest year "
        f"{src['newest_year']}, OWID {src['commit'][:7]} ({src['commit_date']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
