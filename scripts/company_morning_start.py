from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMERCE_ROOT = REPO_ROOT / "teams" / "commerce-agent-team"
CLIENT_OPS_ROOT = REPO_ROOT / "teams" / "client-ops-team"
RUNTIME_DIR = COMMERCE_ROOT / "runtime" / "company_morning"
LATEST_SUMMARY = RUNTIME_DIR / "latest.json"


@dataclass
class StepResult:
    name: str
    command: list[str]
    cwd: str
    started_at: str
    finished_at: str
    returncode: int
    stdout_tail: str
    stderr_tail: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def tail(text: str, max_chars: int = 4000) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def preferred_python(project_root: Path) -> str:
    candidates = []
    if os.name == "nt":
        candidates.append(project_root / ".venv" / "Scripts" / "python.exe")
    else:
        candidates.append(project_root / ".venv" / "bin" / "python")
    candidates.append(Path(sys.executable))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run_step(name: str, command: list[str], cwd: Path, timeout: int) -> StepResult:
    started_at = datetime.now().isoformat(timespec="seconds")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"\n=== {name} ===")
    print("cwd:", cwd)
    print("cmd:", " ".join(command))

    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    finished_at = datetime.now().isoformat(timespec="seconds")

    if completed.stdout:
        print(completed.stdout[-2000:])
    if completed.stderr:
        print(completed.stderr[-2000:], file=sys.stderr)
    print(f"returncode: {completed.returncode}")

    return StepResult(
        name=name,
        command=command,
        cwd=str(cwd),
        started_at=started_at,
        finished_at=finished_at,
        returncode=completed.returncode,
        stdout_tail=tail(completed.stdout),
        stderr_tail=tail(completed.stderr),
    )


def write_summary(results: list[StepResult], *, started_at: str, mode: str) -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    finished_at = datetime.now().isoformat(timespec="seconds")
    payload = {
        "mode": mode,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": "ok" if all(result.ok for result in results) else "failed",
        "steps": [asdict(result) | {"ok": result.ok} for result in results],
    }
    run_path = RUNTIME_DIR / f"morning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LATEST_SUMMARY.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_path


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Run the daily AI Adam Agent Company morning workflow.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run verification steps, but skip the commerce LLM agent execution.",
    )
    args = parser.parse_args()

    started_at = datetime.now().isoformat(timespec="seconds")
    results: list[StepResult] = []

    client_python = preferred_python(CLIENT_OPS_ROOT)
    commerce_python = preferred_python(COMMERCE_ROOT)

    results.append(
        run_step(
            "client-ops preflight",
            [client_python, "scripts/preflight_check.py", "--verbose"],
            CLIENT_OPS_ROOT,
            timeout=180,
        )
    )

    results.append(
        run_step(
            "client-ops mock-vs-real structural check",
            [client_python, "scripts/compare_mock_vs_real.py", "--agent", "all", "--skip-real"],
            CLIENT_OPS_ROOT,
            timeout=180,
        )
    )

    if not args.dry_run:
        results.append(
            run_step(
                "commerce daily agent run",
                [commerce_python, "scripts/run_commerce_cycle.py", "--use-llm"],
                COMMERCE_ROOT,
                timeout=600,
            )
        )

    results.append(
        run_step(
            "commerce run retention cleanup",
            [commerce_python, "scripts/cleanup_runs.py", "--keep", "30"] + (["--dry-run"] if args.dry_run else []),
            COMMERCE_ROOT,
            timeout=120,
        )
    )

    summary_path = write_summary(results, started_at=started_at, mode="dry-run" if args.dry_run else "live")
    print(f"\nsummary: {summary_path}")
    print(f"latest: {LATEST_SUMMARY}")

    failed = [result for result in results if not result.ok]
    if failed:
        print("failed steps:", ", ".join(result.name for result in failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
