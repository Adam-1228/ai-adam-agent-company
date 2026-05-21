from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
DATA_PATH = ROOT / "data" / "product_candidates.csv"
ROSTER_PATH = REPO_ROOT / "shared" / "organization" / "agent_roster.json"
RUNTIME = ROOT / "runtime"
PIPELINE_RUNTIME = RUNTIME / "growth_pipeline"
CHANNEL_PENDING = RUNTIME / "channel_submissions" / "pending"
REPORTS = ROOT / "reports"
DB_PATH = RUNTIME / "commerce_growth.sqlite3"
LATEST_JSON = PIPELINE_RUNTIME / "latest.json"
LATEST_REPORT = REPORTS / "latest_growth_pipeline.md"


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


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def to_int(value: str) -> int:
    return int(float(value or 0))


def to_float(value: str) -> float:
    return float(value or 0)


def money(value: int | float) -> str:
    return f"{int(value):,}원"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def load_roster() -> dict[str, dict]:
    payload = read_json(ROSTER_PATH, {"agents": []})
    return {f"{item['team']}:{item['agent_id']}": item for item in payload.get("agents", [])}


def load_candidates() -> list[Candidate]:
    with DATA_PATH.open("r", encoding="utf-8-sig", newline="") as f:
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
            for row in csv.DictReader(f)
        ]


def score_candidate(c: Candidate) -> dict:
    fee = round(c.target_price_krw * c.platform_fee_rate)
    gross_profit = c.target_price_krw - c.source_price_krw - c.shipping_cost_krw - fee
    margin_rate = gross_profit / c.target_price_krw if c.target_price_krw else 0
    margin_score = clamp(margin_rate / 0.35, 0, 1) * 25
    demand_score = clamp(c.estimated_monthly_demand / 900, 0, 1) * 20
    competition_score = clamp(1 - (c.competitor_count / 180), 0, 1) * 15
    rating_score = clamp((c.avg_rating - 3.7) / 1.1, 0, 1) * 8
    review_score = rating_score + clamp(c.review_count / 800, 0, 1) * 4
    complaint_score = clamp(1 - c.negative_review_rate / 0.25, 0, 1) * 3
    ops_score = clamp(1 - c.return_risk / 5, 0, 1) * 10
    risk_penalty = c.return_risk * 2.2 + c.certification_risk * 4 + c.brand_ip_risk * 4.5 + c.image_rights_risk * 3.5
    total = round(clamp(margin_score + demand_score + competition_score + review_score + complaint_score + ops_score - risk_penalty, 0, 100), 1)
    return {
        "fee": fee,
        "gross_profit": gross_profit,
        "margin_rate": round(margin_rate, 4),
        "margin_score": round(margin_score, 1),
        "demand_score": round(demand_score, 1),
        "competition_score": round(competition_score, 1),
        "review_score": round(review_score + complaint_score, 1),
        "ops_score": round(ops_score, 1),
        "risk_penalty": round(risk_penalty, 1),
        "total": total,
    }


