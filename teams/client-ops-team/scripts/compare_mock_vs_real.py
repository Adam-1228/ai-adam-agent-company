"""Compare mock vs real (OpenAI) outputs for each client-ops agent.

The mock runner is known to pass validation because its output is shaped to do so.
This script proves whether real LLM outputs — which are free-form — survive the
same structural checks. It does NOT modify tasks/done.md or tasks/backlog.md.

Budget: at most 12 LLM invocations per run (6 fake tasks × {mock, openai}).
mock invocations do not cost anything; the real budget is bounded by len(FAKE_TASKS).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_client import complete, configure_stdout, load_dotenv
from load_persona import AGENT_NAMES_KR, compose_system_prompt
from run_agent import (
    P0_ESCALATION_KEYWORDS,
    parse_packet,
    policy_check,
    validate_output,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "mock_vs_real_diff.md"
MAX_LLM_CALLS = 12


# --- fake tasks (synthetic, no real customer data) ---

FAKE_TASKS: list[dict] = [
    {
        "agent": "01_onboarding_manager",
        "label": "ONB-001 신규 고객 진입 (정상)",
        "request": (
            "TASK ID: ONB-COMPARE-001\n"
            "TASK CODE: ONB-INTAKE\n"
            "PRIORITY: P1\n"
            "CONTEXT:\n"
            "- 가상 케이스: CLI-2026-COMPARE-001 (샘플치과 OOO 원장님). 계약 체결 완료.\n"
            "- 운영 시작 +3일. 사업자번호 검증 완료, 결제 본인 명의 확인. 권한 감사 정상.\n"
            "EXPECTED OUTPUT: 온보딩 패키지 + 위험 신호 카드 요약.\n"
        ),
    },
    {
        "agent": "02_ops_operator",
        "label": "OPS-002 일일 발송 (정상)",
        "request": (
            "TASK ID: OPS-COMPARE-002\n"
            "TASK CODE: OPS-REMIND-D-1\n"
            "CONTEXT:\n"
            "- 일일 18:00 예약 전일 리마인더 배치 결과. case CLI-2026-COMPARE-002 / appt-AAAA, "
            "scheduled=412, success=410, skipped=1, failed=1, dry_run=true.\n"
            "EXPECTED OUTPUT: 정형 JSON 일일 실행 요약.\n"
        ),
    },
    {
        "agent": "03_cs_manager",
        "label": "CS-001 환불 요청 (P0 escalation 필수)",
        "request": (
            "TASK ID: CS-COMPARE-001-REFUND\n"
            "TASK CODE: CS-INCOMING\n"
            "PRIORITY: P0\n"
            "CONTEXT:\n"
            "- 고객이 카카오 알림톡으로 \"지난번 시술 너무 아팠어요. 환불해주세요.\" 라고 메시지를 보냈습니다.\n"
            "- 자동 응답하지 말고 즉시 에스컬레이션 카드만 만들어 정총괄에게 넘기세요.\n"
        ),
    },
    {
        "agent": "03_cs_manager",
        "label": "CS-002 영업시간 문의 (정상 FAQ)",
        "request": (
            "TASK ID: CS-COMPARE-002-HOURS\n"
            "TASK CODE: CS-FAQ\n"
            "PRIORITY: P3\n"
            "CONTEXT:\n"
            "- 고객이 카카오 알림톡으로 \"오늘 영업시간이 어떻게 되나요?\" 라고 물어왔습니다.\n"
            "- 톤 카드 등재 FAQ 범위 내 정형 자동응답 초안을 작성하세요.\n"
        ),
    },
    {
        "agent": "04_data_analyst",
        "label": "ANL-002 주간 리포트 초안",
        "request": (
            "TASK ID: ANL-COMPARE-002\n"
            "TASK CODE: ANL-WEEKLY\n"
            "CONTEXT:\n"
            "- 2026-W21 주간 운영 데이터.\n"
            "- 박실행 정시 실행률 99.7% (직전 4주 평균 99.5%).\n"
            "- 이용대 P0 4건, P3 312건. 자동응답 사후 부적합 1건.\n"
            "- 신규 케이스 2건, 정총괄 1차 검수 통과율 2/2.\n"
            "EXPECTED OUTPUT: TL;DR + 표 + 출처 + 가설 (단정 금지).\n"
        ),
    },
    {
        "agent": "05_coordinator_qa",
        "label": "QA-006 최분석 리포트 검수",
        "request": (
            "TASK ID: QA-COMPARE-006\n"
            "TASK CODE: QA-ANL-WEEKLY\n"
            "CONTEXT:\n"
            "- 위 ANL-COMPARE-002 결과물을 검수합니다.\n"
            "- 비교 기준 누락, 출처 누락, 단정 표현 발견 시 HOLD. 모두 정합하면 PASS.\n"
            "EXPECTED OUTPUT: 검수 결정문 (JSON) + 결정 사유.\n"
        ),
    },
]


# --- diff machinery ---

@dataclass
class AgentRun:
    agent: str
    label: str
    mode: str
    text: str
    used: bool
    provider: str
    model: str
    fallback_used: bool
    error: str | None
    policy_fired: bool
    policy_rule: str | None
    warnings: list[str]
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.text or "")


@dataclass
class Diff:
    agent: str
    label: str
    severity: str  # BLOCKING / WARN / INFO / SKIP
    notes: list[str]
    mock: AgentRun
    real: AgentRun | None  # None when real was skipped


def run_one(task: dict, mode: str, *, force_mock: bool) -> AgentRun:
    """Invoke `complete()` once. `mode` controls env override before invocation."""
    if force_mock:
        os.environ["LLM_PROVIDER"] = "mock"
    else:
        if "LLM_PROVIDER" in os.environ:
            del os.environ["LLM_PROVIDER"]
        os.environ["LLM_PROVIDER"] = "openai"

    packet = parse_packet(task["request"])
    composed = compose_system_prompt(task["agent"])
    user_prompt = (
        "# 작업 패킷\n\n"
        f"{task['request']}\n\n"
        "## 응답 지침\n"
        "위 §1~§5(시스템 프롬프트)에 따라, 본 작업에 대해 자신의 output_template.md 형식으로 응답하세요.\n"
        "환불/법적/의료 키워드가 있으면 자동 응답하지 말고 정총괄을 경유한 에스컬레이션 패킷만 만들어 주세요.\n"
    )

    policy_meta = {"fired": False, "rule": None}
    policy_result = policy_check(task["agent"], packet)
    if policy_result is not None:
        result = policy_result
        policy_meta = result.get("policy") or policy_meta
    else:
        result = complete(task["agent"], composed["system_prompt"], user_prompt, use_llm=True)

    warnings = validate_output(task["agent"], result.get("text", ""))
    return AgentRun(
        agent=task["agent"],
        label=task["label"],
        mode=mode,
        text=result.get("text", ""),
        used=bool(result.get("used")),
        provider=str(result.get("provider")),
        model=str(result.get("model")),
        fallback_used=bool(result.get("fallback_used")),
        error=result.get("error"),
        policy_fired=bool(policy_meta.get("fired")),
        policy_rule=policy_meta.get("rule"),
        warnings=warnings,
    )


# Structural-field expectations per agent. Each entry is one of:
#   - a literal substring that must appear
#   - "OR:foo|bar|baz" meaning at least one of these must appear
EXPECTED_MARKERS: dict[str, list[str]] = {
    "01_onboarding_manager": [
        "OR:HANDOFF|다음 담당",
        "OR:확인 필요|확인필요|확인됨|위험",
    ],
    "02_ops_operator": [
        "OR:status|SUCCESS|FAILED|SKIPPED|REJECTED|일일",
        "OR:HANDOFF|next_owner|review_owner",
    ],
    "03_cs_manager": [
        "OR:HANDOFF|다음 담당|Next owner|next_owner",
    ],
    "04_data_analyst": [
        "OR:TL;DR|요약|결론",
        "OR:HANDOFF|다음 담당|Next owner",
    ],
    "05_coordinator_qa": [
        "OR:PASS|HOLD|ESCALATE|OWN_DECISION",
        "OR:HANDOFF|다음 담당|Next owner|결정 사유|사유",
    ],
}


def check_markers(agent: str, text: str) -> list[str]:
    """Return a list of MISSING marker descriptions."""
    missing: list[str] = []
    for marker in EXPECTED_MARKERS.get(agent, []):
        if marker.startswith("OR:"):
            options = marker[3:].split("|")
            if not any(opt and opt in text for opt in options):
                missing.append(f"none of: {', '.join(options)}")
        else:
            if marker not in text:
                missing.append(marker)
    return missing


def classify(mock: AgentRun, real: AgentRun | None) -> Diff:
    notes: list[str] = []
    severity = "INFO"

    if real is None:
        # When the policy gate fired on the mock side, it would identically fire
        # on the real side BEFORE any LLM call — parity is guaranteed by code.
        if mock.policy_fired:
            notes.append(
                "policy gate fired (rule=" + str(mock.policy_rule) + ") — LLM is bypassed in BOTH modes, "
                "so mock and real produce structurally identical escalation cards."
            )
            return Diff(agent=mock.agent, label=mock.label, severity="INFO", notes=notes, mock=mock, real=None)
        notes.append("real side skipped (no OPENAI_API_KEY)")
        return Diff(agent=mock.agent, label=mock.label, severity="SKIP", notes=notes, mock=mock, real=None)

    # Policy gate parity (CS refund must escalate in BOTH modes).
    if mock.policy_fired != real.policy_fired:
        notes.append(f"policy gate divergence: mock={mock.policy_fired} real={real.policy_fired}")
        severity = "BLOCKING"

    # Required structural markers.
    mock_missing = check_markers(mock.agent, mock.text)
    real_missing = check_markers(real.agent, real.text)
    if mock_missing:
        notes.append(f"mock missing markers: {mock_missing}")
    if real_missing:
        notes.append(f"real missing markers: {real_missing}")
    if real_missing and not mock_missing:
        severity = "BLOCKING"
    elif real_missing and mock_missing:
        severity = max(severity, "WARN", key=_sev_rank)

    # validate_output() warnings.
    if real.warnings and not mock.warnings:
        notes.append(f"real-only validator warnings: {real.warnings}")
        severity = max(severity, "WARN", key=_sev_rank)
    if mock.warnings:
        notes.append(f"mock validator warnings: {mock.warnings}")

    # Real-side failures (used=False) are BLOCKING — real LLM was supposed to respond.
    if not real.used and not real.policy_fired:
        notes.append(f"real side did not produce output: {real.error}")
        severity = "BLOCKING"

    # Length deltas are informational unless extreme.
    if mock.char_count and real.char_count:
        ratio = real.char_count / mock.char_count
        if ratio < 0.25 or ratio > 4.0:
            notes.append(f"length ratio {ratio:.2f} (mock={mock.char_count}, real={real.char_count})")
            severity = max(severity, "WARN", key=_sev_rank)

    if not notes:
        notes.append("no structural divergence detected")
    return Diff(agent=mock.agent, label=mock.label, severity=severity, notes=notes, mock=mock, real=real)


_SEV_ORDER = {"INFO": 0, "SKIP": 1, "WARN": 2, "BLOCKING": 3}


def _sev_rank(sev: str) -> int:
    return _SEV_ORDER.get(sev, 0)


# --- report writer ---

def write_report(diffs: list[Diff], *, started_at: str, real_attempted: bool) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    counts = {"BLOCKING": 0, "WARN": 0, "INFO": 0, "SKIP": 0}
    for d in diffs:
        counts[d.severity] = counts.get(d.severity, 0) + 1

    lines: list[str] = [
        "# Mock vs Real Diff Report",
        "",
        f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"시작 시각: {started_at}",
        f"실 LLM 호출 시도: {'yes' if real_attempted else 'no (OPENAI_API_KEY 미설정)'}",
        "",
        "## 요약",
        "",
        f"- 비교 케이스: {len(diffs)}",
        f"- BLOCKING: {counts['BLOCKING']}",
        f"- WARN: {counts['WARN']}",
        f"- INFO: {counts['INFO']}",
        f"- SKIP: {counts['SKIP']}",
        "",
        "## 케이스별 결과",
        "",
        "| Agent | Label | Severity | Mock provider | Real provider | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for d in diffs:
        notes_short = "; ".join(d.notes)
        if len(notes_short) > 110:
            notes_short = notes_short[:107] + "..."
        notes_short = notes_short.replace("|", "/").replace("\n", " ")
        real_label = "(skipped)" if d.real is None else f"{d.real.provider}:{d.real.model}"
        lines.append(
            f"| {AGENT_NAMES_KR.get(d.agent, d.agent)} | {d.label} | {d.severity} | "
            f"{d.mock.provider}:{d.mock.model} | {real_label} | {notes_short} |"
        )

    lines += ["", "## 상세 (각 케이스의 mock + real 본문)", ""]
    for d in diffs:
        lines += [
            f"### {d.agent} / {d.label} — {d.severity}",
            "",
            "- notes:",
        ]
        for note in d.notes:
            lines.append(f"  - {note}")
        lines += ["", "#### mock 출력", "", "```", d.mock.text.rstrip() or "(empty)", "```", ""]
        if d.real is not None:
            lines += ["#### real 출력", "", "```", d.real.text.rstrip() or "(empty)", "```", ""]
        else:
            lines += ["#### real 출력", "", "(skipped — real side not attempted)", ""]

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_PATH


# --- main ---

def select_tasks(agent_filter: str) -> list[dict]:
    if agent_filter == "all":
        return list(FAKE_TASKS)
    return [t for t in FAKE_TASKS if t["agent"] == agent_filter]


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default="all", help="all | 01_onboarding_manager | ... | 05_coordinator_qa")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--skip-real", action="store_true",
        help="Force-skip the real (openai) side even if OPENAI_API_KEY is present.",
    )
    args = parser.parse_args()

    tasks = select_tasks(args.agent)
    if not tasks:
        print(f"No fake tasks match agent='{args.agent}'", file=sys.stderr)
        return 2

    # Budget assertion: mock + real per task ≤ 12.
    expected_calls = len(tasks) * 2
    if expected_calls > MAX_LLM_CALLS:
        print(
            f"Refusing to exceed budget: {expected_calls} > {MAX_LLM_CALLS}. Use --agent <one> to narrow.",
            file=sys.stderr,
        )
        return 2

    # Try to load env. We need to know whether OPENAI_API_KEY is reachable.
    load_dotenv()
    real_available = bool(os.environ.get("OPENAI_API_KEY", "").strip()) and not args.skip_real

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    diffs: list[Diff] = []

    for task in tasks:
        mock = run_one(task, mode="mock", force_mock=True)
        if real_available:
            real = run_one(task, mode="openai", force_mock=False)
        else:
            real = None
        diffs.append(classify(mock, real))

    # Restore env (don't leave LLM_PROVIDER set globally for subsequent invocations).
    if "LLM_PROVIDER" in os.environ:
        del os.environ["LLM_PROVIDER"]

    report_path = write_report(diffs, started_at=started_at, real_attempted=real_available)

    blocking = [d for d in diffs if d.severity == "BLOCKING"]
    warn = [d for d in diffs if d.severity == "WARN"]
    skip = [d for d in diffs if d.severity == "SKIP"]

    print(f"=== mock vs real diff: {len(diffs)} cases ===")
    for d in diffs:
        line = f"  [{d.severity:8}] {d.agent} :: {d.label}"
        print(line)
        if args.verbose or d.severity == "BLOCKING":
            for note in d.notes:
                print(f"           - {note}")
    print()
    print(f"BLOCKING: {len(blocking)} | WARN: {len(warn)} | SKIP: {len(skip)} | total: {len(diffs)}")
    print(f"report: {report_path}")
    if not real_available:
        print(
            "real side skipped (no OPENAI_API_KEY found in client-ops .env or commerce .env fallback).\n"
            "Run on EC2 with the commerce .env or set OPENAI_API_KEY locally to exercise the real path.",
        )

    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
