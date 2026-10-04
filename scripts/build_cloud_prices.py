"""Build and validate the bundled hyperscaler on-demand GPU price snapshot.

The planner prices datacenter GPUs at a marketplace rate, which runs roughly 4-5x
below what AWS or Azure bill on demand for the same part. Both clouds publish
machine-readable list prices without credentials, so this reads them -- a dated
snapshot, never a live quote in a plan -- and records, per offer, where every
fact came from:

- **Price:** AWS Price List bulk CSV (EC2, us-east-1) and the Azure Retail Prices
  API (eastus). Linux, on-demand, shared tenancy; no spot, low-priority, capacity
  blocks, reservations or Windows.
- **GPU count and memory:** AWS's own price list columns; for Azure, the
  "Accelerators" table on each VM series page on learn.microsoft.com.
- **GPU model:** the instance family's or VM series' vendor page, which must name
  the part. The count and per-GPU memory are then checked against the hardware DB,
  and an offer whose memory does not match the DB entry is an error, not a guess.

Variants that are a different card from the DB entry are excluded with a reason
(Azure's NCads H100 v5 is an H100 NVL 94GB; NC A100 v4 is an A100 PCIe, while the
DB's A100 80GB is the SXM part at 2039 GB/s). Fractional-GPU sizes are excluded:
a vGPU slice is not the card the planner sizes.

Usage
-----
    python scripts/build_cloud_prices.py --write
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import io
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATASET = ROOT / "src" / "chimeraforge" / "planner" / "data" / "cloud_prices.json"
HARDWARE = ROOT / "src" / "chimeraforge" / "planner" / "data" / "hardware.json"

SCHEMA_VERSION = 1
FETCH_TIMEOUT_S = 300
AWS_REGION = "us-east-1"
AZURE_REGION = "eastus"
AWS_CSV = (
    "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/"
    f"{AWS_REGION}/index.csv"
)
AWS_DOC = "https://aws.amazon.com/ec2/instance-types/{page}/"
AZURE_API = "https://prices.azure.com/api/retail/prices"
AZURE_DOC = "https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/{page}"
# Per-GPU memory must match the hardware DB within this fraction (B200 is sold as
# "180GB" and listed by AWS as 1432 GB per 8, i.e. 179).
MEMORY_TOLERANCE = 0.06
USER_AGENT = "Mozilla/5.0 (chimeraforge build_cloud_prices)"

# Instance family -> DB GPU, and the page that names the part.
AWS_FAMILIES = (
    ("p4d", "A100 40GB", "p4", "NVIDIA A100"),
    ("p4de", "A100 80GB", "p4", "NVIDIA A100"),
    ("p5", "H100 80GB", "p5", "NVIDIA H100"),
    ("p6-b200", "B200 180GB", "p6", "B200"),
    ("g6", "L4 24GB", "g6", "NVIDIA L4"),
    ("g4dn", "T4 16GB", "g4", "NVIDIA T4"),
)
# Azure VM series page -> DB GPU, and the phrase the page must contain.
AZURE_SERIES = (
    ("ndasra100v4-series", "A100 40GB", "A100 40GB"),
    ("ndma100v4-series", "A100 80GB", "A100 80GB"),
    ("ndh100v5-series", "H100 80GB", "NVIDIA H100"),
    ("nd-h200-v5-series", "H200 141GB", "H200"),
    ("ndmi300xv5-series", "MI300X 192GB", "MI300X"),
    ("ncast4v3-series", "T4 16GB", "T4"),
    ("nc-rtxpro6000-bse-v6-series", "RTX PRO 6000 Blackwell Server 96GB", "RTX PRO 6000"),
)
EXCLUDED = {
    "azure:ncadsh100v5-series": "H100 NVL 94GB, a different card from the DB's H100 80GB (SXM)",
    "azure:nca100v4-series": (
        "A100 PCIe, a different card from the DB's A100 80GB (SXM, 2039 GB/s, 400 W)"
    ),
    "aws:p5e/p5en": "on-demand not listed in us-east-1 (capacity blocks only)",
    "aws:g5": "A10G, not in the hardware DB",
    "aws:g6e": "L40S, not in the hardware DB",
}


class BuildError(RuntimeError):
    """The snapshot cannot be built or does not validate."""


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        return resp.read()


def _page_text(url: str) -> tuple[str, str]:
    raw = _get(url).decode("utf-8", "replace")
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)))
    return raw, text


def _db_vram() -> dict[str, float]:
    data = json.loads(HARDWARE.read_text(encoding="utf-8"))
    return {g["name"]: float(g["vram_gb"]) for g in data["gpus"]}


def _check_memory(where: str, gpu: str, per_gpu_gb: float, vram: dict[str, float]) -> None:
    want = vram.get(gpu)
    if want is None:
        raise BuildError(f"{where}: {gpu!r} is not in the hardware DB")
    if abs(per_gpu_gb - want) / want > MEMORY_TOLERANCE:
        raise BuildError(f"{where}: {per_gpu_gb:g} GB per GPU, but {gpu} is {want:g} GB")


def aws_offers(vram: dict[str, float]) -> tuple[list[dict], str]:
    """Stream the EC2 bulk CSV (~300 MB, never written to disk) for the families."""
    docs: dict[str, str] = {}
    for family, gpu, page, phrase in AWS_FAMILIES:
        url = AWS_DOC.format(page=page)
        if page not in docs:
            docs[page] = _page_text(url)[1]
        if phrase not in docs[page]:
            raise BuildError(f"aws {family}: {url} does not name {phrase!r}")
    req = urllib.request.Request(AWS_CSV, headers={"User-Agent": USER_AGENT})
    offers, published = [], ""
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        stream = io.TextIOWrapper(resp, encoding="utf-8")
        for _ in range(5):  # FormatVersion, Disclaimer, Publication Date, Version, OfferCode
            meta = next(csv.reader([stream.readline()]))
            if meta and meta[0] == "Publication Date":
                published = meta[1]
        for row in csv.DictReader(stream):
            if (
                row["TermType"] != "OnDemand"
                or row["MarketOption"] != "OnDemand"
                or row["Operating System"] != "Linux"
                or row["Tenancy"] != "Shared"
                or row["Pre Installed S/W"] != "NA"
                or row["CapacityStatus"] != "Used"
                or row["Unit"] != "Hrs"
            ):
                continue
            instance = row["Instance Type"]
            for family, gpu, page, _phrase in AWS_FAMILIES:
                if not instance.startswith(family + "."):
                    continue
                gpus = int(row["GPU"])
                total_gb = float(re.match(r"[\d.]+", row["GPU Memory"]).group(0))
                _check_memory(f"aws {instance}", gpu, total_gb / gpus, vram)
                price = float(row["PricePerUnit"])
                if price <= 0 or row["Currency"] != "USD":
                    raise BuildError(f"aws {instance}: price {price} {row['Currency']}")
                offers.append(
                    {
                        "cloud": "aws",
                        "instance": instance,
                        "gpu": gpu,
                        "gpus": gpus,
                        "gpu_memory_gb": round(total_gb / gpus, 1),
                        "price_per_hour": round(price, 6),
                        "region": AWS_REGION,
                        "price_source": AWS_CSV,
                        "spec_source": AWS_DOC.format(page=page),
                    }
                )
    return sorted(offers, key=lambda o: (o["gpu"], o["instance"])), published[:10]


def _azure_sizes(raw: str) -> list[tuple[str, str, str]]:
    """(size, accelerator qty, accelerator memory) rows from a series page."""
    rows = []
    for table in re.findall(r"<table.*?</table>", raw, re.S):
        cells = [
            [
                html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)
            ]
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)
        ]
        if cells and len(cells[0]) > 2 and cells[0][1].startswith("Accelerators"):
            rows += [(c[0], c[1], c[2]) for c in cells[1:] if len(c) >= 3]
    return rows


def _azure_price(sku: str) -> dict | None:
    flt = (
        f"serviceName eq 'Virtual Machines' and armSkuName eq '{sku}' and "
        f"armRegionName eq '{AZURE_REGION}' and priceType eq 'Consumption'"
    )
    items = json.loads(_get(f"{AZURE_API}?{urllib.parse.urlencode({'$filter': flt})}"))["Items"]
    linux = [
        i
        for i in items
        if "Windows" not in i["productName"]
        and not any(w in i["skuName"] for w in ("Spot", "Low Priority"))
        and i["unitOfMeasure"] == "1 Hour"
        and i["currencyCode"] == "USD"
    ]
    return min(linux, key=lambda i: i["retailPrice"]) if linux else None


def azure_offers(vram: dict[str, float]) -> tuple[list[dict], list[str]]:
    offers, skipped = [], []
    for page, gpu, phrase in AZURE_SERIES:
        url = AZURE_DOC.format(page=page)
        raw, text = _page_text(url)
        if phrase not in text:
            raise BuildError(f"azure {page}: {url} does not name {phrase!r}")
        sizes = _azure_sizes(raw)
        if not sizes:
            raise BuildError(f"azure {page}: no Accelerators table at {url}")
        for size, qty, mem in sizes:
            if not qty.isdigit():
                skipped.append(f"{size}: {qty} of a GPU (vGPU slice)")
                continue
            gpus = int(qty)
            mem_gb = float(mem.replace(",", ""))
            # Most series pages give total accelerator memory; NDm A100 v4 gives it per GPU.
            per_gpu = mem_gb / gpus
            if abs(per_gpu - vram.get(gpu, 0)) / max(vram.get(gpu, 1), 1) > MEMORY_TOLERANCE:
                per_gpu = mem_gb
            _check_memory(f"azure {size}", gpu, per_gpu, vram)
            item = _azure_price(size)
            if item is None:
                skipped.append(f"{size}: no Linux on-demand price in {AZURE_REGION}")
                continue
            offers.append(
                {
                    "cloud": "azure",
                    "instance": size,
                    "gpu": gpu,
                    "gpus": gpus,
                    "gpu_memory_gb": round(per_gpu, 1),
                    "price_per_hour": round(float(item["retailPrice"]), 6),
                    "region": AZURE_REGION,
                    "price_source": f"{AZURE_API} (armSkuName {size})",
                    "price_effective": item["effectiveStartDate"][:10],
                    "spec_source": url,
                }
            )
    return sorted(offers, key=lambda o: (o["gpu"], o["instance"])), skipped


def validate(data: dict) -> None:
    offers = data.get("offers") or []
    have = {(o["cloud"], o["gpu"]) for o in offers}
    for anchor in (("aws", "H100 80GB"), ("azure", "H100 80GB"), ("aws", "L4 24GB")):
        if anchor not in have:
            raise BuildError(f"anchor offer missing: {anchor}")
    for o in offers:
        if o["gpus"] < 1 or o["price_per_hour"] <= 0:
            raise BuildError(f"bad offer {o['instance']}")
        for key in ("price_source", "spec_source", "region"):
            if not o.get(key):
                raise BuildError(f"{o['instance']}: {key} missing")
    if not data.get("captured_at"):
        raise BuildError("captured_at missing")
    json.dumps(data).encode("ascii")


def build(today: dt.date) -> dict:
    vram = _db_vram()
    aws, published = aws_offers(vram)
    azure, skipped = azure_offers(vram)
    data = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": today.isoformat(),
        "note": (
            "Hyperscaler on-demand list prices (Linux, shared tenancy, no spot or "
            "reservations) for GPUs in the hardware DB. A dated snapshot, never a live "
            "quote; regenerate with scripts/build_cloud_prices.py."
        ),
        "sources": {
            "aws": {"region": AWS_REGION, "price_list": AWS_CSV, "published": published},
            "azure": {"region": AZURE_REGION, "price_api": AZURE_API},
        },
        "excluded": {
            **EXCLUDED,
            **{f"azure:{s.split(':')[0]}": s.split(": ", 1)[1] for s in skipped},
        },
        "offers": aws + azure,
    }
    validate(data)
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--write", action="store_true", help="regenerate the bundled snapshot")
    args = ap.parse_args()
    if not args.write:
        ap.error("pass --write (prices move, so there is no byte-identical --check)")
    data = build(dt.date.today())
    DATASET.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
    by_cloud = {c: sum(o["cloud"] == c for o in data["offers"]) for c in ("aws", "azure")}
    print(f"wrote {DATASET.name}: {by_cloud}, {len(data['excluded'])} exclusions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