def connect_db() -> sqlite3.Connection:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        create table if not exists pipeline_runs (
          run_id text primary key,
          created_at text not null,
          status text not null,
          summary_json text not null
        );
        create table if not exists product_opportunities (
          run_id text not null,
          opportunity_id text not null,
          product_name text not null,
          category text not null,
          source_market text not null,
          target_market text not null,
          evidence_json text not null,
          status text not null,
          created_at text not null,
          primary key (run_id, opportunity_id)
        );
        create table if not exists supplier_evidence (
          run_id text not null,
          opportunity_id text not null,
          supplier_status text not null,
          landed_cost_krw integer not null,
          expected_margin_krw integer not null,
          margin_rate real not null,
          evidence_level text not null,
          notes text not null,
          primary key (run_id, opportunity_id)
        );
        create table if not exists risk_reviews (
          run_id text not null,
          opportunity_id text not null,
          risk_level text not null,
          blocked integer not null,
          hard_stops_json text not null,
          required_evidence_json text not null,
          reviewer text not null,
          primary key (run_id, opportunity_id)
        );
        create table if not exists listing_packages (
          run_id text not null,
          opportunity_id text not null,
          title text not null,
          bullets_json text not null,
          description text not null,
          faq_json text not null,
          image_brief text not null,
          status text not null,
          primary key (run_id, opportunity_id)
        );
        create table if not exists channel_submissions (
          run_id text not null,
          opportunity_id text not null,
          channel text not null,
          payload_json text not null,
          validation_status text not null,
          approval_status text not null,
          submit_status text not null,
          notes text not null,
          primary key (run_id, opportunity_id, channel)
        );
        create table if not exists performance_signals (
          run_id text not null,
          opportunity_id text not null,
          views integer not null,
          clicks integer not null,
          orders_count integer not null,
          revenue_krw integer not null,
          cost_krw integer not null,
          returns_count integer not null,
          net_profit_krw integer not null,
          signal_status text not null,
          primary key (run_id, opportunity_id)
        );
        create table if not exists approval_queue (
          approval_id text primary key,
          run_id text not null,
          opportunity_id text not null,
          stage text not null,
          summary text not null,
          requested_by text not null,
          status text not null,
          created_at text not null
        );
        """
    )
    return con


def insert_json(con: sqlite3.Connection, table: str, values: dict) -> None:
    columns = list(values)
    placeholders = ", ".join("?" for _ in columns)
    con.execute(
        f"insert or replace into {table} ({', '.join(columns)}) values ({placeholders})",
        [values[column] for column in columns],
    )


def stage_1_discovery(con: sqlite3.Connection, run_id: str, candidates: list[Candidate]) -> list[dict]:
    discovered = []
    for candidate in candidates:
        score = score_candidate(candidate)
        evidence = {
            "source": "seed_or_external_inbox",
            "source_url": candidate.source_url,
            "demand": candidate.estimated_monthly_demand,
            "competitors": candidate.competitor_count,
            "reviews": candidate.review_count,
            "avg_rating": candidate.avg_rating,
            "scout": "commerce:01_market_scout",
        }
        status = "candidate_found" if score["total"] >= 35 else "weak_signal"
        row = {"candidate": candidate, "score": score, "evidence": evidence, "status": status}
        discovered.append(row)
        insert_json(
            con,
            "product_opportunities",
            {
                "run_id": run_id,
                "opportunity_id": candidate.id,
                "product_name": candidate.product_name,
                "category": candidate.category,
                "source_market": candidate.source_market,
                "target_market": candidate.target_market,
                "evidence_json": json.dumps(evidence, ensure_ascii=False),
                "status": status,
                "created_at": now(),
            },
        )
    return discovered


def stage_2_supplier_validation(con: sqlite3.Connection, run_id: str, rows: list[dict]) -> list[dict]:
    for row in rows:
        c: Candidate = row["candidate"]
        score = row["score"]
        source_is_placeholder = c.source_url.strip().upper() in {"", "SAMPLE", "EXAMPLE"} or "example.com" in c.source_url
        if source_is_placeholder:
            supplier_status = "needs_supplier_evidence"
            evidence_level = "sample_only"
            notes = "공급처 URL/견적/정품 증빙이 없어 Adam 확인 전 게시 불가"
        else:
            supplier_status = "supplier_candidate"
            evidence_level = "url_recorded"
            notes = "공급처 후보 URL이 있어 가격/배송/정품 증빙 추가 확인 필요"
        landed_cost = c.source_price_krw + c.shipping_cost_krw
        row["supplier"] = {
            "supplier_status": supplier_status,
            "evidence_level": evidence_level,
            "landed_cost_krw": landed_cost,
            "expected_margin_krw": score["gross_profit"],
            "margin_rate": score["margin_rate"],
            "notes": notes,
            "analyst": "commerce:02_margin_analyst",
        }
        insert_json(
            con,
            "supplier_evidence",
            {
                "run_id": run_id,
                "opportunity_id": c.id,
                "supplier_status": supplier_status,
                "landed_cost_krw": landed_cost,
                "expected_margin_krw": score["gross_profit"],
                "margin_rate": score["margin_rate"],
                "evidence_level": evidence_level,
                "notes": notes,
            },
        )
    return rows


def stage_3_risk_filter(con: sqlite3.Connection, run_id: str, rows: list[dict]) -> list[dict]:
    for row in rows:
        c: Candidate = row["candidate"]
        score = row["score"]
        hard_stops = []
        required = []
        if score["gross_profit"] <= 0:
            hard_stops.append("예상 마진이 0원 이하")
        if c.certification_risk >= 4:
            hard_stops.append("인증/KC/전기/의료 등 규제 위험 높음")
            required.append("인증 면제 또는 인증서 증빙")
        if c.brand_ip_risk >= 4:
            hard_stops.append("브랜드/IP/캐릭터 권리 위험 높음")
            required.append("상표권/유통권/정품 증빙")
        if c.image_rights_risk >= 4:
            hard_stops.append("이미지 권리 위험 높음")
            required.append("자체 촬영 또는 사용 허가 이미지")
        if c.return_risk >= 5:
            hard_stops.append("반품 위험 과다")
        if c.negative_review_rate >= 0.2:
            required.append("부정 리뷰 원인 분석")

        blocked = bool(hard_stops)
        risk_level = "blocked" if blocked else ("review_required" if required or row["supplier"]["supplier_status"] != "supplier_candidate" else "managed")
        row["risk"] = {
            "risk_level": risk_level,
            "blocked": blocked,
            "hard_stops": hard_stops,
            "required_evidence": required,
            "reviewer": "commerce:03_risk_guardian",
        }
        insert_json(
            con,
            "risk_reviews",
            {
                "run_id": run_id,
                "opportunity_id": c.id,
                "risk_level": risk_level,
                "blocked": 1 if blocked else 0,
                "hard_stops_json": json.dumps(hard_stops, ensure_ascii=False),
                "required_evidence_json": json.dumps(required, ensure_ascii=False),
                "reviewer": "commerce:03_risk_guardian",
            },
        )
    return rows


def make_listing_package(c: Candidate, row: dict) -> dict:
    title = f"{c.product_name} {c.category} 실사용 패키지"
    bullets = [
        f"{c.category} 고객을 위한 실용형 구성",
        "구매 전 사이즈, 구성품, 배송/반품 조건을 확인하도록 안내",
        "타사 상세페이지나 이미지를 복사하지 않고 자체 콘텐츠로 제작",
        f"예상 판매가 {money(c.target_price_krw)} 기준으로 마진 검토 완료",
    ]
    faq = [
        {"q": "구성품은 무엇인가요?", "a": "실제 공급처 확인 후 최종 구성품을 확정합니다."},
        {"q": "배송은 얼마나 걸리나요?", "a": "공급처와 채널 정책 확인 후 최종 안내합니다."},
        {"q": "반품이 가능한가요?", "a": "상품 상태와 채널 반품 정책에 따라 처리합니다."},
    ]
    image_brief = (
        "흰 배경 대표 이미지 1장, 실제 사용 장면 2장, 구성품/사이즈 안내 이미지 1장. "
        "브랜드 로고, 캐릭터, 타사 워터마크, 타사 상세페이지 캡처 사용 금지."
    )
    return {
        "title": title,
        "bullets": bullets,
        "description": f"{c.product_name} 후보의 판매 페이지 초안입니다. 최종 공급처 증빙과 이미지 확보 후 게시 가능합니다.",
        "faq": faq,
        "image_brief": image_brief,
        "status": "blocked" if row["risk"]["blocked"] else "draft_needs_adam_approval",
    }


def stage_4_listing_creation(con: sqlite3.Connection, run_id: str, rows: list[dict]) -> list[dict]:
    for row in rows:
        c: Candidate = row["candidate"]
        listing = make_listing_package(c, row)
        row["listing"] = listing
        insert_json(
            con,
            "listing_packages",
            {
                "run_id": run_id,
                "opportunity_id": c.id,
                "title": listing["title"],
                "bullets_json": json.dumps(listing["bullets"], ensure_ascii=False),
                "description": listing["description"],
                "faq_json": json.dumps(listing["faq"], ensure_ascii=False),
                "image_brief": listing["image_brief"],
                "status": listing["status"],
            },
        )
    return rows


def channel_payloads(c: Candidate, row: dict) -> list[dict]:
    listing = row["listing"]
    common = {
        "sku": f"ADAM-{c.id}",
        "title": listing["title"],
        "price_krw": c.target_price_krw,
        "category": c.category,
        "bullets": listing["bullets"],
        "description": listing["description"],
        "faq": listing["faq"],
        "image_brief": listing["image_brief"],
        "source_evidence": row["evidence"],
        "risk_review": row["risk"],
        "supplier_evidence": row["supplier"],
    }
    return [
        {
            "channel": "coupang",
            "payload": {
                "mode": "draft_only_requires_adam_approval",
                "sellerProductName": common["title"],
                "displayProductName": common["title"],
                "salePrice": common["price_krw"],
                "externalVendorSku": common["sku"],
                "categoryHint": common["category"],
                "content": common,
            },
        },
        {
            "channel": "amazon",
            "payload": {
                "mode": "validation_preview_only_requires_adam_approval",
                "sku": common["sku"],
                "productType": "PRODUCT",
                "requirements": "LISTING",
                "attributes": common,
            },
        },
    ]


def stage_5_channel_packages(con: sqlite3.Connection, run_id: str, rows: list[dict]) -> list[dict]:
    CHANNEL_PENDING.mkdir(parents=True, exist_ok=True)
    for row in rows:
        c: Candidate = row["candidate"]
        submissions = []
        for item in channel_payloads(c, row):
            blocked = row["risk"]["blocked"]
            validation_status = "blocked_by_risk" if blocked else "draft_validated_locally"
            approval_status = "blocked" if blocked else "adam_approval_required"
            submit_status = "not_submitted"
            notes = "Adam 승인 전 실제 채널 게시 금지"
            payload_path = CHANNEL_PENDING / f"{run_id}_{c.id}_{item['channel']}.json"
            payload_path.write_text(json.dumps(item["payload"], ensure_ascii=False, indent=2), encoding="utf-8")
            submission = {
                "channel": item["channel"],
                "payload_path": str(payload_path),
                "validation_status": validation_status,
                "approval_status": approval_status,
                "submit_status": submit_status,
                "notes": notes,
            }
            submissions.append(submission)
            insert_json(
                con,
                "channel_submissions",
                {
                    "run_id": run_id,
                    "opportunity_id": c.id,
                    "channel": item["channel"],
                    "payload_json": json.dumps(item["payload"], ensure_ascii=False),
                    "validation_status": validation_status,
                    "approval_status": approval_status,
                    "submit_status": submit_status,
                    "notes": notes,
                },
            )
        row["submissions"] = submissions
    return rows


def stage_6_performance_tracking(con: sqlite3.Connection, run_id: str, rows: list[dict]) -> list[dict]:
    for row in rows:
        c: Candidate = row["candidate"]
        signal_status = "not_live_pending_adam_approval" if not row["risk"]["blocked"] else "not_live_blocked"
        performance = {
            "views": 0,
            "clicks": 0,
            "orders_count": 0,
            "revenue_krw": 0,
            "cost_krw": 0,
            "returns_count": 0,
            "net_profit_krw": 0,
            "signal_status": signal_status,
            "analyst": "client_ops:04_data_analyst",
        }
        row["performance"] = performance
        insert_json(
            con,
            "performance_signals",
            {
                "run_id": run_id,
                "opportunity_id": c.id,
                **{k: v for k, v in performance.items() if k != "analyst"},
            },
        )
    return rows


def create_approval_queue(con: sqlite3.Connection, run_id: str, rows: list[dict]) -> list[dict]:
    approvals = []
    for row in rows:
        if row["risk"]["blocked"]:
            continue
        c: Candidate = row["candidate"]
        approval = {
            "approval_id": f"{run_id}-{c.id}",
            "run_id": run_id,
            "opportunity_id": c.id,
            "product_name": c.product_name,
            "stage": "channel_publish_gate",
            "summary": (
                f"{c.product_name} / 예상마진 {money(row['score']['gross_profit'])} / "
                f"점수 {row['score']['total']} / {row['supplier']['supplier_status']}"
            ),
            "requested_by": "client_ops:05_coordinator_qa",
            "status": "adam_review_required",
            "created_at": now(),
        }
        approvals.append(approval)
        insert_json(
            con,
            "approval_queue",
            {
                "approval_id": approval["approval_id"],
                "run_id": run_id,
                "opportunity_id": c.id,
                "stage": approval["stage"],
                "summary": approval["summary"],
                "requested_by": approval["requested_by"],
                "status": approval["status"],
                "created_at": approval["created_at"],
            },
        )
    return approvals


def summarize(run_id: str, rows: list[dict], approvals: list[dict]) -> dict:
    blocked = [row for row in rows if row["risk"]["blocked"]]
    pending = [row for row in rows if not row["risk"]["blocked"]]
    supplier_needed = [row for row in pending if row["supplier"]["supplier_status"] != "supplier_candidate"]
    stage_counts = {
        "discovered": len(rows),
        "supplier_checked": len(rows),
        "risk_blocked": len(blocked),
        "listing_drafts": len(rows),
        "channel_packages": sum(len(row["submissions"]) for row in rows),
        "approval_required": len(approvals),
        "performance_trackers": len(rows),
        "supplier_evidence_needed": len(supplier_needed),
    }
    return {
        "run_id": run_id,
        "created_at": now(),
        "status": "approval_required" if approvals else "blocked_or_empty",
        "stage_counts": stage_counts,
        "approval_required": approvals,
        "blocked": [
            {
                "opportunity_id": row["candidate"].id,
                "product_name": row["candidate"].product_name,
                "hard_stops": row["risk"]["hard_stops"],
            }
            for row in blocked
        ],
        "opportunities": [
            {
                "opportunity_id": row["candidate"].id,
                "product_name": row["candidate"].product_name,
                "category": row["candidate"].category,
                "score": row["score"],
                "supplier": row["supplier"],
                "risk": row["risk"],
                "listing_status": row["listing"]["status"],
                "submissions": row["submissions"],
                "performance": row["performance"],
            }
            for row in rows
        ],
    }


def render_report(summary: dict, roster: dict[str, dict]) -> str:
    counts = summary["stage_counts"]
    lines = [
        "# Commerce Growth Pipeline Report",
        "",
        f"- Run ID: {summary['run_id']}",
        f"- Created: {summary['created_at']}",
        f"- Status: {summary['status']}",
        "",
        "## 6단계 진행 현황",
        "",
        f"1. 상품 발굴: {counts['discovered']}건",
        f"2. 공급처/마진 검증: {counts['supplier_checked']}건, 공급처 증빙 필요 {counts['supplier_evidence_needed']}건",
        f"3. 리스크 차단: 차단 {counts['risk_blocked']}건",
        f"4. 판매 페이지 제작: 초안 {counts['listing_drafts']}건",
        f"5. 채널 제출 준비: 패키지 {counts['channel_packages']}개, Adam 승인 대기 {counts['approval_required']}건",
        f"6. 성과 추적: 추적 레코드 {counts['performance_trackers']}건",
        "",
        "## 직급별 담당",
        "",
    ]
    for key in [
        "commerce:01_market_scout",
        "commerce:02_margin_analyst",
        "commerce:03_risk_guardian",
        "commerce:04_listing_builder",
        "commerce:05_ops_manager",
        "client_ops:04_data_analyst",
        "client_ops:05_coordinator_qa",
    ]:
        agent = roster.get(key, {})
        if agent:
            lines.append(f"- {agent['display_name']} {agent['rank']} / {agent['title']}: {agent['primary_stage']}")
    lines.extend(["", "## Adam 승인 대기", ""])
    approvals = summary["approval_required"]
    if not approvals:
        lines.append("- 없음")
    else:
        for item in approvals:
            lines.append(f"- {item['opportunity_id']} / {item['product_name']}: {item['summary']}")
    lines.extend(["", "## 상품별 결과", ""])
    for item in summary["opportunities"]:
        risk = item["risk"]
        supplier = item["supplier"]
        score = item["score"]
        lines.extend(
            [
                f"### {item['opportunity_id']} {item['product_name']}",
                "",
                f"- 카테고리: {item['category']}",
                f"- 총점: {score['total']} / 예상마진: {money(score['gross_profit'])} / 마진율: {score['margin_rate'] * 100:.1f}%",
                f"- 공급처 상태: {supplier['supplier_status']} ({supplier['evidence_level']})",
                f"- 리스크: {risk['risk_level']}",
                f"- 차단 사유: {', '.join(risk['hard_stops']) if risk['hard_stops'] else '없음'}",
                f"- 리스팅: {item['listing_status']}",
                f"- 채널 패키지: {', '.join(sub['channel'] + ':' + sub['approval_status'] for sub in item['submissions'])}",
                f"- 성과 추적: {item['performance']['signal_status']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 운영 원칙",
            "",
            "- 이 파이프라인은 실제 채널 게시를 하지 않는다.",
            "- `approval_status=adam_approval_required`인 항목만 Adam 검토 대상이다.",
            "- 공급처 증빙, 이미지 권리, 인증 문제가 해결되지 않으면 승인해도 라이브 게시 단계로 넘기면 안 된다.",
        ]
    )
    return "\n".join(lines) + "\n"


def run() -> dict:
    run_id = "GROWTH-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    roster = load_roster()
    con = connect_db()
    try:
        candidates = load_candidates()
        rows = stage_1_discovery(con, run_id, candidates)
        rows = stage_2_supplier_validation(con, run_id, rows)
        rows = stage_3_risk_filter(con, run_id, rows)
        rows = stage_4_listing_creation(con, run_id, rows)
        rows = stage_5_channel_packages(con, run_id, rows)
        rows = stage_6_performance_tracking(con, run_id, rows)
        approvals = create_approval_queue(con, run_id, rows)
        summary = summarize(run_id, rows, approvals)
        insert_json(
            con,
            "pipeline_runs",
            {
                "run_id": run_id,
                "created_at": summary["created_at"],
                "status": summary["status"],
                "summary_json": json.dumps(summary, ensure_ascii=False),
            },
        )
        con.commit()
    finally:
        con.close()

    PIPELINE_RUNTIME.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    run_json = PIPELINE_RUNTIME / f"{run_id}.json"
    run_report = PIPELINE_RUNTIME / f"{run_id}.md"
    report = render_report(summary, roster)
    run_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    LATEST_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    run_report.write_text(report, encoding="utf-8")
    LATEST_REPORT.write_text(report, encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the six-stage commerce growth pipeline.")
    parser.add_argument("--json", action="store_true", help="Print full JSON summary.")
    args = parser.parse_args()
    summary = run()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        counts = summary["stage_counts"]
        print(f"Generated growth run: {summary['run_id']}")
        print(f"Approval required: {counts['approval_required']}")
        print(f"Risk blocked: {counts['risk_blocked']}")
        print(f"Report: {LATEST_REPORT}")
        print(f"DB: {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
