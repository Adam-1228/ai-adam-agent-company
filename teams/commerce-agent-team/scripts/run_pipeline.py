from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "product_candidates.csv"
REPORT_PATH = ROOT / "reports" / "latest_product_report.md"


@dataclass
class Candidate:
    id: str
    product_name: str
    source_market: str
    target_market: str
    category: str
    source_price_krw: int
    target_price_krw: int
    shipping_cost_krw: int
    platform_fee_rate: float
    estimated_monthly_demand: int
    competitor_count: int
    review_count: int
    avg_rating: float
    negative_review_rate: float
    return_risk: int
    certification_risk: int
    brand_ip_risk: int
    image_rights_risk: int
    notes: str
    source_url: str


def to_int(value: str) -> int:
    return int(float(value or 0))


def to_float(value: str) -> float:
    return float(value or 0)


def load_candidates() -> list[Candidate]:
    with DATA_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        return [
            Candidate(
                id=row["id"],
                product_name=row["product_name"],
                source_market=row["source_market"],
                target_market=row["target_market"],
                category=row["category"],
                source_price_krw=to_int(row["source_price_krw"]),
                target_price_krw=to_int(row["target_price_krw"]),
                shipping_cost_krw=to_int(row["shipping_cost_krw"]),
                platform_fee_rate=to_float(row["platform_fee_rate"]),
                estimated_monthly_demand=to_int(row["estimated_monthly_demand"]),
                competitor_count=to_int(row["competitor_count"]),
                review_count=to_int(row["review_count"]),
                avg_rating=to_float(row["avg_rating"]),
                negative_review_rate=to_float(row["negative_review_rate"]),
                return_risk=to_int(row["return_risk"]),
                certification_risk=to_int(row["certification_risk"]),
                brand_ip_risk=to_int(row["brand_ip_risk"]),
                image_rights_risk=to_int(row["image_rights_risk"]),
                notes=row["notes"],
                source_url=row["source_url"],
            )
            for row in rows
        ]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_candidate(c: Candidate) -> dict:
    fee = round(c.target_price_krw * c.platform_fee_rate)
    gross_profit = c.target_price_krw - c.source_price_krw - c.shipping_cost_krw - fee
    margin_rate = gross_profit / c.target_price_krw if c.target_price_krw else 0

    margin_score = clamp(margin_rate / 0.35, 0, 1) * 25
    demand_score = clamp(c.estimated_monthly_demand / 900, 0, 1) * 20
    competition_score = clamp(1 - (c.competitor_count / 180), 0, 1) * 15

    rating_component = clamp((c.avg_rating - 3.7) / 1.1, 0, 1) * 8
    review_volume_component = clamp(c.review_count / 800, 0, 1) * 4
    negative_component = clamp(1 - (c.negative_review_rate / 0.25), 0, 1) * 3
    review_score = rating_component + review_volume_component + negative_component

    ops_score = clamp(1 - (c.return_risk / 5), 0, 1) * 10

    risk_penalty = (
        c.return_risk * 2.2
        + c.certification_risk * 4.0
        + c.brand_ip_risk * 4.5
        + c.image_rights_risk * 3.5
    )

    hard_stops = []
    if gross_profit <= 0:
        hard_stops.append("예상 마진 0 이하")
    if c.return_risk >= 5:
        hard_stops.append("반품 리스크 5")
    if c.certification_risk >= 4:
        hard_stops.append("인증 리스크 높음")
    if c.brand_ip_risk >= 4:
        hard_stops.append("상표/IP 리스크 높음")
    if c.image_rights_risk >= 4:
        hard_stops.append("이미지 권리 리스크 높음")

    total = margin_score + demand_score + competition_score + review_score + ops_score - risk_penalty
    total = round(clamp(total, 0, 100), 1)

    if hard_stops:
        decision = "보류"
    elif total >= 70:
        decision = "진행 후보"
    elif total >= 50:
        decision = "검토 필요"
    else:
        decision = "보류"

    return {
        "candidate": c,
        "fee": fee,
        "gross_profit": gross_profit,
        "margin_rate": margin_rate,
        "margin_score": round(margin_score, 1),
        "demand_score": round(demand_score, 1),
        "competition_score": round(competition_score, 1),
        "review_score": round(review_score, 1),
        "ops_score": round(ops_score, 1),
        "risk_penalty": round(risk_penalty, 1),
        "total": total,
        "decision": decision,
        "hard_stops": hard_stops,
    }


