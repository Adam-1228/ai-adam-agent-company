from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
BACKLOG = ROOT / "tasks" / "backlog.md"

VALID_AGENTS = {
    "01_onboarding_manager": "Onboarding Manager - 김은보",
    "02_ops_operator": "Ops Operator - 박실행",
    "03_cs_manager": "CS Manager - 이용대",
    "04_data_analyst": "Data Analyst - 최분석",
    "05_coordinator_qa": "Coordinator/QA - 정총괄",
}

DEFAULT_TASK_CODE = {
    "01_onboarding_manager": "ONB-INTAKE",
    "02_ops_operator": "OPS-REMIND-D-1",
    "03_cs_manager": "CS-INCOMING",
    "04_data_analyst": "ANL-AD-HOC",
    "05_coordinator_qa": "QA-CS-DRAFT",
}


def usage() -> str:
    agents = "\n".join(f"  - {a}: {n}" for a, n in VALID_AGENTS.items())
    return (
        "Usage:\n"
        "  python scripts/assign_task.py <agent_id> \"<task description>\" [priority] [--task-code CODE]\n\n"
        f"Agent IDs:\n{agents}\n\n"
        "Example:\n"
        "  python scripts/assign_task.py 01_onboarding_manager \"샘플치과 001 신규 온보딩 시작\" P1\n"
        "  python scripts/assign_task.py 03_cs_manager \"환불 키워드 케이스 검토\" P0 --task-code CS-ESCALATE\n"
    )


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build_block(*, task_id: str, agent_id: str, task_code: str, priority: str, description: str) -> str:
    owner = VALID_AGENTS[agent_id]
    return (
        "\n\n"
        f"## {task_id}\n\n"
        f"TASK ID: {task_id}\n"
        f"TASK CODE: {task_code}\n"
        f"ASSIGNEE: {agent_id} ({owner})\n"
        "PRIORITY: " + priority + "\n"
        "REQUESTED BY: assign_task.py\n"
        f"CREATED AT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "DUE: 확인 필요\n\n"
        "CONTEXT:\n"
        f"- {description}\n"
        "- 실고객 정보 사용 금지. 가상 식별자 또는 케이스 ID만 사용합니다.\n\n"
        "INPUTS:\n"
        "- 확인 필요\n\n"
        "EXPECTED OUTPUT:\n"
        "- output_template.md 형식을 준수\n\n"
        "GUARDRAILS:\n"
        "- 사람 승인 전 외부 발송 금지\n"
        "- 환불/계약/법적/의료/세무 키워드는 즉시 05_coordinator_qa 에스컬레이션\n\n"
        "HANDOFF:\n"
        "- Next owner: 확인 필요\n"
        "- Required evidence: 확인 필요\n"
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Append a v1 task packet to the client-ops backlog and agent inbox.",
        usage=usage(),
        add_help=True,
    )
    parser.add_argument("agent_id", nargs="?")
    parser.add_argument("description", nargs="?")
    parser.add_argument("priority", nargs="?", default="P2")
    parser.add_argument("--task-code", default=None, help="Override the default task code for this agent.")
    parser.add_argument("--task-id", default=None, help="Override the auto-generated TASK ID (use for fixtures).")
    args = parser.parse_args()

    if not args.agent_id or not args.description:
        print(usage())
        return 1

    if args.agent_id not in VALID_AGENTS:
        print(f"Unknown agent_id: {args.agent_id}\n")
        print(usage())
        return 1

    task_code = args.task_code or DEFAULT_TASK_CODE[args.agent_id]
    if args.task_id:
        task_id = args.task_id
    else:
        task_id = f"TASK-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    block = build_block(
        task_id=task_id,
        agent_id=args.agent_id,
        task_code=task_code,
        priority=args.priority,
        description=args.description.strip(),
    )

    inbox = AGENTS_DIR / args.agent_id / "inbox.md"
    append_text(inbox, block)
    append_text(BACKLOG, block)

    print(f"Assigned {task_id} to {args.agent_id} ({task_code} / {args.priority})")
    print(f"Inbox:   {inbox}")
    print(f"Backlog: {BACKLOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
