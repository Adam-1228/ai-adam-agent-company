from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
IMPORTER = ROOT / "scripts" / "import_commerce_handoff.py"
COMMERCE_HANDOFF_DIR = REPO_ROOT / "teams" / "commerce-agent-team" / "runtime" / "commerce_to_client_ops_handoffs"
RUNTIME_DIR = ROOT / "runtime" / "commerce_handoffs"
STATE_PATH = RUNTIME_DIR / "watch_state.json"
REPORTS = ROOT / "reports"
LATEST_REPORT = REPORTS / "latest_commerce_handoff_watch.md"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_state() -> dict:
    state = read_json(STATE_PATH, {"processed": {}})
    if not isinstance(state, dict):
        return {"processed": {}}
    if not isinstance(state.get("processed"), dict):
        state["processed"] = {}
    return state


def file_fingerprint(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}


def is_processed(state: dict, path: Path) -> bool:
    key = repo_relative(path)
    seen = state.get("processed", {}).get(key)
    return isinstance(seen, dict) and all(seen.get(k) == v for k, v in file_fingerprint(path).items())


def mark_processed(state: dict, path: Path, outcome: dict) -> None:
    key = repo_relative(path)
    state.setdefault("processed", {})[key] = {
        **file_fingerprint(path),
        "processed_at": now(),
        "qa_status": outcome.get("qa_status"),
        "returncode": outcome.get("returncode"),
    }


def discover(max_files: int) -> list[Path]:
    if not COMMERCE_HANDOFF_DIR.exists():
        return []
    paths = [p for p in COMMERCE_HANDOFF_DIR.glob("*.json") if p.is_file()]
    return sorted(paths, key=lambda p: p.stat().st_mtime)[:max_files]


def run_importer(path: Path, dry_run: bool) -> dict:
    command = [sys.executable, str(IMPORTER), str(path), "--json"]
    if dry_run:
        command.append("--dry-run")
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    payload: dict[str, Any]
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {
            "handoff_id": path.stem,
            "qa_status": "IMPORT_FATAL",
            "findings": [],
            "stdout_parse_error": True,
        }
    payload["returncode"] = completed.returncode
    payload["source_path"] = repo_relative(path)
    if completed.stderr.strip():
        payload["stderr_present"] = True
    return payload


def render_report(summary: dict) -> str:
    lines = [
        "# Commerce Handoff Watch Report",
        "",
        f"- Created: {summary['created_at']}",
        f"- Scanned: {summary['scanned']}",
        f"- Imported: {summary['imported']}",
        f"- Skipped: {summary['skipped']}",
        f"- Fatal: {summary['fatal']}",
        "",
        "| Source | Return | QA Status | Blocking | Warn |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in summary["results"]:
        lines.append(
            "| {source} | {returncode} | {qa_status} | {blocking} | {warn} |".format(
                source=item.get("source_path", ""),
                returncode=item.get("returncode", ""),
                qa_status=item.get("qa_status", ""),
                blocking=item.get("blocking_count", ""),
                warn=item.get("warn_count", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This watcher only passes files to the safe client-ops importer.",
            "- Importer decisions may be PASS, HOLD, or REJECT; REJECT is a QA outcome, not a watcher crash.",
            "- Runtime state and queues are gitignored under teams/client-ops-team/runtime/.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_once(max_files: int, dry_run: bool) -> dict:
    state = load_state()
    paths = discover(max_files)
    results = []
    skipped = 0
    fatal = 0
    imported = 0
    for path in paths:
        if is_processed(state, path):
            skipped += 1
            continue
        outcome = run_importer(path, dry_run=dry_run)
        results.append(outcome)
        if outcome.get("returncode") == 2 or outcome.get("qa_status") == "IMPORT_FATAL":
            fatal += 1
            continue
        imported += 1
        if not dry_run:
            mark_processed(state, path, outcome)

    if not dry_run:
        write_json(STATE_PATH, state)

    summary = {
        "created_at": now(),
        "scanned": len(paths),
        "imported": imported,
        "skipped": skipped,
        "fatal": fatal,
        "dry_run": dry_run,
        "results": results,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    LATEST_REPORT.write_text(render_report(summary), encoding="utf-8")
    return summary


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Watch commerce_to_client_ops handoffs and feed them to client-ops QA.")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit.")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between scans when not using --once.")
    parser.add_argument("--max-files", type=int, default=100, help="Maximum handoff files to scan per pass.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing importer output or watcher state.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    args = parser.parse_args()

    while True:
        summary = run_once(max_files=args.max_files, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(
                "Commerce handoff watch: "
                f"scanned={summary['scanned']} imported={summary['imported']} "
                f"skipped={summary['skipped']} fatal={summary['fatal']}"
            )
            print(f"Report: {LATEST_REPORT}")
        if args.once:
            return 1 if summary["fatal"] else 0
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
