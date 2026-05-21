from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

from llm_client import complete
from load_persona import AGENT_NAMES_KR, compose_system_prompt


ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"
ACTIVE_PATH = TASKS_DIR / "active.md"
BACKLOG_PATH = TASKS_DIR / "backlog.md"
DONE_PATH = TASKS_DIR / "done.md"

# Hard-coded handoff matrix enforcement.
# These triggers run BEFORE any LLM call. They encode shared/handoff_contract.md
# rules that must never depend on a model decision.
P0_ESCALATION_KEYWORDS = [
    "환불", "환급", "결제 취소", "카드 분쟁", "챠지백",
    "변호사", "고소", "소송", "신고", "민원", "공정위", "식약처", "보건소",
    "진단", "처방", "부작용", "의약품", "의료기기",
    "주민번호", "카르테", "진료기록",
    "자해", "자살", "협박", "폭언",
]

# Inputs that 박실행 (Ops Operator) must reject. He has no judgment scope.
OPS_REJECTED_KEYWORDS = [
    "환불", "결제", "계약", "변호사", "고소", "환급",
    "진단", "처방", "의료", "법률", "세무",
]


def has_any(text: str, needles: Iterable[str]) -> list[str]:
    found = []
    lowered = text
    for n in needles:
        if n in lowered:
            found.append(n)
    return found


# ---------- task packet parsing ----------

TASK_HEADING_RE = re.compile(r"^##\s+(?P<task_id>TASK-\S+|ONB-\S+|OPS-\S+|CS-\S+|ANL-\S+|QA-\S+)\s*$")


def split_blocks(text: str) -> list[tuple[str, str]]:
    """Return [(task_id, block_text), ...] from a tasks/*.md file."""
    blocks: list[tuple[str, str]] = []
    current_id: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = TASK_HEADING_RE.match(line.strip())
        if m:
            if current_id is not None:
                blocks.append((current_id, "\n".join(buf).rstrip()))
            current_id = m.group("task_id")
            buf = [line]
        else:
            if current_id is not None:
                buf.append(line)
    if current_id is not None:
        blocks.append((current_id, "\n".join(buf).rstrip()))
    return blocks


def parse_packet(block: str) -> dict:
    """Parse a v1 packet text block into a dict.

    Extracts top-level fields (key: value lines before the first indented section)
    plus multi-line sections (CONTEXT, INPUTS, EXPECTED OUTPUT, GUARDRAILS, HANDOFF).
    """
    packet: dict = {"raw": block, "sections": {}}
    lines = block.splitlines()
    section: str | None = None
    section_lines: list[str] = []

    section_headers = {"CONTEXT", "INPUTS", "EXPECTED OUTPUT", "GUARDRAILS", "HANDOFF"}

    def flush_section() -> None:
        if section is not None:
            packet["sections"][section] = "\n".join(section_lines).strip()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("## "):
            continue
        if stripped.endswith(":") and stripped[:-1] in section_headers:
            flush_section()
            section = stripped[:-1]
            section_lines = []
            continue
        if section is not None:
            section_lines.append(line)
        else:
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                packet[key.strip()] = value.strip()
    flush_section()
    return packet


def find_task(task_id: str) -> tuple[Path, dict] | None:
    for path in (ACTIVE_PATH, BACKLOG_PATH):
        if not path.exists():
            continue
        for tid, block in split_blocks(path.read_text(encoding="utf-8")):
            if tid == task_id:
                return path, parse_packet(block)
    return None


# ---------- handoff matrix enforcement ----------

