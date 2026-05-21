from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFORCE = ROOT / "workforce"
RUNS = WORKFORCE / "runs"
AGENTS = WORKFORCE / "agents"


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def remove_path(path: Path, dry_run: bool) -> None:
    if not is_under(path, ROOT):
        raise RuntimeError(f"Refusing to remove outside project root: {path}")
    if dry_run:
        print(f"would remove {path}")
        return
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
    print(f"removed {path}")


def list_run_dirs() -> list[Path]:
    if not RUNS.exists():
        return []
    return sorted([p for p in RUNS.iterdir() if p.is_dir() and p.name.startswith("RUN-")], reverse=True)


def cleanup_runs(keep: int, dry_run: bool) -> int:
    run_dirs = list_run_dirs()
    keep_names = {p.name for p in run_dirs[:keep]}
    removed = 0

    for run_dir in run_dirs[keep:]:
        remove_path(run_dir, dry_run)
        removed += 1

    if AGENTS.exists():
        for outbox in AGENTS.glob("*/outbox"):
            if not outbox.is_dir():
                continue
            for artifact in outbox.glob("RUN-*.md"):
                run_name = artifact.stem
                if run_name not in keep_names:
                    remove_path(artifact, dry_run)
                    removed += 1

    print(f"kept runs: {min(len(run_dirs), keep)}")
    print(f"removed items: {removed}")
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove old commerce agent run artifacts.")
    parser.add_argument("--keep", type=int, default=30, help="Number of latest runs to keep. Default: 30")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be removed without deleting")
    args = parser.parse_args()

    if args.keep < 1:
        raise SystemExit("--keep must be at least 1")
    cleanup_runs(args.keep, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
