from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from llm_client import complete
from load_persona import AGENT_NAMES_KR, compose_system_prompt
from run_agent import P0_ESCALATION_KEYWORDS, has_any


ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs"
REPORTS_DIR = ROOT / "reports"


# ---------- simulated customer messages ----------
# All content is synthetic. Phone numbers, names, and clinic IDs are placeholders.

SIMULATED_INBOUND = [
    {"day": 3, "from": "고객A", "channel": "kakao_alimtalk", "text": "내일 예약 시간 변경 가능할까요?"},
    {"day": 4, "from": "고객B", "channel": "kakao_alimtalk", "text": "주차장 위치가 어디인가요?"},
    {"day": 5, "from": "고객C", "channel": "sms", "text": "지난번 시술 너무 아팠어요. 환불해주세요."},
    {"day": 6, "from": "고객D", "channel": "kakao_alimtalk", "text": "다음 예약은 언제로 잡아주시나요?"},
]


@dataclass
class StepRecord:
    day: int
    step: str
    agent_id: str
    task_code: str
    decision: str
    summary: str
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_used: bool | None = None
    llm_fallback_used: bool | None = None
    policy_fired: bool = False
    policy_rule: str | None = None
    handoff_to_adam: bool = False
    metadata: dict = field(default_factory=dict)


def serialize(step: StepRecord) -> dict:
    return {
        "day": step.day,
        "step": step.step,
        "agent_id": step.agent_id,
        "agent_name_kr": AGENT_NAMES_KR.get(step.agent_id, step.agent_id),
        "task_code": step.task_code,
        "decision": step.decision,
        "summary": step.summary,
        "llm": {
            "provider": step.llm_provider,
            "model": step.llm_model,
            "used": step.llm_used,
            "fallback_used": step.llm_fallback_used,
        },
        "policy_fired": step.policy_fired,
        "policy_rule": step.policy_rule,
        "handoff_to_adam": step.handoff_to_adam,
        "metadata": step.metadata,
    }


# ---------- helper: invoke an LLM step (mock-safe) ----------

def llm_step(agent_id: str, task_description: str, use_llm: bool) -> dict:
    composed = compose_system_prompt(agent_id)
    user_prompt = f"# 시뮬레이션 작업\n\n{task_description}\n\noutput_template.md 형식으로 응답하세요."
    return complete(agent_id, composed["system_prompt"], user_prompt, use_llm=use_llm)


# ---------- mock Adam response (only when escalation fires) ----------

def synth_adam_response(*, case_id: str, escalation_summary: str) -> str:
    return (
        f"[MOCK ADAM RESPONSE]\n"
        f"case: {case_id}\n"
        f"decision: 직접 응대 진행. 의료 결과 불만이 아닌 만족도 이슈로 1차 판단함.\n"
        f"action: 정총괄에게 톤 카드 v2 작성 위임. 김은보 갱신 후 정총괄 검수.\n"
        f"context: {escalation_summary[:160]}{'...' if len(escalation_summary) > 160 else ''}\n"
    )


# ---------- write logs + report ----------

def write_jsonl(*, week: int, client_ref: str, records: list[StepRecord]) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / f"simulation_w{week}_{client_ref}.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(serialize(rec), ensure_ascii=False) + "\n")
    return path