def policy_check(agent_id: str, packet: dict) -> dict | None:
    """If a hard-coded policy fires, return a synthesized result dict; else None.

    The returned dict mirrors `complete()` output plus a `policy` key with metadata.
    """
    haystack = "\n".join(filter(None, [
        packet.get("raw", ""),
        packet.get("sections", {}).get("CONTEXT", ""),
    ]))

    if agent_id == "03_cs_manager":
        hits = has_any(haystack, P0_ESCALATION_KEYWORDS)
        if hits:
            return {
                "text": (
                    "ESCALATION CARD (POLICY-ENFORCED)\n\n"
                    f"케이스: {packet.get('TASK ID', '(unknown)')}\n"
                    f"감지 키워드: {', '.join(hits)}\n"
                    "자동 응답: 보내지 않음\n"
                    "처리: 05_coordinator_qa 경유로 Adam에게 즉시 통지\n"
                    "근거: shared/handoff_contract.md / 03_cs_manager/persona.md §즉시 사람 에스컬레이션\n"
                ),
                "model": "policy:p0-escalation",
                "provider": "policy",
                "used": True,
                "error": None,
                "usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
                "fallback_used": False,
                "policy": {
                    "fired": True,
                    "rule": "p0_keyword_escalation",
                    "hits": hits,
                    "decision": "ESCALATE_TO_ADAM",
                    "next_owner": "05_coordinator_qa",
                    "handoff_to_adam": True,
                },
            }

    if agent_id == "02_ops_operator":
        hits = has_any(haystack, OPS_REJECTED_KEYWORDS)
        if hits:
            return {
                "text": (
                    "REJECTION (POLICY-ENFORCED)\n\n"
                    f"status: REJECTED_OUT_OF_SCOPE\n"
                    f"task_id: {packet.get('TASK ID', '(unknown)')}\n"
                    f"trigger_keywords: {', '.join(hits)}\n"
                    "route_to: 03_cs_manager\n"
                    "reason: 박실행은 환불/결제/계약/법적/의료 영역을 처리하지 않습니다.\n"
                    "근거: shared/handoff_contract.md / 02_ops_operator/persona.md §하지 않는 일\n"
                ),
                "model": "policy:ops-rejection",
                "provider": "policy",
                "used": True,
                "error": None,
                "usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
                "fallback_used": False,
                "policy": {
                    "fired": True,
                    "rule": "ops_out_of_scope",
                    "hits": hits,
                    "decision": "REJECTED_OUT_OF_SCOPE",
                    "next_owner": "03_cs_manager",
                    "handoff_to_adam": False,
                },
            }

    return None


# ---------- output validation ----------

def validate_output(agent_id: str, text: str) -> list[str]:
    """Return a list of warning strings (empty if structure looks OK)."""
    warnings: list[str] = []
    if not text.strip():
        warnings.append("empty output")
        return warnings

    if agent_id == "02_ops_operator":
        # 박실행은 정형 출력. JSON-like 또는 status 필드가 있어야 함.
        if "{" not in text and "status" not in text.lower():
            warnings.append("02_ops_operator output missing JSON/status structure")
    else:
        if "HANDOFF" not in text and "다음 담당" not in text:
            warnings.append("output missing HANDOFF / 다음 담당 marker")
    return warnings


# ---------- writers ----------

def append_done_entry(*, task_id: str, agent_id: str, result: dict, warnings: list[str]) -> None:
    DONE_PATH.parent.mkdir(parents=True, exist_ok=True)
    block = (
        "\n\n"
        f"## {task_id}\n\n"
        f"COMPLETED AT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"AGENT: {agent_id} ({AGENT_NAMES_KR.get(agent_id, '?')})\n"
        f"PROVIDER: {result.get('provider')}\n"
        f"MODEL: {result.get('model')}\n"
        f"USED: {result.get('used')}\n"
        f"FALLBACK_USED: {result.get('fallback_used')}\n"
        f"WARNINGS: {', '.join(warnings) if warnings else 'none'}\n\n"
        "OUTPUT:\n"
        "```text\n"
        f"{result.get('text', '').rstrip()}\n"
        "```\n"
    )
    with DONE_PATH.open("a", encoding="utf-8", newline="\n") as f:
        f.write(block)


def append_handoff_packet(*, source_task_id: str, target_agent: str, task_code: str, description: str) -> str:
    new_id = f"TASK-{datetime.now().strftime('%Y%m%d-%H%M%S')}-handoff"
    block = (
        "\n\n"
        f"## {new_id}\n\n"
        f"TASK ID: {new_id}\n"
        f"TASK CODE: {task_code}\n"
        f"ASSIGNEE: {target_agent} ({AGENT_NAMES_KR.get(target_agent, '?')})\n"
        "PRIORITY: P0\n"
        "REQUESTED BY: run_agent.py (handoff)\n"
        f"CREATED AT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"PARENT TASK: {source_task_id}\n\n"
        "CONTEXT:\n"
        f"- {description}\n\n"
        "INPUTS:\n"
        f"- Source packet: {source_task_id}\n\n"
        "EXPECTED OUTPUT:\n"
        "- 05_coordinator_qa 결정문 (PASS / HOLD / ESCALATE_TO_ADAM / OWN_DECISION)\n\n"
        "GUARDRAILS:\n"
        "- 사람 승인 전 외부 발송 금지\n\n"
        "HANDOFF:\n"
        "- Next owner: 확인 필요\n"
        "- Required evidence: 본 패킷 + 원 케이스 로그\n"
    )
    BACKLOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BACKLOG_PATH.open("a", encoding="utf-8", newline="\n") as f:
        f.write(block)
    return new_id


# ---------- main ----------

