from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFORCE = ROOT / "workforce"
AGENTS = WORKFORCE / "agents"
ACTIVE_TASKS = WORKFORCE / "tasks" / "active.md"

VALID_AGENTS = {
    "01_market_scout": "Market Scout - 윤서",
    "02_margin_analyst": "Margin Analyst - 민준",
    "03_risk_guardian": "Risk Guardian - 서아",
    "04_listing_builder": "Listing Builder - 지훈",
    "05_ops_manager": "Ops Manager - 태오",
}


def usage() -> str:
    agents = "\n".join(f"  - {agent}: {name}" for agent, name in VALID_AGENTS.items())
    return f"""Usage:
  python scripts\\assign_task.py <agent_id> "<task description>" [priority]

Agent IDs:
{agents}

Example:
  python scripts\\assign_task.py 01_market_scout "쿠팡 사무용품 후보 20개 조사" P1
"""


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] in {"-h", "--help"}:
        print(usage())
        return 0 if len(sys.argv) >= 2 else 1

    agent_id = sys.argv[1]
    task = sys.argv[2].strip()
    priority = sys.argv[3] if len(sys.argv) >= 4 else "P2"

    if agent_id not in VALID_AGENTS:
        print(f"Unknown agent_id: {agent_id}\n")
        print(usage())
        return 1

    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = f"TASK-{now}"
    owner = VALID_AGENTS[agent_id]
    block = f"""

## {task_id}

TASK ID: {task_id}
OWNER: {agent_id} ({owner})
STATUS: TODO
PRIORITY: {priority}
REQUEST: {task}
INPUTS: 확인 필요
EXPECTED OUTPUT: output_template.md 형식 준수
DEADLINE: 확인 필요
CONSTRAINTS: 자동 게시/구매/결제 금지. 리스크는 보수적으로 판단.
NEXT HANDOFF: 확인 필요
"""

    inbox = AGENTS / agent_id / "inbox.md"
    append_text(inbox, block)
    append_text(ACTIVE_TASKS, block)

    print(f"Assigned {task_id} to {agent_id}")
    print(f"Inbox: {inbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
