from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from llm_client import complete
from run_pipeline import Candidate, load_candidates, make_listing_draft, pct, score_candidate, won


ROOT = Path(__file__).resolve().parents[1]
WORKFORCE = ROOT / "workforce"
RUNS_DIR = WORKFORCE / "runs"
REPORTS_DIR = WORKFORCE / "reports"
LATEST_REPORT = ROOT / "reports" / "latest_agent_run.md"

AGENTS = {
    "01_market_scout": "Market Scout - 윤서",
    "02_margin_analyst": "Margin Analyst - 민준",
    "03_risk_guardian": "Risk Guardian - 서아",
    "04_listing_builder": "Listing Builder - 지훈",
    "05_ops_manager": "Ops Manager - 태오",
}


def read_agent_file(agent_id: str, filename: str) -> str:
    path = WORKFORCE / "agents" / agent_id / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_agent_output(agent_id: str, run_dir: Path, content: str) -> Path:
    run_path = run_dir / f"{agent_id}.md"
    run_path.write_text(content, encoding="utf-8")

    outbox = WORKFORCE / "agents" / agent_id / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    outbox_path = outbox / f"{run_dir.name}.md"
    outbox_path.write_text(content, encoding="utf-8")
    return run_path


def candidate_line(c: Candidate) -> str:
    return (
        f"- {c.id} | {c.product_name} | {c.category} | "
        f"소싱가 {won(c.source_price_krw)} | 판매가 {won(c.target_price_krw)} | "
        f"경쟁 {c.competitor_count} | 리뷰 {c.review_count} | 평점 {c.avg_rating}"
    )


def scout_report(candidates: list[Candidate]) -> str:
    lines = [
        "# SCOUT REPORT",
        "",
        "담당: 01_market_scout / 윤서",
        "",
        "## 후보 목록",
        "",
    ]
    lines.extend(candidate_line(c) for c in candidates)
    lines.extend(
        [
            "",
            "## 1차 관찰",
            "",
            "- 소형/저파손 상품은 케이블 정리, 반려동물 소모품, 주방 수납 쪽에서 보입니다.",
            "- 전기/캐릭터/IP 의존 상품은 초기 단계에서 보수적으로 넘깁니다.",
            "- 다음 단계에서는 마진과 수요 대비 경쟁 강도를 숫자로 확인해야 합니다.",
            "",
            "HANDOFF",
            "- 다음 담당: 02_margin_analyst",
            "- 넘길 자료: data/product_candidates.csv",
            "- 확인 필요: 실제 소싱처, 공급 가능 수량, 광고비 가정",
            "- 하드 스톱: 없음",
            "- 추천 액션: 모든 후보를 1차 점수화",
        ]
    )
    return "\n".join(lines)