def run(*, agent_id: str, task_id: str, use_llm: bool, dry_run: bool) -> dict:
    if agent_id not in AGENT_NAMES_KR:
        raise SystemExit(f"Unknown agent_id: {agent_id}")

    found = find_task(task_id)
    if not found:
        raise SystemExit(
            f"Task '{task_id}' not found in {ACTIVE_PATH.name} or {BACKLOG_PATH.name}.\n"
            f"Use scripts/assign_task.py to create it first."
        )
    source_path, packet = found

    composed = compose_system_prompt(agent_id)
    system_prompt = composed["system_prompt"]

    request_summary = packet.get("sections", {}).get("CONTEXT") or packet.get("CONTEXT") or packet.get("raw", "")
    user_prompt = (
        f"# 작업 패킷\n\n"
        f"TASK ID: {task_id}\n"
        f"TASK CODE: {packet.get('TASK CODE', '(none)')}\n"
        f"PRIORITY: {packet.get('PRIORITY', '(none)')}\n\n"
        f"## 요청\n{request_summary}\n\n"
        f"## 응답 지침\n"
        f"위 §1~§5(시스템 프롬프트)에 따라, 본 작업에 대해 자신의 output_template.md 형식으로 응답하세요.\n"
        f"환불/법적/의료 키워드가 있으면 자동 응답하지 말고 정총괄을 경유한 에스컬레이션 패킷만 만들어 주세요.\n"
    )

    # ---- handoff matrix enforcement BEFORE the LLM call ----
    policy_result = policy_check(agent_id, packet)
    if policy_result is not None:
        result = policy_result
    else:
        result = complete(agent_id, system_prompt, user_prompt, use_llm=use_llm)

    warnings = validate_output(agent_id, result.get("text", ""))

    handoff_id: str | None = None
    policy_meta = result.get("policy") or {}
    if not dry_run:
        append_done_entry(task_id=task_id, agent_id=agent_id, result=result, warnings=warnings)

        if policy_meta.get("fired"):
            target = policy_meta.get("next_owner")
            if target:
                if policy_meta.get("rule") == "p0_keyword_escalation":
                    task_code = "QA-CS-P0"
                    description = "이용대 P0 키워드 감지, 정총괄 검수 후 Adam 통지 필요."
                else:
                    task_code = "CS-RECOVERY"
                    description = "박실행 권한 외 입력, 이용대 회수 응대 필요."
                handoff_id = append_handoff_packet(
                    source_task_id=task_id,
                    target_agent=target,
                    task_code=task_code,
                    description=description,
                )

    summary = {
        "task_id": task_id,
        "agent_id": agent_id,
        "agent_name_kr": AGENT_NAMES_KR.get(agent_id),
        "source_packet_path": str(source_path),
        "policy_fired": bool(policy_meta.get("fired")),
        "policy_rule": policy_meta.get("rule"),
        "policy_decision": policy_meta.get("decision"),
        "handoff_task_id": handoff_id,
        "llm_used": result.get("used"),
        "llm_provider": result.get("provider"),
        "llm_model": result.get("model"),
        "llm_fallback_used": result.get("fallback_used"),
        "warnings": warnings,
        "dry_run": dry_run,
    }
    return {"summary": summary, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a single client-ops agent for one task.")
    parser.add_argument("agent_id", help=f"One of: {', '.join(AGENT_NAMES_KR)}")
    parser.add_argument("--task-id", required=True, help="TASK ID found in tasks/active.md or tasks/backlog.md")
    parser.add_argument("--no-llm", action="store_true", help="Force mock provider regardless of config.")
    parser.add_argument("--dry-run", action="store_true", help="Run the call but do not write tasks/done.md or backlog.md")
    parser.add_argument("--json", action="store_true", help="Print full result JSON instead of human summary.")
    args = parser.parse_args()

    use_llm = not args.no_llm  # mock mode is still triggered when provider==mock or env LLM_PROVIDER=mock

    out = run(
        agent_id=args.agent_id,
        task_id=args.task_id,
        use_llm=use_llm,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    s = out["summary"]
    print(f"=== {s['agent_id']} ({s['agent_name_kr']}) / {s['task_id']} ===")
    print(f"policy_fired   : {s['policy_fired']} ({s.get('policy_rule')} → {s.get('policy_decision')})")
    print(f"llm            : provider={s['llm_provider']} model={s['llm_model']} used={s['llm_used']} fallback={s['llm_fallback_used']}")
    print(f"warnings       : {', '.join(s['warnings']) if s['warnings'] else 'none'}")
    if s["handoff_task_id"]:
        print(f"handoff packet : {s['handoff_task_id']} (added to backlog.md)")
    if s["dry_run"]:
        print("dry-run        : tasks/done.md and backlog.md were NOT modified")
    print()
    print("--- OUTPUT ---")
    print(out["result"].get("text", "").rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