def won(value: int) -> str:
    return f"{value:,}원"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def make_listing_draft(c: Candidate) -> str:
    title_1 = f"{c.product_name} {c.category} 실속형"
    title_2 = f"{c.category}용 {c.product_name} 정리 패키지"
    title_3 = f"{c.product_name} - 구매 전 확인사항 포함"

    return f"""### 상세페이지 초안: {c.product_name}

**상품명 후보**

1. {title_1}
2. {title_2}
3. {title_3}

**상세페이지 구성**

- 이런 분께 추천: {c.category}에서 작고 실용적인 상품을 찾는 고객
- 구매 전 확인: 사이즈, 구성품, 색상/옵션, 배송/반품 조건
- 사용 상황: 일상 사용, 정리/보관, 선물 또는 사무/가정용
- 차별화 포인트: {c.notes}
- FAQ:
  - Q. 구성품은 어떻게 되나요?
  - Q. 사이즈와 소재는 무엇인가요?
  - Q. 세척 또는 관리 방법은 무엇인가요?

**검수 메모**

- 인증/상표/이미지 리스크를 먼저 확인한 뒤 등록합니다.
- 타 판매자 이미지와 문구를 그대로 사용하지 않습니다.
"""


def render_report(scored: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ranked = sorted(scored, key=lambda x: x["total"], reverse=True)
    proceed = [x for x in ranked if x["decision"] == "진행 후보"]
    review = [x for x in ranked if x["decision"] == "검토 필요"]
    hold = [x for x in ranked if x["decision"] == "보류"]

    lines = [
        "# Weekly Product Discovery Report",
        "",
        f"생성 시각: {now}",
        "",
        "## 요약",
        "",
        f"- 전체 후보: {len(scored)}개",
        f"- 진행 후보: {len(proceed)}개",
        f"- 검토 필요: {len(review)}개",
        f"- 보류: {len(hold)}개",
        "",
        "## 랭킹",
        "",
        "| 순위 | ID | 상품 | 결정 | 총점 | 예상마진 | 마진율 | 리스크 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]

    for i, item in enumerate(ranked, start=1):
        c = item["candidate"]
        risk = ", ".join(item["hard_stops"]) if item["hard_stops"] else "관리 가능"
        lines.append(
            f"| {i} | {c.id} | {c.product_name} | {item['decision']} | {item['total']} | "
            f"{won(item['gross_profit'])} | {pct(item['margin_rate'])} | {risk} |"
        )

    lines.extend(["", "## 에이전트별 상세 판단", ""])

    for item in ranked:
        c = item["candidate"]
        lines.extend(
            [
                f"### {c.id}. {c.product_name}",
                "",
                f"- 목표 플랫폼: {c.target_market}",
                f"- 카테고리: {c.category}",
                f"- 예상 판매가: {won(c.target_price_krw)}",
                f"- 예상 수수료: {won(item['fee'])}",
                f"- 예상 마진: {won(item['gross_profit'])} ({pct(item['margin_rate'])})",
                f"- 점수: 마진 {item['margin_score']} / 수요 {item['demand_score']} / 경쟁 {item['competition_score']} / 리뷰 {item['review_score']} / 운영 {item['ops_score']} / 리스크 -{item['risk_penalty']}",
                f"- 최종 결정: **{item['decision']}**",
                f"- 하드 스톱: {', '.join(item['hard_stops']) if item['hard_stops'] else '없음'}",
                f"- 메모: {c.notes}",
                "",
            ]
        )

    lines.extend(["## TOP 후보 상세페이지 초안", ""])

    draft_targets = [x for x in ranked if x["decision"] in {"진행 후보", "검토 필요"}][:3]
    if not draft_targets:
        lines.append("진행 가능한 후보가 없습니다. Scout 단계에서 후보를 다시 수집하세요.")
    else:
        for item in draft_targets:
            lines.append(make_listing_draft(item["candidate"]))

    lines.extend(
        [
            "",
            "## 다음 액션",
            "",
            "1. 진행 후보의 실제 소싱처와 공급 가능 수량을 확인합니다.",
            "2. 인증/상표/IP/이미지 권리 증빙을 확인합니다.",
            "3. 샘플 구매 또는 상세페이지 제작 전 사람이 최종 승인합니다.",
            "4. 보류 상품은 이유를 데이터에 남기고 같은 유형을 반복 수집하지 않습니다.",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    candidates = load_candidates()
    scored = [score_candidate(c) for c in candidates]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(scored), encoding="utf-8")
    print(f"Generated: {REPORT_PATH}")


if __name__ == "__main__":
    main()