def render_report(*, week: int, client_ref: str, records: list[StepRecord], started_at: str) -> str:
    counts: dict[str, int] = {}
    escalations = 0
    for rec in records:
        counts[rec.agent_id] = counts.get(rec.agent_id, 0) + 1
        if rec.handoff_to_adam:
            escalations += 1

    lines = [
        f"# Simulation Report - W{week} / {client_ref}",
        "",
        f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"시작 시각: {started_at}",
        "",
        "## TL;DR",
        "",
        f"- 총 스텝: {len(records)}",
        f"- Adam 에스컬레이션: {escalations}",
        f"- 에이전트별 호출 횟수: {', '.join(f'{k}={v}' for k, v in sorted(counts.items()))}",
        "",
        "## 일자별 흐름",
        "",
        "| Day | Step | Agent | 작업코드 | 결정 | 요약 |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for rec in records:
        name = AGENT_NAMES_KR.get(rec.agent_id, rec.agent_id)
        summary_short = rec.summary.replace("|", "/").replace("\n", " ")
        if len(summary_short) > 80:
            summary_short = summary_short[:77] + "..."
        lines.append(f"| {rec.day} | {rec.step} | {name} | {rec.task_code} | {rec.decision} | {summary_short} |")

    lines.extend([
        "",
        "## 정책 게이트 발동",
        "",
    ])
    policy_steps = [r for r in records if r.policy_fired]
    if not policy_steps:
        lines.append("- 없음")
    else:
        for r in policy_steps:
            lines.append(f"- Day {r.day} / {r.agent_id} / rule={r.policy_rule} → {r.decision}")

    lines.extend([
        "",
        "## 가드레일 점검",
        "",
        "- 실고객 정보 사용: 없음 (모든 메시지는 시뮬레이션 가짜 데이터)",
        "- DRY_RUN 기본값: true (외부 발송 0건)",
        "- 환불/법적 키워드 감지 시 자동 응답: 차단됨",
        "- 박실행 자유 텍스트 응답: 발생하지 않음 (정형 출력만)",
        "",
        "HANDOFF",
        "- 다음 담당: Adam",
        "- 넘길 자료: 본 리포트 + logs/simulation_w" + str(week) + "_" + client_ref + ".jsonl",
        "- 확인 필요: pre_launch_checklist.md §3, §5, §6 통과 시점",
        "- 하드 스톱: 없음 (시뮬레이션 한정)",
        "- 추천 액션: REVIEW",
    ])
    return "\n".join(lines) + "\n"


def write_report(*, week: int, client_ref: str, body: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"simulation_w{week}_{client_ref}.md"
    path.write_text(body, encoding="utf-8")
    return path


# ---------- the simulation itself ----------

def simulate(*, week: int, client_ref: str, use_llm: bool) -> tuple[Path, Path, list[StepRecord]]:
    records: list[StepRecord] = []
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    case_id = f"CLI-2026-{client_ref}"

    # Day 0: Adam → 김은보 ONB-001
    desc = (
        f"신규 케이스 {case_id} (가상: 샘플치과 OOO 원장님). "
        "계약은 체결되었고, 운영 시작 예정일은 +3일. 정보 수집 + 계약 검증 + 권한 감사 진행."
    )
    res = llm_step("01_onboarding_manager", desc, use_llm)
    records.append(StepRecord(
        day=0, step="ONB-INTAKE-OPEN", agent_id="01_onboarding_manager", task_code="ONB-INTAKE",
        decision="IN_PROGRESS",
        summary=f"Adam이 김은보에게 {case_id} 신규 온보딩 패키지 작성 요청.",
        llm_provider=res.get("provider"), llm_model=res.get("model"),
        llm_used=res.get("used"), llm_fallback_used=res.get("fallback_used"),
        metadata={"case_id": case_id},
    ))

    # Day 1~2: 김은보 정보 수집 + 검증 통과
    desc = (
        f"{case_id} 사업자번호 외부 API 검증 완료, 결제 정보 본인 명의 확인, "
        "권한 감사: 예약 조회/생성 권한만 부여, 환자 차트 읽기 권한은 거절. "
        "확인 필요 0건. 정총괄 셋업 검수 요청 단계로 전환."
    )
    res = llm_step("01_onboarding_manager", desc, use_llm)
    records.append(StepRecord(
        day=2, step="ONB-PACKAGE-COMPLETE", agent_id="01_onboarding_manager", task_code="ONB-PACKAGE",
        decision="READY_FOR_REVIEW",
        summary="김은보 온보딩 패키지 v1 작성 완료, 정총괄 셋업 검수 요청 대기.",
        llm_provider=res.get("provider"), llm_model=res.get("model"),
        llm_used=res.get("used"), llm_fallback_used=res.get("fallback_used"),
        metadata={"case_id": case_id, "checks_remaining": 0},
    ))

    # Day 2: 정총괄 셋업 검수 → PASS
    desc = (
        f"{case_id} 온보딩 패키지 검수. 확인 필요 0건, 권한 과잉 없음, 톤 카드 정합. "
        "박실행에게 OPS-REMIND-D-1, OPS-REVIEW-REQ 등록 승인. PASS."
    )
    res = llm_step("05_coordinator_qa", desc, use_llm)
    records.append(StepRecord(
        day=2, step="QA-ONB-PASS", agent_id="05_coordinator_qa", task_code="QA-ONB-REVIEW",
        decision="PASS",
        summary="정총괄 1차 검수 통과, 박실행 정기 작업 등록 인계 승인.",
        llm_provider=res.get("provider"), llm_model=res.get("model"),
        llm_used=res.get("used"), llm_fallback_used=res.get("fallback_used"),
        metadata={"case_id": case_id, "confidence": "high"},
    ))

    # Day 3: 김은보 → 박실행 OPS-001 핸드오프
    desc = (
        f"{case_id} 정기 작업 인계: OPS-REMIND-D-1 (cron 0 18 * * *), "
        "OPS-REVIEW-REQ (방문 +24h). 멱등성 키 패턴 정의 포함, DRY_RUN=true."
    )
    res = llm_step("02_ops_operator", desc, use_llm)
    records.append(StepRecord(
        day=3, step="ONB-HANDOFF-OPS", agent_id="02_ops_operator", task_code="ONB-HANDOFF-OPS",
        decision="REGISTERED",
        summary="박실행이 OPS-REMIND-D-1, OPS-REVIEW-REQ 작업 명세 수신, 스케줄러 등록 완료(가상).",
        llm_provider=res.get("provider"), llm_model=res.get("model"),
        llm_used=res.get("used"), llm_fallback_used=res.get("fallback_used"),
        metadata={"case_id": case_id, "tasks_registered": ["OPS-REMIND-D-1", "OPS-REVIEW-REQ"]},
    ))

    # Day 3~6: 박실행 일일 작업 + 고객 답장 라우팅
    for inbound in SIMULATED_INBOUND:
        day = inbound["day"]

        # 박실행이 매일 18:00 리마인더 발송 (가상). 결과를 기록.
        desc = (
            f"OPS-REMIND-D-1 실행: case={case_id}, day={day}, channel=kakao_alimtalk, status=SUCCESS, dry_run=true."
        )
        res = llm_step("02_ops_operator", desc, use_llm)
        records.append(StepRecord(
            day=day, step="OPS-REMIND-D-1", agent_id="02_ops_operator", task_code="OPS-REMIND-D-1",
            decision="SUCCESS",
            summary=f"Day {day} 18:00 리마인더 발송 성공 (DRY_RUN=true).",
            llm_provider=res.get("provider"), llm_model=res.get("model"),
            llm_used=res.get("used"), llm_fallback_used=res.get("fallback_used"),
            metadata={"case_id": case_id, "dry_run": True},
        ))

        # 고객 답장 → 이용대 라우팅
        inbound_text = inbound["text"]
        hits = has_any(inbound_text, P0_ESCALATION_KEYWORDS)
        if hits:
            # P0: 자동 응답 차단 + 정총괄 경유 Adam 통지 + Adam mock 응답
            summary = f"{inbound['from']} 인입 ({inbound['channel']}): \"{inbound_text}\" — P0 키워드 감지: {', '.join(hits)}."
            records.append(StepRecord(
                day=day, step="CS-INCOMING-P0", agent_id="03_cs_manager", task_code="CS-ESCALATE",
                decision="ESCALATE",
                summary=summary,
                llm_provider="policy", llm_model="policy:p0-escalation",
                llm_used=True, llm_fallback_used=False,
                policy_fired=True, policy_rule="p0_keyword_escalation",
                metadata={"case_id": case_id, "hits": hits, "channel": inbound["channel"]},
            ))

            qa_summary = f"{case_id} 이용대 P0 카드 수신: {', '.join(hits)}. Adam 통지 진행."
            res_qa = llm_step("05_coordinator_qa", qa_summary, use_llm)
            records.append(StepRecord(
                day=day, step="QA-CS-P0", agent_id="05_coordinator_qa", task_code="QA-CS-P0",
                decision="ESCALATE_TO_ADAM",
                summary="정총괄이 Adam에게 즉시 통지 (Telegram + 에스컬레이션 카드).",
                llm_provider=res_qa.get("provider"), llm_model=res_qa.get("model"),
                llm_used=res_qa.get("used"), llm_fallback_used=res_qa.get("fallback_used"),
                handoff_to_adam=True,
                metadata={"case_id": case_id, "trigger_keywords": hits},
            ))

            adam_text = synth_adam_response(case_id=case_id, escalation_summary=summary)
            records.append(StepRecord(
                day=day, step="ADAM-DECISION", agent_id="adam", task_code="HUMAN-DECISION",
                decision="DECIDED",
                summary=adam_text.replace("\n", " ")[:160],
                llm_provider="mock-human", llm_model="mock-human",
                llm_used=True, llm_fallback_used=False,
                metadata={"case_id": case_id, "raw": adam_text},
            ))
        else:
            # 일반 응대: P1/P2/P3 톤 카드 범위 내, 정총괄 사후 검수
            res_cs = llm_step("03_cs_manager", f"인입 응대: \"{inbound_text}\" (case {case_id}).", use_llm)
            records.append(StepRecord(
                day=day, step="CS-INCOMING", agent_id="03_cs_manager", task_code="CS-INCOMING",
                decision="DRAFTED",
                summary=f"{inbound['from']} 인입: \"{inbound_text}\" — 톤 카드 범위 내 응답 초안 작성.",
                llm_provider=res_cs.get("provider"), llm_model=res_cs.get("model"),
                llm_used=res_cs.get("used"), llm_fallback_used=res_cs.get("fallback_used"),
                metadata={"case_id": case_id, "channel": inbound["channel"]},
            ))

    # Day 7: 김은보 → 정총괄 정식 인계 (30일 운영 계획 확정), 정총괄 → Adam 주간 보고
    res = llm_step("01_onboarding_manager", f"{case_id} 첫 7일 운영 완료, 30일 계획 확정. 정총괄 정식 인계.", use_llm)
    records.append(StepRecord(
        day=7, step="ONB-30D-PLAN", agent_id="01_onboarding_manager", task_code="ONB-PACKAGE",
        decision="DONE",
        summary="김은보가 첫 7일 운영 결과 + 30일 계획 정총괄에게 정식 인계.",
        llm_provider=res.get("provider"), llm_model=res.get("model"),
        llm_used=res.get("used"), llm_fallback_used=res.get("fallback_used"),
        metadata={"case_id": case_id},
    ))

    res = llm_step("05_coordinator_qa", f"{case_id} 1주차 운영 회고 + Adam 주간 보고 작성.", use_llm)
    records.append(StepRecord(
        day=7, step="QA-WEEKLY-REPORT", agent_id="05_coordinator_qa", task_code="QA-ANL-WEEKLY",
        decision="PASS",
        summary="정총괄이 1주차 회고 정리 후 Adam에게 주간 보고. 에스컬레이션 정확도 양호 평가.",
        llm_provider=res.get("provider"), llm_model=res.get("model"),
        llm_used=res.get("used"), llm_fallback_used=res.get("fallback_used"),
        handoff_to_adam=True,
        metadata={"case_id": case_id, "scope": "weekly_review"},
    ))

    jsonl_path = write_jsonl(week=week, client_ref=client_ref, records=records)
    report_body = render_report(week=week, client_ref=client_ref, records=records, started_at=started_at)
    report_path = write_report(week=week, client_ref=client_ref, body=report_body)
    return jsonl_path, report_path, records


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a 7-day client-ops simulation.")
    parser.add_argument("--simulate-week", type=int, required=True, help="Week number (used in log/report filename).")
    parser.add_argument("--client-ref", required=True, help="Synthetic client reference, e.g., sample_dental_clinic_001.")
    parser.add_argument("--mock", action="store_true", help="Force mock provider (no real API calls). Default if no keys set.")
    args = parser.parse_args()

    # safety: only ASCII-friendly client_ref slug
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", args.client_ref):
        raise SystemExit("--client-ref must contain only [A-Za-z0-9_-].")

    use_llm = not args.mock
    jsonl_path, report_path, records = simulate(
        week=args.simulate_week,
        client_ref=args.client_ref,
        use_llm=use_llm,
    )

    print(f"Simulation complete: {len(records)} steps")
    print(f"  log:    {jsonl_path}")
    print(f"  report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
