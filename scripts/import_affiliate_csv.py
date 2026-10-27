#!/usr/bin/env python3
"""Convert a manually reviewed Shopee affiliate CSV into PR #3's feed contract.

Never infer affiliate eligibility, availability, timestamps or tracking links.
This script only preserves explicit assertions supplied by an authorized export.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

COLUMNS = ("id", "name", "market", "available", "affiliate_eligible",
           "affiliate_url", "source", "verified_at", "expires_at", "keywords",
           "benefit_zh", "commission_rate")

def convert(source: Path) -> dict:
    if not source.is_file():
        raise FileNotFoundError("No reviewed CSV supplied: " + str(source))
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV must contain column headers")
        missing = set(COLUMNS[:-1]) - set(reader.fieldnames)
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
        products = []
        for row_number, row in enumerate(reader, start=2):
            if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                continue
            if any(v is None for v in row.values()):
                raise ValueError(f"Row {row_number}: malformed CSV")
            p = {k: (row.get(k) or "").strip() for k in COLUMNS}
            for k in ("available", "affiliate_eligible"):
                if p[k].lower() not in ("true", "false"):
                    raise ValueError(f"Row {row_number}: {k} must be true or false, never assumed")
                p[k] = p[k].lower() == "true"
            p["keywords"] = [x.strip() for x in p["keywords"].split("|") if x.strip()]
            if p["commission_rate"]:
                p["commission_rate"] = float(p["commission_rate"])
            else:
                del p["commission_rate"]
            # Validate using the same selector contract as the production ad engine.
            # Invalid/expired offers remain in the output for audit but cannot be selected.
            products.append(p)
    if not products:
        raise ValueError("CSV has no reviewed products")
    return {"products": products}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    feed = convert(args.csv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Converted {len(feed['products'])} reviewed rows; eligibility still checked at selection time.")

if __name__ == "__main__":
    main()
