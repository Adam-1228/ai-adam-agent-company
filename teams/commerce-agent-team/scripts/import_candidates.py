from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "product_candidates.csv"

FIELDS = [
    "id",
    "product_name",
    "source_market",
    "target_market",
    "category",
    "source_price_krw",
    "target_price_krw",
    "shipping_cost_krw",
    "platform_fee_rate",
    "estimated_monthly_demand",
    "competitor_count",
    "review_count",
    "avg_rating",
    "negative_review_rate",
    "return_risk",
    "certification_risk",
    "brand_ip_risk",
    "image_rights_risk",
    "notes",
    "source_url",
]

DEFAULTS = {
    "source_market": "unknown",
    "target_market": "coupang",
    "category": "uncategorized",
    "source_price_krw": "0",
    "target_price_krw": "0",
    "shipping_cost_krw": "0",
    "platform_fee_rate": "0.108",
    "estimated_monthly_demand": "0",
    "competitor_count": "999",
    "review_count": "0",
    "avg_rating": "0",
    "negative_review_rate": "0",
    "return_risk": "3",
    "certification_risk": "3",
    "brand_ip_risk": "3",
    "image_rights_risk": "3",
    "notes": "",
    "source_url": "",
}


def read_existing() -> list[dict[str, str]]:
    if not DATA_PATH.exists():
        return []
    with DATA_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def next_id(existing: list[dict[str, str]], prefix: str) -> str:
    max_num = 0
    for row in existing:
        value = row.get("id", "")
        if value.startswith(prefix):
            try:
                max_num = max(max_num, int(value[len(prefix) :]))
            except ValueError:
                continue
    return f"{prefix}{max_num + 1:03d}"


def normalize_row(row: dict[str, str], existing: list[dict[str, str]], prefix: str) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for field in FIELDS:
        value = (row.get(field) or DEFAULTS.get(field) or "").strip()
        normalized[field] = value

    if not normalized["id"]:
        normalized["id"] = next_id(existing, prefix)
        existing.append({"id": normalized["id"]})

    if not normalized["product_name"]:
        raise ValueError("product_name is required for every imported row")

    return normalized


def import_file(source: Path, prefix: str, dry_run: bool) -> tuple[int, int]:
    if not source.exists():
        raise FileNotFoundError(source)

    existing = read_existing()
    existing_ids = {row.get("id", "") for row in existing}

    with source.open("r", encoding="utf-8-sig", newline="") as f:
        incoming = list(csv.DictReader(f))

    imported: list[dict[str, str]] = []
    skipped = 0
    scratch_existing = list(existing)

    for row in incoming:
        normalized = normalize_row(row, scratch_existing, prefix)
        if normalized["id"] in existing_ids:
            skipped += 1
            continue
        imported.append(normalized)
        existing_ids.add(normalized["id"])

    if dry_run:
        return len(imported), skipped

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not DATA_PATH.exists() or DATA_PATH.stat().st_size == 0
    with DATA_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(imported)

    return len(imported), skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Import product candidate CSV files into the shared candidate database.")
    parser.add_argument("source_csv", help="CSV file to import, usually under data/manual_inbox/")
    parser.add_argument("--prefix", default="M", help="ID prefix for rows without an id. Default: M")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count rows without changing product_candidates.csv")
    args = parser.parse_args()

    imported, skipped = import_file(Path(args.source_csv), args.prefix, args.dry_run)
    mode = "would import" if args.dry_run else "imported"
    print(f"{mode}: {imported}")
    print(f"skipped existing ids: {skipped}")
    print(f"target: {DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
