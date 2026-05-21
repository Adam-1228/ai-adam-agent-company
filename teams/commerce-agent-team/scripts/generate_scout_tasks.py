from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "seed_keywords.csv"
TASK_PATH = ROOT / "workforce" / "tasks" / "generated_scout_tasks.md"


def generate(limit: int) -> str:
    with SEED_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))[:limit]

    lines = [
        "# Generated Scout Tasks",
        "",
        f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    for index, row in enumerate(rows, start=1):
        keyword = row.get("keyword", "").strip()
        target_market = row.get("target_market", "coupang").strip()
        category = row.get("category", "uncategorized").strip()
        notes = row.get("notes", "").strip()
        lines.extend(
            [
                f"## TASK-SCOUT-{index:03d}: {keyword}",
                "",
                "- Assignee: 01_market_scout",
                "- Priority: P2",
                f"- Target market: {target_market}",
                f"- Category: {category}",
                f"- Notes: {notes}",
                "- Output: 5 to 10 candidate products with source URL, estimated price, competition, reviews, and risk notes.",
                "- Handoff: 02_margin_analyst",
                "",
            ]
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate repeatable scout tasks from seed keywords.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum seed keywords to convert into tasks")
    args = parser.parse_args()

    TASK_PATH.parent.mkdir(parents=True, exist_ok=True)
    TASK_PATH.write_text(generate(args.limit), encoding="utf-8")
    print(f"Generated: {TASK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