def analyst_report(scored: list[dict]) -> str:
    ranked = sorted(scored, key=lambda x: x["total"], reverse=True)
    lines = [
        "# ANALYSIS REPORT",
        "",
        "담당: 02_margin_analyst / 민준",
        "",
        "| ID | 상품 | 총점 | 결정 | 예상마진 | 마진율 | 수요 | 경쟁 | 리뷰 | 운영 |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in ranked:
        c = item["candidate"]
        lines.append(
            f"| {c.id} | {c.product_name} | {item['total']} | {item['decision']} | "
            f"{won(item['gross_profit'])} | {pct(item['margin_rate'])} | "
            f"{item['demand_score']} | {item['competition_score']} | {item['review_score']} | {item['ops_score']} |"
        )
    lines.extend(
        [
            "",
            "## 분석 의견",
            "",
            "- 50점 이상은 추가 검토 대상으로 볼 수 있습니다.",
            "- 인증/IP 하드 스톱이 있는 상품은 점수가 높아도 Risk Guardian에서 막아야 합니다.",
            "- 광고비를 넣으면 저가 상품의 실제 마진은 더 낮아질 수 있습니다.",
            "",
            "HANDOFF",
            "- 다음 담당: 03_risk_guardian",
            "- 넘길 자료: 점수표, 마진율, 하드 스톱 후보",
            "- 확인 필요: 인증 필요 여부, 브랜드/IP 사용 가능 여부",
            "- 하드 스톱: 점수만으로 확정 금지",
            "- 추천 액션: 리스크 높은 상품 우선 검수",
        ]
    )
    return "\n".join(lines)


def risk_report(scored: list[dict]) -> str:
    ranked = sorted(scored, key=lambda x: x["total"], reverse=True)
    lines = [
        "# RISK REVIEW",
        "",
        "담당: 03_risk_guardian / 서아",
        "",
        "| ID | 상품 | 결정 | 하드 스톱 | 인증 | IP | 이미지 | 반품 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in ranked:
        c = item["candidate"]
        hard_stop = ", ".join(item["hard_stops"]) if item["hard_stops"] else "없음"
        risk_decision = "HOLD" if item["hard_stops"] else "REVIEW"
        if item["decision"] == "진행 후보" and not item["hard_stops"]:
            risk_decision = "PROCEED"
        lines.append(
            f"| {c.id} | {c.product_name} | {risk_decision} | {hard_stop} | "
            f"{c.certification_risk} | {c.brand_ip_risk} | {c.image_rights_risk} | {c.return_risk} |"
        )
    lines.extend(
        [
            "",
            "## 단호한 판단",
            "",
            "- USB 충전식 미니 가습기는 인증/AS/반품 리스크 확인 전 보류입니다.",
            "- 캐릭터 휴대폰 케이스 랜덤박스는 IP와 이미지 권리 리스크로 보류입니다.",
            "- 리스크가 낮은 후보만 Listing Builder에게 넘깁니다.",
            "",
            "HANDOFF",
            "- 다음 담당: 04_listing_builder 또는 05_ops_manager",
            "- 넘길 자료: 하드 스톱 없는 후보",
            "- 확인 필요: 인증 증빙, 이미지 사용 권한, 소싱 계약 조건",
            "- 하드 스톱: 인증/IP/이미지 권리 리스크 높은 상품",
            "- 추천 액션: REVIEW 후보만 상세페이지 초안 작성",
        ]
    )
    return "\n".join(lines)


def listing_report(scored: list[dict]) -> str:
    targets = [
        item
        for item in sorted(scored, key=lambda x: x["total"], reverse=True)
        if not item["hard_stops"] and item["decision"] in {"진행 후보", "검토 필요"}
    ][:3]

    lines = [
        "# LISTING DRAFTS",
        "",
        "담당: 04_listing_builder / 지훈",
        "",
    ]
    if not targets:
        lines.append("상세페이지 초안을 만들 수 있는 후보가 없습니다.")
    else:
        for item in targets:
            lines.append(make_listing_draft(item["candidate"]))
    lines.extend(
        [
            "",
            "HANDOFF",
            "- 다음 담당: 05_ops_manager",
            "- 넘길 자료: 상품명 후보, 상세페이지 구성, FAQ, 구매 전 확인사항",
            "- 확인 필요: 실제 상품 사진, 구성품, 소재, 사이즈, 공급사 권한",
            "- 하드 스톱: 리스크 검수 미통과 상품은 제외",
            "- 추천 액션: 검토 필요 후보만 샘플/소싱 확인",
        ]
    )
    return "\n".join(lines)


def manager_report(scored: list[dict], run_id: str) -> str:
    ranked = sorted(scored, key=lambda x: x["total"], reverse=True)
    proceed = [x for x in ranked if x["decision"] == "진행 후보" and not x["hard_stops"]]
    review = [x for x in ranked if x["decision"] == "검토 필요" and not x["hard_stops"]]
    hold = [x for x in ranked if x not in proceed and x not in review]

    def names(items: list[dict]) -> str:
        if not items:
            return "- 없음"
        return "\n".join(f"- {x['candidate'].id}: {x['candidate'].product_name} ({x['total']}점)" for x in items)

    lines = [
        "# FINAL COMMERCE REPORT",
        "",
        f"RUN ID: {run_id}",
        f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 결론",
        "",
        "현재 샘플 데이터에서는 즉시 진행 후보는 없고, 검토 필요 후보 2개를 소싱/샘플 확인 대상으로 봅니다.",
        "",
        "## 진행 후보",
        "",
        names(proceed),
        "",
        "## 검토 필요",
        "",
        names(review),
        "",
        "## 보류/폐기",
        "",
        names(hold),
        "",
        "## 가장 큰 리스크",
        "",
        "- 인증/IP/이미지 권리 리스크가 있는 상품은 점수와 무관하게 막아야 합니다.",
        "- 저가 상품은 광고비를 포함하면 마진이 급격히 낮아질 수 있습니다.",
        "- 실제 판매 전 공급사 권한, 이미지 권리, 구성품 정보를 확인해야 합니다.",
        "",
        "## 사람 승인 필요",
        "",
        "- 실제 상품 소싱처 확인",
        "- 샘플 구매 여부",
        "- 이미지/상세페이지 제작 방식",
        "- 플랫폼 등록 여부",
        "",
        "## 다음 액션",
        "",
        "1. 검토 필요 후보 2개에 대해 실제 소싱처와 샘플 가능 여부를 확인합니다.",
        "2. Scout에게 같은 조건으로 후보 20개를 더 찾게 합니다.",
        "3. 광고비 10~20% 시나리오를 Analyst에게 추가 계산시킵니다.",
    ]
    return "\n".join(lines)


def append_llm_note(agent_id: str, deterministic_report: str, use_llm: bool) -> str:
    if not use_llm:
        return deterministic_report

    persona = read_agent_file(agent_id, "persona.md")
    prompt = (
        "아래 결정론적 에이전트 산출물을 검토하고, 빠진 리스크나 다음 액션만 짧게 보강하세요.\n\n"
        f"{deterministic_report}"
    )
    result = complete(agent_id, persona, prompt, use_llm=True)
    if result.used and result.text:
        return (
            deterministic_report
            + "\n\n## LLM 보강 메모\n\n"
            + result.text.strip()
            + f"\n\n_PROVIDER: {result.provider} / MODEL: {result.model}_\n"
        )
    return (
        deterministic_report
        + "\n\n## LLM 보강 메모\n\n"
        + f"- LLM 보강을 건너뜀: {result.error or 'mock provider'}\n"
    )


def run(use_llm: bool) -> Path:
    run_id = "RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    candidates = load_candidates()
    scored = [score_candidate(c) for c in candidates]

    artifacts = {
        "01_market_scout": scout_report(candidates),
        "02_margin_analyst": analyst_report(scored),
        "03_risk_guardian": risk_report(scored),
        "04_listing_builder": listing_report(scored),
        "05_ops_manager": manager_report(scored, run_id),
    }

    metadata = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "use_llm": use_llm,
        "candidate_count": len(candidates),
        "agent_count": len(AGENTS),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    for agent_id, content in artifacts.items():
        write_agent_output(agent_id, run_dir, append_llm_note(agent_id, content, use_llm))

    final_report = run_dir / "05_ops_manager.md"
    latest_workforce_report = REPORTS_DIR / "latest_final_report.md"
    shutil.copyfile(final_report, latest_workforce_report)
    shutil.copyfile(final_report, LATEST_REPORT)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the five-agent commerce workforce.")
    parser.add_argument("--use-llm", action="store_true", help="Use configured LLM provider for short enhancement notes.")
    args = parser.parse_args()

    run_dir = run(use_llm=args.use_llm)
    print(f"Generated run: {run_dir}")
    print(f"Latest report: {LATEST_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
