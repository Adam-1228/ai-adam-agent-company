from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_command(command: list[str]) -> int:
    print("cmd:", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=str(ROOT))
    print("returncode:", completed.returncode, flush=True)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the recurring commerce work cycle.")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM notes in the legacy five-agent report.")
    args = parser.parse_args()

    python = sys.executable
    first = [python, "scripts/run_agents.py"]
    if args.use_llm:
        first.append("--use-llm")

    rc = run_command(first)
    if rc != 0:
        return rc
    rc = run_command([python, "scripts/commerce_growth_pipeline.py"])
    if rc != 0:
        return rc
    rc = run_command([python, "scripts/check_channel_readiness.py"])
    if rc != 0:
        return rc
    rc = run_command([python, "scripts/validate_channel_submissions.py"])
    if rc != 0:
        return rc
    return run_command([python, "scripts/validate_commerce_handoffs.py"])


if __name__ == "__main__":
    raise SystemExit(main())
