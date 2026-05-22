from __future__ import annotations

import argparse
import base64
import hmac
import html
import json
import os
import shutil
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DASHBOARD_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
CLIENT_OPS_ROOT = ROOT.parent / "client-ops-team"
ASSETS = DASHBOARD_DIR / "assets"
REPORTS = ROOT / "reports"
CLIENT_OPS_REPORTS = CLIENT_OPS_ROOT / "reports"
WORKFORCE = ROOT / "workforce"
RUNS = WORKFORCE / "runs"
RUNTIME = ROOT / "runtime"
LLM_USAGE_LOG = RUNTIME / "llm_usage.jsonl"
CLIENT_OPS_HANDOFFS = RUNTIME / "client_ops_handoffs"
CLIENT_OPS_LOGS = CLIENT_OPS_ROOT / "logs"
APPROVALS_PATH = RUNTIME / "approval_decisions.json"
APPROVAL_LOG = RUNTIME / "approval_log.jsonl"
REPO_ROOT = ROOT.parents[1]
ROSTER_PATH = REPO_ROOT / "shared" / "organization" / "agent_roster.json"
GROWTH_PIPELINE_SUMMARY = RUNTIME / "growth_pipeline" / "latest.json"
GROWTH_PIPELINE_REPORT = REPORTS / "latest_growth_pipeline.md"
PIPELINE_APPROVALS_PATH = RUNTIME / "growth_pipeline_approval_decisions.json"
PIPELINE_APPROVAL_LOG = RUNTIME / "growth_pipeline_approval_log.jsonl"
CHANNEL_READINESS_SUMMARY = RUNTIME / "channel_readiness" / "latest.json"
CHANNEL_READINESS_REPORT = REPORTS / "latest_channel_readiness.md"
CHANNEL_VALIDATION_SUMMARY = RUNTIME / "channel_submissions" / "latest_validation.json"
CHANNEL_VALIDATION_REPORT = REPORTS / "latest_channel_validation.md"

COMMERCE_AGENTS = [
    ("01_market_scout", "시장 탐색가", "상품 기회 발굴", "수요 신호와 카테고리 후보를 찾습니다."),
    ("02_margin_analyst", "마진 분석가", "수익성 검토", "원가, 판매가, 경쟁 강도, 리뷰 신호를 계산합니다."),
    ("03_risk_guardian", "리스크 감시자", "위험 차단", "인증, 지식재산권, 이미지 권리, 반품 리스크를 막습니다."),
    ("04_listing_builder", "리스팅 작성자", "판매 페이지 초안", "상품명, 상세페이지 구조, FAQ, 금지 표현을 정리합니다."),
    ("05_ops_manager", "운영 관리자", "최종 판단", "진행/검토/보류 결론과 다음 액션을 조율합니다."),
]

CLIENT_OPS_AGENTS = [
    ("01_onboarding_manager", "김은보", "온보딩 매니저", "신규 고객 정보 수집, 계약/권한 확인, 셋업 검수 handoff를 맡습니다."),
    ("02_ops_operator", "박실행", "운영 오퍼레이터", "정기 자동화 실행, 로그 기록, 실패 재시도와 알림을 담당합니다."),
    ("03_cs_manager", "이용대", "CS 매니저", "고객 문의 1차 응대, 응대 초안, 에스컬레이션 판단을 맡습니다."),
    ("04_data_analyst", "최분석", "데이터 애널리스트", "주간 성과 분석, KPI 비교, 리포트 초안을 작성합니다."),
    ("05_coordinator_qa", "정총괄", "코디네이터 / QA", "4명의 산출물 검수, 일정 조율, 오류 모니터링을 총괄합니다."),
]

AGENTS = COMMERCE_AGENTS
COMPANY_AGENTS = [
    ("commerce", agent_id, title, role, description)
    for agent_id, title, role, description in COMMERCE_AGENTS
] + [
    ("client_ops", agent_id, title, role, description)
    for agent_id, title, role, description in CLIENT_OPS_AGENTS
]
TEAM_LABELS = {
    "commerce": "커머스 발굴 검수팀",
    "client_ops": "클라이언트 운영팀",
}
OFFICE_SEATS = {
    "client_ops:01_onboarding_manager": ("47.0%", "42.0%"),
    "client_ops:02_ops_operator": ("57.3%", "42.0%"),
    "client_ops:03_cs_manager": ("67.7%", "42.0%"),
    "client_ops:04_data_analyst": ("78.0%", "42.0%"),
    "client_ops:05_coordinator_qa": ("88.3%", "42.0%"),
    "commerce:01_market_scout": ("47.0%", "73.5%"),
    "commerce:02_margin_analyst": ("57.3%", "73.5%"),
    "commerce:03_risk_guardian": ("67.7%", "73.5%"),
    "commerce:04_listing_builder": ("78.0%", "73.5%"),
    "commerce:05_ops_manager": ("88.3%", "73.5%"),
}

OFFICE_LAYOUT = {
    "01_market_scout": {
        "room": "리서치룸",
        "area": "scout",
        "desk": "market",
        "status": "검색중",
        "focus": "상품 후보 발굴",
    },
    "02_margin_analyst": {
        "room": "분석실",
        "area": "analyst",
        "desk": "numbers",
        "status": "계산중",
        "focus": "마진과 경쟁 강도",
    },
    "03_risk_guardian": {
        "room": "검수실",
        "area": "risk",
        "desk": "risk",
        "status": "검토중",
        "focus": "인증/IP/반품 리스크",
    },
    "04_listing_builder": {
        "room": "콘텐츠룸",
        "area": "listing",
        "desk": "copy",
        "status": "작성중",
        "focus": "상세페이지 초안",
    },
    "05_ops_manager": {
        "room": "운영실",
        "area": "ops",
        "desk": "approval",
        "status": "승인대기",
        "focus": "최종 판단과 다음 액션",
    },
    "01_onboarding_manager": {
        "room": "온보딩룸",
        "area": "onboarding",
        "desk": "approval",
        "status": "셋업검수",
        "focus": "고객 정보와 권한 확인",
    },
    "02_ops_operator": {
        "room": "자동화실",
        "area": "operator",
        "desk": "numbers",
        "status": "정시실행",
        "focus": "예약 작업과 실패 재시도",
    },
    "03_cs_manager": {
        "room": "CS룸",
        "area": "cs",
        "desk": "copy",
        "status": "응대검토",
        "focus": "문의 초안과 에스컬레이션",
    },
    "04_data_analyst": {
        "room": "리포트실",
        "area": "data",
        "desk": "numbers",
        "status": "분석중",
        "focus": "KPI와 주간 리포트",
    },
    "05_coordinator_qa": {
        "room": "QA 총괄실",
        "area": "qa",
        "desk": "risk",
        "status": "최종검수",
        "focus": "산출물 검수와 일정 조율",
    },
}


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_text(path: Path, fallback: str = "") -> str:
    if not path.exists():
        return fallback
    return path.read_text(encoding="utf-8", errors="replace")


def read_json_file(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return fallback


def agent_roster() -> list[dict]:
    payload = read_json_file(ROSTER_PATH, {"agents": []})
    agents = payload.get("agents", [])
    return agents if isinstance(agents, list) else []


def agent_profile(team: str, agent_id: str) -> dict:
    for item in agent_roster():
        if item.get("team") == team and item.get("agent_id") == agent_id:
            return item
    return {}


def latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = [p for p in directory.glob(pattern) if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def list_runs() -> list[Path]:
    if not RUNS.exists():
        return []
    return sorted([p for p in RUNS.iterdir() if p.is_dir()], reverse=True)


def read_run_metadata(run_dir: Path) -> dict:
    path = run_dir / "metadata.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def agent_outbox_count(agent_id: str) -> int:
    outbox = WORKFORCE / "agents" / agent_id / "outbox"
    if not outbox.exists():
        return 0
    return len([p for p in outbox.iterdir() if p.is_file() and p.suffix == ".md"])


def env_summary() -> dict[str, str]:
    return {
        "provider": os.getenv("LLM_PROVIDER", "mock") or "mock",
        "base_url": os.getenv("OPENAI_BASE_URL", ""),
        "dashboard_auth": "켜짐" if os.getenv("DASHBOARD_USERNAME") and os.getenv("DASHBOARD_PASSWORD") else "꺼짐",
    }


def disk_summary() -> dict[str, str]:
    total, used, free = shutil.disk_usage(ROOT)
    used_pct = round((used / total) * 100, 1) if total else 0
    return {
        "used_pct": f"{used_pct}%",
        "free_gb": f"{free / (1024 ** 3):.1f} GB",
        "total_gb": f"{total / (1024 ** 3):.1f} GB",
    }


def llm_usage_summary() -> dict[str, str]:
    if not LLM_USAGE_LOG.exists():
        return {"ok": "0", "error": "0", "tokens": "0", "latest": "none"}

    events = []
    for line in LLM_USAGE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    ok = sum(1 for event in events if event.get("status") == "ok")
    error = sum(1 for event in events if event.get("status") == "error")
    tokens = sum(int(event.get("total_tokens") or 0) for event in events)
    latest = events[-1].get("created_at", "none") if events else "none"
    return {"ok": str(ok), "error": str(error), "tokens": str(tokens), "latest": str(latest)}


def handoff_summary() -> dict[str, str]:
    if not CLIENT_OPS_HANDOFFS.exists():
        return {"received": "0", "task_log": "없음"}
    received = len([p for p in CLIENT_OPS_HANDOFFS.glob("*.json") if p.is_file()])
    task_log = "있음" if (CLIENT_OPS_HANDOFFS / "commerce_tasks.md").exists() else "없음"
    return {"received": str(received), "task_log": task_log}


def client_ops_log_events() -> list[dict]:
    if not CLIENT_OPS_LOGS.exists():
        return []

    events = []
    for path in sorted(CLIENT_OPS_LOGS.glob("*.jsonl")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events[-500:]


def client_ops_agent_events(agent_id: str) -> list[dict]:
    return [event for event in client_ops_log_events() if event.get("agent_id") == agent_id]


def client_ops_activity_count(agent_id: str) -> int:
    return len(client_ops_agent_events(agent_id))


def client_ops_event_tone(event: dict | None) -> str:
    if not event:
        return "muted"
    text = f"{event.get('decision', '')} {event.get('summary', '')}".upper()
    if any(keyword in text for keyword in ("FAIL", "ERROR", "BLOCK", "ESCALATION", "P0", "REJECT")):
        return "danger"
    if any(keyword in text for keyword in ("READY", "REVIEW", "IN_PROGRESS", "WAIT", "PENDING")):
        return "warn"
    return "good"


def load_approval_decisions() -> dict[str, dict]:
    if not APPROVALS_PATH.exists():
        return {}
    try:
        payload = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_approval_decisions(decisions: dict[str, dict]) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")


def approval_for_run(run_id: str) -> dict:
    return load_approval_decisions().get(run_id, {})


def approval_label(status: str) -> str:
    labels = {
        "approved": "승인됨",
        "rejected": "반려됨",
        "canceled": "취소됨",
        "pending": "미확인",
    }
    return labels.get(status, "미확인")


def approval_tone(status: str) -> str:
    tones = {
        "approved": "good",
        "rejected": "danger",
        "canceled": "muted",
        "pending": "warn",
    }
    return tones.get(status, "warn")


def latest_approval_decision() -> dict:
    decisions = load_approval_decisions()
    if not decisions:
        return {}
    return max(decisions.values(), key=lambda item: str(item.get("decided_at", "")))


def record_approval(run_id: str, action: str, note: str) -> None:
    actions = {
        "approve": "approved",
        "reject": "rejected",
        "cancel": "canceled",
    }
    if action not in actions:
        raise ValueError("unsupported approval action")

    clean_run_id = Path(run_id).name
    if not clean_run_id:
        raise ValueError("missing run id")
    if not (RUNS / clean_run_id).is_dir():
        raise ValueError("unknown run id")

    decision = {
        "run_id": clean_run_id,
        "status": actions[action],
        "label": approval_label(actions[action]),
        "note": note.strip()[:1000],
        "decided_by": "adam_dashboard",
        "decided_at": datetime.now().isoformat(timespec="seconds"),
    }
    decisions = load_approval_decisions()
    decisions[clean_run_id] = decision
    save_approval_decisions(decisions)

    RUNTIME.mkdir(parents=True, exist_ok=True)
    with APPROVAL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False))
        f.write("\n")


def agent_opinion_summary(agent_id: str, run_dir: Path | None) -> str:
    if not run_dir:
        return "아직 실행 산출물이 없습니다."
    report = read_text(run_dir / f"{agent_id}.md", "")
    if not report:
        return "이 에이전트의 의견서가 아직 없습니다."
    lines = [line.strip("#- |") for line in report.splitlines() if line.strip()]
    summary = " ".join(lines[:4])
    return summary[:180] + ("..." if len(summary) > 180 else "")


def company_agent_state(team: str, agent_id: str, latest_run: Path | None) -> dict[str, str]:
    if team == "commerce":
        state = agent_run_state(agent_id, latest_run)
        return {**state, "unit": "산출물"}

    events = client_ops_agent_events(agent_id)
    if not events:
        return {"label": "대기", "tone": "muted", "outbox": "0", "unit": "로그"}

    latest_event = events[-1]
    label = str(latest_event.get("decision") or latest_event.get("step") or "활동")
    return {
        "label": label[:18],
        "tone": client_ops_event_tone(latest_event),
        "outbox": str(len(events)),
        "unit": "로그",
    }


def company_agent_opinion_summary(team: str, agent_id: str, latest_run: Path | None) -> str:
    if team == "commerce":
        return agent_opinion_summary(agent_id, latest_run)

    events = client_ops_agent_events(agent_id)
    if not events:
        return "운영 로그는 아직 없지만 페르소나, 업무 범위, 출력 템플릿은 준비되어 있습니다."

    latest_event = events[-1]
    decision = str(latest_event.get("decision") or "활동")
    summary = str(latest_event.get("summary") or "최근 활동 요약이 없습니다.")
    text = f"{decision}: {summary}"
    return text[:180] + ("..." if len(text) > 180 else "")


def client_ops_agent_report(agent_id: str) -> str:
    events = client_ops_agent_events(agent_id)
    if not events:
        return "아직 운영 로그가 없습니다. 페르소나와 업무 템플릿은 준비되어 있습니다."

    lines = []
    for event in events[-8:]:
        day = event.get("day", "-")
        step = event.get("step", "unknown-step")
        decision = event.get("decision", "unknown")
        summary = event.get("summary", "")
        provider = (event.get("llm") or {}).get("provider", "unknown")
        lines.append(f"- Day {day} / {step} / {decision} / {provider}\n  {summary}")
    return "\n".join(lines)


def report_metric(report: str, key: str, fallback: str = "0") -> str:
    for line in report.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(f"- {key.lower()}:"):
            return stripped.split(":", 1)[1].strip()
    return fallback


def preflight_report_summary() -> dict[str, str]:
    path = latest_file(CLIENT_OPS_REPORTS, "preflight_*.md")
    report = read_text(path, "아직 preflight 리포트가 없습니다.") if path else "아직 preflight 리포트가 없습니다."
    status = report_metric(report, "Status", "보고서 없음")
    return {
        "path": path.name if path else "없음",
        "report": report,
        "pass": report_metric(report, "PASS"),
        "fail": report_metric(report, "FAIL"),
        "warn": report_metric(report, "WARN"),
        "skip": report_metric(report, "SKIP_MANUAL"),
        "status": status,
        "tone": "good" if "READY FOR BETA" in status else ("danger" if "NOT READY" in status else "warn"),
    }


def mock_real_report_summary() -> dict[str, str]:
    path = CLIENT_OPS_REPORTS / "mock_vs_real_diff.md"
    report = read_text(path, "아직 mock vs real 비교 리포트가 없습니다.")
    blocking = report_metric(report, "BLOCKING")
    warn = report_metric(report, "WARN")
    skip = report_metric(report, "SKIP")
    tone = "good" if blocking == "0" and warn == "0" else ("danger" if blocking != "0" else "warn")
    return {
        "path": path.name if path.exists() else "없음",
        "report": report,
        "blocking": blocking,
        "warn": warn,
        "skip": skip,
        "tone": tone,
    }


def growth_pipeline_summary() -> dict:
    return read_json_file(
        GROWTH_PIPELINE_SUMMARY,
        {
            "run_id": "없음",
            "created_at": "아직 실행 기록이 없습니다.",
            "status": "not_started",
            "stage_counts": {
                "discovered": 0,
                "supplier_checked": 0,
                "risk_blocked": 0,
                "listing_drafts": 0,
                "channel_packages": 0,
                "approval_required": 0,
                "performance_trackers": 0,
                "supplier_evidence_needed": 0,
            },
            "approval_required": [],
            "blocked": [],
            "opportunities": [],
        },
    )


def load_pipeline_approvals() -> dict[str, dict]:
    payload = read_json_file(PIPELINE_APPROVALS_PATH, {})
    return payload if isinstance(payload, dict) else {}


def save_pipeline_approvals(decisions: dict[str, dict]) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    PIPELINE_APPROVALS_PATH.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")


def record_pipeline_approval(approval_id: str, action: str, note: str) -> None:
    actions = {
        "approve": "approved_for_manual_publish",
        "reject": "rejected",
        "hold": "hold_for_more_evidence",
    }
    if action not in actions:
        raise ValueError("unsupported pipeline approval action")
    clean_id = Path(approval_id).name
    summary = growth_pipeline_summary()
    valid_ids = {str(item.get("approval_id", "")) for item in summary.get("approval_required", [])}
    if clean_id not in valid_ids:
        raise ValueError("unknown pipeline approval id")

    decision = {
        "approval_id": clean_id,
        "status": actions[action],
        "note": note.strip()[:1000],
        "decided_by": "adam_dashboard",
        "decided_at": datetime.now().isoformat(timespec="seconds"),
    }
    decisions = load_pipeline_approvals()
    decisions[clean_id] = decision
    save_pipeline_approvals(decisions)

    RUNTIME.mkdir(parents=True, exist_ok=True)
    with PIPELINE_APPROVAL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False))
        f.write("\n")


def pipeline_decision_label(approval_id: str) -> str:
    decision = load_pipeline_approvals().get(approval_id)
    if not decision:
        return "Adam 승인 대기"
    labels = {
        "approved_for_manual_publish": "수동 게시 승인",
        "rejected": "반려",
        "hold_for_more_evidence": "증빙 보류",
    }
    return labels.get(str(decision.get("status", "")), "결정 기록됨")


def render_growth_summary_cards() -> str:
    summary = growth_pipeline_summary()
    counts = summary.get("stage_counts", {})
    return f"""
      <section class="decision-cards">
        <a class="decision-card" href="/growth-pipeline">
          <h2>6단계 파이프라인</h2>
          <div class="metric decision-status">{html.escape(str(summary.get("status", "not_started")))}</div>
          <p class="muted">{html.escape(str(summary.get("run_id", "없음")))} / {html.escape(str(summary.get("created_at", "")))}</p>
        </a>
        <a class="decision-card" href="/growth-pipeline">
          <h2>게시 승인 대기</h2>
          <div class="metric">{html.escape(str(counts.get("approval_required", 0)))}</div>
          <p class="muted">쿠팡/아마존 제출 패키지는 Adam 승인 전 게시되지 않습니다.</p>
        </a>
        <a class="decision-card" href="/growth-pipeline">
          <h2>리스크 차단</h2>
          <div class="metric">{html.escape(str(counts.get("risk_blocked", 0)))}</div>
          <p class="muted">인증, IP, 이미지 권리, 마진 문제로 자동 차단된 후보입니다.</p>
        </a>
      </section>
    """


def channel_readiness_summary() -> dict:
    return read_json_file(
        CHANNEL_READINESS_SUMMARY,
        {
            "created_at": "아직 점검 기록이 없습니다.",
            "status": "not_started",
            "config_source": "none",
            "blocking_count": 0,
            "channels": {},
            "checks": [],
        },
    )


def channel_validation_summary() -> dict:
    return read_json_file(
        CHANNEL_VALIDATION_SUMMARY,
        {
            "created_at": "아직 검증 기록이 없습니다.",
            "status": "not_started",
            "growth_run_id": "none",
            "submission_count": 0,
            "blocking": 0,
            "warn": 0,
            "info": 0,
            "findings": [],
        },
    )


def render_channel_summary_cards() -> str:
    readiness = channel_readiness_summary()
    validation = channel_validation_summary()
    readiness_tone = "good" if readiness.get("status") == "ready" else ("danger" if readiness.get("status") == "unsafe_config" else "warn")
    validation_tone = "good" if validation.get("status") == "valid" else ("danger" if validation.get("status") == "invalid" else "warn")
    return f"""
      <section class="decision-cards">
        <a class="decision-card" href="/channel-ops">
          <h2>판매자 계정 준비</h2>
          <div class="metric decision-status">{html.escape(str(readiness.get("status", "not_started")))}</div>
          <p class="muted">설정: {html.escape(str(readiness.get("config_source", "none")))} / 미완료 {html.escape(str(readiness.get("blocking_count", 0)))}</p>
        </a>
        <a class="decision-card" href="/channel-ops">
          <h2>채널 Dry-run</h2>
          <div class="metric decision-status">{html.escape(str(validation.get("status", "not_started")))}</div>
          <p class="muted">패키지 {html.escape(str(validation.get("submission_count", 0)))}개 / BLOCK {html.escape(str(validation.get("blocking", 0)))}</p>
        </a>
        <a class="decision-card" href="/channel-ops">
          <h2>라이브 게시</h2>
          <div class="metric decision-status">잠금</div>
          <p class="muted">Adam 승인과 API 키 연결 전에는 실제 게시하지 않습니다.</p>
        </a>
      </section>
    """


def render_approval_summary_cards(latest_run: Path | None, latest_meta: dict) -> str:
    run_id = str(latest_meta.get("run_id", latest_run.name if latest_run else ""))
    decision = approval_for_run(run_id) if run_id else {}
    status = str(decision.get("status", "pending" if latest_run else "canceled"))
    pending_count = "1" if latest_run and status == "pending" else "0"
    opinions_count = str(len(COMPANY_AGENTS))
    latest_decision = latest_approval_decision()
    latest_label = latest_decision.get("label", "기록 없음")
    latest_time = latest_decision.get("decided_at", "아직 결재 기록이 없습니다.")

    return f"""
      <section class="decision-cards">
        <a class="decision-card" href="/approvals">
          <h2>미확인 결재</h2>
          <div class="metric">{html.escape(pending_count)}</div>
          <p class="muted">최신 실행의 최종 진행 여부를 Adam이 승인합니다.</p>
        </a>
        <a class="decision-card" href="/opinions">
          <h2>직원들 의견서</h2>
          <div class="metric">{html.escape(opinions_count)}</div>
          <p class="muted">각 에이전트가 남긴 산출물과 판단 근거입니다.</p>
        </a>
        <a class="decision-card" href="/approvals">
          <h2>마지막 결재</h2>
          <div class="metric decision-status">{html.escape(str(latest_label))}</div>
          <p class="muted">{html.escape(str(latest_time))}</p>
        </a>
      </section>
    """


def render_approval_panel(latest_run: Path | None, latest_meta: dict) -> str:
    if not latest_run:
        return """
          <section class="panel approval-panel">
            <h2>최종 결재 센터</h2>
            <p class="muted">아직 결재할 실행 결과가 없습니다.</p>
          </section>
        """

    run_id = str(latest_meta.get("run_id", latest_run.name))
    decision = approval_for_run(run_id)
    status = str(decision.get("status", "pending"))
    report = read_text(REPORTS / "latest_agent_run.md", "")
    brief = " ".join(line.strip("#- ") for line in report.splitlines() if line.strip())[:360]
    if not brief:
        brief = "최신 최종 보고서가 아직 비어 있습니다."

    return f"""
      <section class="panel approval-panel">
        <div class="section-head">
          <div>
            <h2>최종 결재 센터</h2>
            <p class="muted">승인은 내부 결정 기록만 남깁니다. 자동 게시나 자동 결제는 실행하지 않습니다.</p>
          </div>
          <span class="badge {approval_tone(status)}">{html.escape(approval_label(status))}</span>
        </div>
        <div class="approval-body">
          <div>
            <div class="kv"><span>대상 실행</span><strong>{html.escape(run_id)}</strong></div>
            <div class="kv"><span>생성 시각</span><strong>{html.escape(str(latest_meta.get("created_at", "unknown")))}</strong></div>
            <p class="approval-brief">{html.escape(brief)}</p>
          </div>
          <form class="approval-form" method="post" action="/approval">
            <input type="hidden" name="run_id" value="{html.escape(run_id)}">
            <label for="approval-note">결재 메모</label>
            <textarea id="approval-note" name="note" rows="3" placeholder="예: 샘플 확인 후 진행, 소싱처 부족으로 반려 등">{html.escape(str(decision.get("note", "")))}</textarea>
            <div class="approval-actions">
              <button class="action approve" type="submit" name="action" value="approve">승인</button>
              <button class="action reject" type="submit" name="action" value="reject">반려</button>
              <button class="action cancel" type="submit" name="action" value="cancel">취소</button>
            </div>
          </form>
        </div>
      </section>
    """


def render_opinion_cards(latest_run: Path | None) -> str:
    cards = []
    for team, agent_id, title, role, _description in COMPANY_AGENTS:
        summary = company_agent_opinion_summary(team, agent_id, latest_run)
        cards.append(
            f"""
            <article class="opinion-card">
              <h3>{html.escape(title)}</h3>
              <p class="muted">{html.escape(TEAM_LABELS[team])} · {html.escape(role)}</p>
              <p>{html.escape(summary)}</p>
            </article>
            """
        )
    return '<section class="opinion-grid">' + "".join(cards) + "</section>"


def agent_run_state(agent_id: str, latest_run: Path | None) -> dict[str, str]:
    outbox_count = agent_outbox_count(agent_id)
    if latest_run and (latest_run / f"{agent_id}.md").exists():
        return {"label": "완료", "tone": "good", "outbox": str(outbox_count)}
    if outbox_count:
        return {"label": "기록 있음", "tone": "warn", "outbox": str(outbox_count)}
    return {"label": "대기", "tone": "muted", "outbox": "0"}


def render_flow_nodes(team: str, agents: list[tuple[str, str, str, str]], latest_run: Path | None) -> str:
    nodes = []
    for index, (agent_id, title, role, description) in enumerate(agents, start=1):
        state = company_agent_state(team, agent_id, latest_run)
        nodes.append(
            f"""
            <div class="agent-node {html.escape(state["tone"])}">
              <div class="node-step">{index:02d}</div>
              <h3>{html.escape(title)}</h3>
              <p class="node-role">{html.escape(role)}</p>
              <p class="node-desc">{html.escape(description)}</p>
              <div class="node-meta">
                <span class="badge {html.escape(state["tone"])}">{html.escape(state["label"])}</span>
                <span>{html.escape(state["unit"])} {html.escape(state["outbox"])}개</span>
              </div>
            </div>
            """
        )
        if index < len(agents):
            nodes.append('<div class="flow-arrow" aria-hidden="true">&rarr;</div>')
    return "".join(nodes)


def render_agent_flow(latest_run: Path | None) -> str:
    client_nodes = render_flow_nodes("client_ops", CLIENT_OPS_AGENTS, latest_run)
    commerce_nodes = render_flow_nodes("commerce", COMMERCE_AGENTS, latest_run)

    return f"""
      <section class="panel agent-map">
        <div class="section-head">
          <div>
            <h2>에이전트 운영 흐름</h2>
            <p class="muted">클라이언트 운영팀 5명과 커머스 발굴 검수팀 5명이 각각의 업무 흐름을 맡습니다.</p>
          </div>
        </div>
        <div class="flow-lane">
          <div class="flow-lane-head">
            <strong>클라이언트 운영팀</strong>
            <span class="muted">고객 온보딩, 자동화 실행, CS, 리포트, QA</span>
          </div>
          <div class="agent-flow">{client_nodes}</div>
        </div>
        <div class="flow-lane">
          <div class="flow-lane-head">
            <strong>커머스 발굴 검수팀</strong>
            <span class="muted">상품 발굴, 마진 분석, 리스크 차단, 리스팅, 최종 판단</span>
          </div>
          <div class="agent-flow">{commerce_nodes}</div>
        </div>
      </section>
    """


def render_security_panel() -> str:
    env = env_summary()
    env_file = "있음" if (ROOT / ".env").exists() else "없음"
    auth_tone = "good" if env["dashboard_auth"] == "켜짐" else "danger"
    provider_tone = "good" if env["provider"] != "mock" else "warn"
    return f"""
      <section class="panel">
        <h2>보안/운영 체크</h2>
        <div class="check-row">
          <span>대시보드 로그인</span>
          <strong class="badge {auth_tone}">{html.escape(env["dashboard_auth"])}</strong>
        </div>
        <div class="check-row">
          <span>LLM 모드</span>
          <strong class="badge {provider_tone}">{html.escape(env["provider"])}</strong>
        </div>
        <div class="check-row">
          <span>서버 .env</span>
          <strong>{env_file}</strong>
        </div>
        <div class="check-row">
          <span>퍼블릭 GitHub</span>
          <strong>비밀값 제외</strong>
        </div>
        <div class="check-row">
          <span>8080 접근</span>
          <strong>IP 제한 유지</strong>
        </div>
      </section>
    """


def render_health_panel() -> str:
    env = env_summary()
    disk = disk_summary()
    usage = llm_usage_summary()
    handoff = handoff_summary()
    run_count = len(list_runs())
    client_log_count = sum(client_ops_activity_count(agent_id) for agent_id, *_rest in CLIENT_OPS_AGENTS)
    return f"""
      <section class="panel">
        <h2>시스템 상태</h2>
        <div class="kv"><span>LLM 제공자</span><strong>{html.escape(env["provider"])}</strong></div>
        <div class="kv"><span>대시보드 인증</span><strong>{html.escape(env["dashboard_auth"])}</strong></div>
        <div class="kv"><span>등록 직원</span><strong>{len(COMPANY_AGENTS)}</strong></div>
        <div class="kv"><span>저장된 실행</span><strong>{run_count}</strong></div>
        <div class="kv"><span>Client Ops 로그</span><strong>{client_log_count}</strong></div>
        <div class="kv"><span>수신 handoff</span><strong>{html.escape(handoff["received"])}</strong></div>
        <div class="kv"><span>handoff 작업 로그</span><strong>{html.escape(handoff["task_log"])}</strong></div>
        <div class="kv"><span>디스크 사용률</span><strong>{html.escape(disk["used_pct"])}</strong></div>
        <div class="kv"><span>남은 디스크</span><strong>{html.escape(disk["free_gb"])}</strong></div>
        <div class="kv"><span>LLM 성공/오류</span><strong>{html.escape(usage["ok"])}/{html.escape(usage["error"])}</strong></div>
        <div class="kv"><span>최근 토큰</span><strong>{html.escape(usage["tokens"])}</strong></div>
      </section>
    """


def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #697586;
      --line: #d9e0e8;
      --accent: #0f766e;
      --accent-2: #8a5a13;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
      line-height: 1.5;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    .wrap {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 68px;
      gap: 16px;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      letter-spacing: 0;
    }}
    nav {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    nav a, .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      padding: 0 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      text-decoration: none;
      font-size: 14px;
    }}
    main {{
      padding: 24px 0 36px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 132px;
    }}
    .card h2, .panel h2 {{
      margin: 0 0 8px;
      font-size: 15px;
      letter-spacing: 0;
    }}
    .card p {{
      margin: 0;
    }}
    .muted,
    .card p,
    .team-heading p,
    .node-desc,
    .office-status span {{
      overflow-wrap: anywhere;
    }}
    .card-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 6px;
    }}
    .card-head h2 {{
      margin-bottom: 0;
    }}
    .team-chip {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 0 7px;
      border-radius: 999px;
      background: #eef7f5;
      color: var(--accent);
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .agent-card {{
      display: grid;
      grid-template-rows: auto auto auto 1fr auto;
      gap: 6px;
      min-height: 190px;
    }}
    .team-client_ops .team-chip {{
      background: #eef2fb;
      color: #365f91;
    }}
    .card-foot {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-top: 6px;
      font-size: 12px;
    }}
    .metric {{
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
    }}
    .metric.run-id {{
      font-size: 16px;
      overflow-wrap: anywhere;
      line-height: 1.35;
    }}
    .decision-cards {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .decision-card {{
      display: block;
      min-height: 132px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--text);
      text-decoration: none;
    }}
    .decision-card h2 {{
      margin: 0 0 8px;
      font-size: 15px;
    }}
    .decision-status {{
      font-size: 21px;
      line-height: 1.3;
    }}
    .approval-panel {{
      margin-top: 16px;
    }}
    .team-section {{
      margin-top: 16px;
    }}
    .team-heading {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .team-heading h2 {{
      margin: 0 0 2px;
      font-size: 17px;
    }}
    .team-heading p {{
      margin: 0;
    }}
    .team-count {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 46px;
      min-height: 30px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--accent);
      font-weight: 700;
      white-space: nowrap;
    }}
    .team-grid {{
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    }}
    .approval-body {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 16px;
      align-items: start;
    }}
    .approval-brief {{
      margin: 12px 0 0;
      color: var(--text);
      font-size: 13px;
      line-height: 1.6;
    }}
    .approval-form {{
      display: grid;
      gap: 8px;
    }}
    .approval-form label {{
      font-size: 13px;
      font-weight: 700;
    }}
    .approval-form textarea {{
      width: 100%;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      color: var(--text);
      font-family: inherit;
      font-size: 13px;
    }}
    .approval-actions {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }}
    .action {{
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: #fff;
      font-family: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .action.approve {{
      background: #047857;
      border-color: #047857;
    }}
    .action.reject {{
      background: #b42318;
      border-color: #b42318;
    }}
    .action.cancel {{
      background: #64748b;
      border-color: #64748b;
    }}
    .opinion-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .opinion-card {{
      min-height: 150px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    .opinion-card h3 {{
      margin: 0 0 6px;
      font-size: 15px;
    }}
    .opinion-card p {{
      margin: 0 0 8px;
      font-size: 13px;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    .data-table th,
    .data-table td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 6px;
      text-align: left;
      vertical-align: top;
    }}
    .data-table th {{
      color: var(--muted);
      font-weight: 700;
      background: #f8fafc;
    }}
    .muted {{
      color: var(--muted);
      font-size: 13px;
    }}
    .panels {{
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 16px;
      margin-top: 18px;
      align-items: start;
    }}
    .ops-panels {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 16px;
      margin-top: 18px;
      align-items: start;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }}
    .section-head h2 {{
      margin-bottom: 2px;
    }}
    .agent-map {{
      margin-top: 16px;
    }}
    .agent-flow {{
      display: flex;
      align-items: stretch;
      gap: 10px;
      overflow-x: auto;
      padding-bottom: 2px;
    }}
    .flow-lane {{
      display: grid;
      gap: 10px;
    }}
    .flow-lane + .flow-lane {{
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }}
    .flow-lane-head {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
    }}
    .flow-lane-head strong {{
      font-size: 14px;
    }}
    .agent-node {{
      flex: 1 0 180px;
      min-width: 180px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
      padding: 12px;
      display: grid;
      grid-template-rows: auto auto auto 1fr auto;
      gap: 6px;
    }}
    .agent-node.good {{
      border-color: #9bd3c7;
      background: #f2fbf8;
    }}
    .agent-node.warn {{
      border-color: #e6c98f;
      background: #fffaf0;
    }}
    .agent-node.danger {{
      border-color: #efa7a0;
      background: #fff5f4;
    }}
    .agent-node.muted {{
      background: #f7f9fb;
    }}
    .agent-node h3 {{
      margin: 0;
      font-size: 15px;
      line-height: 1.35;
    }}
    .node-step {{
      width: 32px;
      height: 28px;
      border-radius: 6px;
      background: #e8f3f1;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }}
    .node-role {{
      margin: 0;
      font-size: 13px;
      font-weight: 700;
    }}
    .node-desc {{
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }}
    .node-meta {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    .flow-arrow {{
      align-self: center;
      color: var(--muted);
      font-size: 20px;
      font-weight: 700;
      flex: 0 0 auto;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      background: #eef2f6;
      color: var(--muted);
      white-space: nowrap;
    }}
    .badge.good {{
      background: #dff7ef;
      color: #047857;
    }}
    .badge.warn {{
      background: #fff0c2;
      color: #8a5a13;
    }}
    .badge.danger {{
      background: #fde2df;
      color: var(--danger);
    }}
    .badge.muted {{
      background: #eef2f6;
      color: var(--muted);
    }}
    .check-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid var(--line);
      padding: 9px 0;
      font-size: 13px;
    }}
    .check-row:first-of-type {{
      border-top: 0;
    }}
    .check-row span {{
      color: var(--muted);
    }}
    .check-row strong {{
      text-align: right;
    }}
    .run-list {{
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }}
    .run-list a {{
      display: block;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      text-decoration: none;
      color: var(--text);
      background: #fff;
    }}
    .side-stack {{
      display: grid;
      gap: 16px;
    }}
    .kv {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid var(--line);
      padding: 8px 0;
      font-size: 13px;
    }}
    .kv:first-of-type {{
      border-top: 0;
    }}
    .kv span {{
      color: var(--muted);
    }}
    .kv strong {{
      color: var(--text);
      text-align: right;
      overflow-wrap: anywhere;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
      font-family: "Consolas", "SFMono-Regular", monospace;
      font-size: 13px;
    }}
    .status {{
      color: var(--accent-2);
      font-weight: 700;
    }}
    .office-hero {{
      display: grid;
      gap: 6px;
      margin-bottom: 16px;
    }}
    .office-hero p {{
      margin: 0;
      max-width: 760px;
    }}
    .office-shell {{
      background: #eef2f6;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      overflow: hidden;
    }}
    .office-map-visual {{
      border: 1px solid #b8c3cf;
      border-radius: 8px;
      background: #dfe7ed;
      overflow: hidden;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.5);
    }}
    .office-map-stage {{
      position: relative;
      width: 100%;
    }}
    .office-map-image {{
      display: block;
      width: 100%;
      height: auto;
    }}
    .seat-marker {{
      position: absolute;
      left: var(--seat-x);
      top: var(--seat-y);
      width: min(132px, 11.5%);
      min-width: 96px;
      transform: translate(-50%, -50%);
      border: 1px solid rgba(15, 118, 110, .24);
      border-radius: 8px;
      background: rgba(255, 255, 255, .88);
      color: var(--text);
      padding: 7px 8px;
      box-shadow: 0 8px 20px rgba(31,41,51,.14);
      backdrop-filter: blur(3px);
    }}
    .seat-marker.client_ops {{
      border-color: rgba(54, 95, 145, .24);
    }}
    .seat-marker strong {{
      display: block;
      font-size: 13px;
      line-height: 1.2;
      margin-bottom: 3px;
    }}
    .seat-marker span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .seat-marker .badge {{
      display: inline-flex;
      min-height: 20px;
      margin-top: 5px;
      padding: 0 6px;
      font-size: 11px;
    }}
    .office-wing-title {{
      margin: 2px 2px 10px;
      color: #41505f;
      font-size: 14px;
      font-weight: 700;
    }}
    .office-wing-title + .office-floor {{
      margin-bottom: 18px;
    }}
    .office-floor {{
      position: relative;
      min-height: 620px;
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      grid-template-rows: 1fr 74px 1fr;
      grid-template-areas:
        "scout analyst risk"
        "hall hall hall"
        "client listing ops";
      gap: 10px;
      padding: 10px;
      border: 2px solid #cbd5df;
      border-radius: 8px;
      background:
        linear-gradient(90deg, rgba(255,255,255,.38) 1px, transparent 1px),
        linear-gradient(rgba(255,255,255,.38) 1px, transparent 1px),
        #dfe7ed;
      background-size: 32px 32px;
    }}
    .office-floor.client-wing {{
      grid-template-areas:
        "onboarding operator cs"
        "hall hall hall"
        "data qa client";
    }}
    .office-room {{
      position: relative;
      min-height: 220px;
      border: 2px solid #b8c3cf;
      border-radius: 6px;
      background:
        linear-gradient(#fbfcfd 0 28px, transparent 28px),
        linear-gradient(135deg, rgba(255,255,255,.72), rgba(255,255,255,.34)),
        #e8efe9;
      overflow: hidden;
    }}
    .room-scout {{ grid-area: scout; background-color: #edf7f1; }}
    .room-analyst {{ grid-area: analyst; background-color: #f6f2e6; }}
    .room-risk {{ grid-area: risk; background-color: #f3ecec; }}
    .room-client {{ grid-area: client; background-color: #eef2fb; }}
    .room-listing {{ grid-area: listing; background-color: #f1eef8; }}
    .room-ops {{ grid-area: ops; background-color: #edf3f7; }}
    .room-onboarding {{ grid-area: onboarding; background-color: #eef8f4; }}
    .room-operator {{ grid-area: operator; background-color: #f6f2e6; }}
    .room-cs {{ grid-area: cs; background-color: #eef3fb; }}
    .room-data {{ grid-area: data; background-color: #f3f0e9; }}
    .room-qa {{ grid-area: qa; background-color: #f3ecec; }}
    .room-label {{
      position: absolute;
      top: 7px;
      left: 10px;
      right: 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      z-index: 3;
    }}
    .room-label strong {{
      font-size: 13px;
    }}
    .window {{
      position: absolute;
      top: 44px;
      right: 18px;
      width: 82px;
      height: 42px;
      border: 3px solid #c8d3df;
      background:
        linear-gradient(180deg, #f7fbff, #dcecf8);
      box-shadow: inset 38px 0 0 rgba(255,255,255,.45);
    }}
    .window::after {{
      content: "";
      position: absolute;
      left: 38px;
      top: 0;
      bottom: 0;
      border-left: 2px solid #c8d3df;
    }}
    .plant {{
      position: absolute;
      right: 18px;
      bottom: 22px;
      width: 28px;
      height: 42px;
      border-bottom: 20px solid #8f684d;
      border-left: 6px solid transparent;
      border-right: 6px solid transparent;
    }}
    .plant::before {{
      content: "";
      position: absolute;
      left: -16px;
      bottom: 19px;
      width: 42px;
      height: 28px;
      background:
        radial-gradient(circle at 12px 15px, #4f9d69 0 9px, transparent 10px),
        radial-gradient(circle at 24px 10px, #5fb878 0 10px, transparent 11px),
        radial-gradient(circle at 31px 20px, #3f8c61 0 8px, transparent 9px);
    }}
    .office-desk {{
      position: absolute;
      left: 28px;
      bottom: 30px;
      width: min(58%, 190px);
      height: 54px;
      border: 3px solid #6b5749;
      border-radius: 4px;
      background: linear-gradient(#7b6252, #5c493e);
      box-shadow: inset 0 8px 0 rgba(255,255,255,.12);
    }}
    .office-desk::before,
    .office-desk::after {{
      content: "";
      position: absolute;
      bottom: -26px;
      width: 8px;
      height: 26px;
      background: #4f4038;
    }}
    .office-desk::before {{ left: 18px; }}
    .office-desk::after {{ right: 18px; }}
    .monitor {{
      position: absolute;
      top: -40px;
      left: 22px;
      width: 56px;
      height: 36px;
      border: 5px solid #333b45;
      border-radius: 3px;
      background: linear-gradient(135deg, #dff5ff, #ffffff);
    }}
    .monitor::after {{
      content: "";
      position: absolute;
      left: 20px;
      bottom: -15px;
      width: 12px;
      height: 10px;
      background: #333b45;
    }}
    .desk-paper {{
      position: absolute;
      top: 13px;
      right: 16px;
      width: 34px;
      height: 26px;
      border-radius: 2px;
      background:
        linear-gradient(#8fb2d4 2px, transparent 2px) 6px 7px / 22px 6px no-repeat,
        #fff;
    }}
    .avatar {{
      position: absolute;
      left: 82px;
      bottom: 93px;
      width: 44px;
      height: 72px;
      z-index: 2;
    }}
    .avatar::before {{
      content: "";
      position: absolute;
      left: 8px;
      top: 10px;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: #f0b48f;
      box-shadow:
        inset 0 7px 0 #5d3c33,
        0 0 0 2px rgba(45,35,30,.2);
    }}
    .avatar::after {{
      content: "";
      position: absolute;
      left: 10px;
      bottom: 7px;
      width: 24px;
      height: 34px;
      border-radius: 10px 10px 6px 6px;
      background: #2f6f92;
      box-shadow:
        -7px 28px 0 -3px #26323f,
        7px 28px 0 -3px #26323f;
    }}
    .avatar.scout::after {{ background: #2f7d64; }}
    .avatar.analyst::after {{ background: #80623b; }}
    .avatar.risk::after {{ background: #8a3d45; }}
    .avatar.listing::after {{ background: #6d5ba6; }}
    .avatar.ops::after {{ background: #375f7d; }}
    .avatar.onboarding::after {{ background: #2f7d64; }}
    .avatar.operator::after {{ background: #6f5a35; }}
    .avatar.cs::after {{ background: #365f91; }}
    .avatar.data::after {{ background: #795548; }}
    .avatar.qa::after {{ background: #8a3d45; }}
    .office-status {{
      position: absolute;
      left: 18px;
      top: 42px;
      max-width: 148px;
      display: grid;
      gap: 3px;
      z-index: 4;
    }}
    .office-status strong {{
      font-size: 14px;
      line-height: 1.25;
    }}
    .office-status span {{
      font-size: 12px;
      color: var(--muted);
      line-height: 1.35;
    }}
    .hallway {{
      grid-area: hall;
      position: relative;
      border: 2px dashed #b3beca;
      border-radius: 6px;
      background:
        repeating-linear-gradient(90deg, rgba(255,255,255,.6) 0 26px, rgba(230,236,242,.9) 26px 52px);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #41505f;
      font-weight: 700;
    }}
    .handoff-doc {{
      position: absolute;
      left: 9%;
      top: 20px;
      width: 34px;
      height: 42px;
      border-radius: 4px;
      background:
        linear-gradient(135deg, transparent 0 9px, #d7e4f2 10px),
        linear-gradient(#8fb2d4 2px, transparent 2px) 8px 15px / 18px 7px no-repeat,
        #ffffff;
      border: 2px solid #9fb0c0;
      box-shadow: 0 4px 0 rgba(45,55,65,.12);
      animation: handoffMove 8s ease-in-out infinite;
    }}
    @keyframes handoffMove {{
      0%, 100% {{ transform: translateX(0); }}
      50% {{ transform: translateX(720px); }}
    }}
    .office-legend {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }}
    .legend-item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 10px 12px;
      font-size: 13px;
    }}
    .legend-item strong {{
      display: block;
      margin-bottom: 2px;
    }}
    @media (max-width: 920px) {{
      .grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .panels {{
        grid-template-columns: 1fr;
      }}
      .ops-panels {{
        grid-template-columns: 1fr;
      }}
      .decision-cards {{
        grid-template-columns: 1fr;
      }}
      .approval-body {{
        grid-template-columns: 1fr;
      }}
      .office-floor {{
        grid-template-columns: 1fr 1fr;
        grid-template-rows: auto auto 68px auto;
        grid-template-areas:
          "scout analyst"
          "risk listing"
          "hall hall"
          "client ops";
      }}
      .office-floor.client-wing {{
        grid-template-areas:
          "onboarding operator"
          "cs data"
          "hall hall"
          "qa client";
      }}
      @keyframes handoffMove {{
        0%, 100% {{ transform: translateX(0); }}
        50% {{ transform: translateX(420px); }}
      }}
    }}
    @media (max-width: 540px) {{
      .wrap {{
        width: min(100vw - 20px, 1180px);
      }}
      .topbar {{
        align-items: flex-start;
        flex-direction: column;
        padding: 14px 0;
      }}
      nav {{
        width: 100%;
        display: grid;
        grid-template-columns: 1fr;
      }}
      nav a, .button {{
        width: 100%;
        min-width: 0;
        padding: 0 8px;
        font-size: 13px;
        text-align: center;
      }}
      .grid {{
        grid-template-columns: 1fr;
      }}
      .card-head,
      .card-foot,
      .team-heading,
      .flow-lane-head,
      .node-meta {{
        align-items: flex-start;
        flex-direction: column;
      }}
      .team-chip,
      .node-meta {{
        white-space: normal;
      }}
      .card,
      .agent-node,
      .opinion-card,
      .team-heading {{
        overflow-wrap: anywhere;
      }}
      .agent-flow {{
        display: grid;
        overflow-x: visible;
      }}
      .agent-node {{
        min-width: 0;
      }}
      .flow-arrow {{
        transform: rotate(90deg);
        justify-self: center;
      }}
      .office-shell {{
        padding: 10px;
      }}
      .office-map-visual {{
        overflow-x: auto;
      }}
      .office-map-stage {{
        width: 860px;
      }}
      .seat-marker {{
        min-width: 88px;
        padding: 6px;
      }}
      .seat-marker strong {{
        font-size: 12px;
      }}
      .seat-marker span {{
        font-size: 10px;
      }}
      .office-floor {{
        grid-template-columns: 1fr;
        grid-template-rows: auto;
        grid-template-areas:
          "scout"
          "analyst"
          "risk"
          "listing"
          "ops"
          "client"
          "hall";
      }}
      .office-floor.client-wing {{
        grid-template-areas:
          "onboarding"
          "operator"
          "cs"
          "data"
          "qa"
          "client"
          "hall";
      }}
      .office-room {{
        min-height: 230px;
      }}
      .office-status {{
        right: 18px;
        max-width: none;
        padding: 8px;
        border-radius: 6px;
        background: rgba(255, 255, 255, .76);
      }}
      .avatar {{
        left: auto;
        right: 68px;
        bottom: 72px;
      }}
      .window {{
        width: 58px;
        height: 34px;
      }}
      .approval-panel .kv {{
        display: grid;
        gap: 3px;
      }}
      .approval-panel .kv strong {{
        text-align: left;
        overflow-wrap: anywhere;
      }}
      .approval-actions {{
        grid-template-columns: 1fr;
      }}
      .hallway {{
        min-height: 68px;
      }}
      .handoff-doc {{
        animation: none;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap topbar">
      <h1>{html.escape(title)}</h1>
      <nav>
        <a href="/channel-ops">판매 채널 준비</a>
        <a href="/growth-pipeline">6단계 파이프라인</a>
        <a href="/org">직원 직제</a>
        <a href="/">대시보드</a>
        <a href="/approvals">결재 센터</a>
        <a href="/office">AI 에이전트 오피스</a>
        <a href="/ops-check">운영 점검</a>
        <a href="/report">최신 보고서</a>
        <a href="/runs">실행 기록</a>
      </nav>
    </div>
  </header>
  <main class="wrap">{body}</main>
</body>
</html>"""


def render_office_room(team: str, agent_id: str, title: str, role: str, description: str, latest_run: Path | None) -> str:
    layout = OFFICE_LAYOUT[agent_id]
    state = company_agent_state(team, agent_id, latest_run)
    desk_class = html.escape(layout["desk"])
    area_class = html.escape(layout["area"])
    return f"""
      <section class="office-room room-{area_class}">
        <div class="room-label">
          <strong>{html.escape(layout["room"])}</strong>
          <span class="badge {html.escape(state["tone"])}">{html.escape(state["label"])}</span>
        </div>
        <div class="window"></div>
        <div class="office-status">
          <strong>{html.escape(layout["status"])} · {html.escape(title)}</strong>
          <span>{html.escape(role)}</span>
          <span>{html.escape(layout["focus"])}</span>
          <span>{html.escape(state["unit"])} {html.escape(state["outbox"])}개</span>
        </div>
        <div class="office-desk desk-{desk_class}">
          <div class="monitor"></div>
          <div class="desk-paper"></div>
        </div>
        <div class="avatar {area_class}" aria-hidden="true"></div>
        <div class="plant" aria-hidden="true"></div>
      </section>
    """


def render_client_room() -> str:
    handoff = handoff_summary()
    return f"""
      <section class="office-room room-client">
        <div class="room-label">
          <strong>Client Ops 연결실</strong>
          <span class="badge muted">대기</span>
        </div>
        <div class="window"></div>
        <div class="office-status">
          <strong>외부 팀 handoff</strong>
          <span>commerce 팀으로 넘기는 검수 입구</span>
          <span>수신 {html.escape(handoff["received"])}건 · 작업 로그 {html.escape(handoff["task_log"])}</span>
        </div>
        <div class="office-desk">
          <div class="monitor"></div>
          <div class="desk-paper"></div>
        </div>
      </section>
    """


def render_office_marker(team: str, agent_id: str, title: str, role: str, latest_run: Path | None) -> str:
    x, y = OFFICE_SEATS[f"{team}:{agent_id}"]
    state = company_agent_state(team, agent_id, latest_run)
    return f"""
      <div class="seat-marker {html.escape(team)}" style="--seat-x: {html.escape(x)}; --seat-y: {html.escape(y)};">
        <strong>{html.escape(title)}</strong>
        <span>{html.escape(role)}</span>
        <span class="badge {html.escape(state["tone"])}">{html.escape(state["label"])}</span>
      </div>
    """


def render_office_map(latest_run: Path | None) -> str:
    markers = [
        render_office_marker(team, agent_id, title, role, latest_run)
        for team, agent_id, title, role, _description in COMPANY_AGENTS
    ]
    return f"""
      <section class="office-shell">
        <div class="office-map-visual" aria-label="10명 AI 에이전트 사무실 배치도">
          <div class="office-map-stage">
            <img class="office-map-image" src="/assets/office-map.png" alt="10개 PC 좌석이 있는 AI 에이전트 사무실 지도">
            {''.join(markers)}
          </div>
        </div>
      </section>
    """


def render_office() -> str:
    runs = list_runs()
    latest_run = runs[0] if runs else None
    latest_meta = read_run_metadata(latest_run) if latest_run else {}
    body = f"""
      <section class="office-hero">
        <h2>AI 에이전트 오피스</h2>
        <p class="muted">
          10명의 AI 직원이 실제 사무실 배치처럼 어떤 좌석에서 어떤 업무를 맡는지 한눈에 보는 화면입니다.
          운영 상태를 설명하거나, 자동화 회사를 제품처럼 보여줄 때 사용할 수 있습니다.
        </p>
        <p class="muted">최신 실행: {html.escape(str(latest_meta.get("run_id", "아직 없음")))}</p>
      </section>
      {render_office_map(latest_run)}
      <section class="office-legend">
        <div class="legend-item"><strong>01-05</strong><span class="muted">클라이언트 운영팀: 온보딩, 자동화 실행, CS, 분석, QA</span></div>
        <div class="legend-item"><strong>06-10</strong><span class="muted">커머스 발굴 검수팀: 탐색, 마진, 리스크, 리스팅, 운영 판단</span></div>
        <div class="legend-item"><strong>상태 배지</strong><span class="muted">최근 산출물이나 운영 로그의 마지막 상태를 표시합니다.</span></div>
      </section>
    """
    return html_page("AI 에이전트 오피스", body)


def render_agent_card(team: str, agent_id: str, title: str, role: str, description: str, latest_run: Path | None) -> str:
    state = company_agent_state(team, agent_id, latest_run)
    profile = agent_profile(team, agent_id)
    rank = profile.get("rank", "")
    primary_stage = profile.get("primary_stage", "")
    display_name = profile.get("display_name", title)
    return f"""
      <section class="card agent-card team-{html.escape(team)}">
        <div class="card-head">
          <h2>{html.escape(str(display_name))}</h2>
          <span class="team-chip">{html.escape(TEAM_LABELS[team])}</span>
        </div>
        <div class="metric">{html.escape(state["outbox"])}</div>
        <p class="muted">{html.escape(str(rank))} · {html.escape(str(primary_stage))}</p>
        <p class="muted">{html.escape(role)}</p>
        <p class="muted">{html.escape(description)}</p>
        <div class="card-foot">
          <span class="badge {html.escape(state["tone"])}">{html.escape(state["label"])}</span>
          <span class="muted">{html.escape(state["unit"])} 기준</span>
        </div>
      </section>
    """


def render_team_section(team: str, agents: list[tuple[str, str, str, str]], latest_run: Path | None) -> str:
    cards = [
        render_agent_card(team, agent_id, title, role, description, latest_run)
        for agent_id, title, role, description in agents
    ]
    caption = (
        "상품 발굴부터 최종 판단까지 판매 후보를 검수합니다."
        if team == "commerce"
        else "고객 온보딩부터 CS, 주간 리포트와 QA까지 운영 자동화를 맡습니다."
    )
    return f"""
      <section class="team-section">
        <div class="team-heading">
          <div>
            <h2>{html.escape(TEAM_LABELS[team])}</h2>
            <p class="muted">{caption}</p>
          </div>
          <span class="team-count">5명</span>
        </div>
        <div class="grid team-grid">{''.join(cards)}</div>
      </section>
    """


def render_dashboard() -> str:
    runs = list_runs()
    latest_run = runs[0] if runs else None
    latest_meta = read_run_metadata(latest_run) if latest_run else {}
    latest_report = read_text(REPORTS / "latest_agent_run.md", "아직 생성된 보고서가 없습니다.")
    client_log_count = sum(client_ops_activity_count(agent_id) for agent_id, *_rest in CLIENT_OPS_AGENTS)

    run_items = []
    for run_dir in runs[:8]:
        meta = read_run_metadata(run_dir)
        created = meta.get("created_at", "unknown time")
        count = meta.get("candidate_count", "?")
        run_items.append(
            f'<a href="/run?id={html.escape(run_dir.name)}"><strong>{html.escape(run_dir.name)}</strong>'
            f'<br><span class="muted">{html.escape(str(created))} / 후보: {html.escape(str(count))}</span></a>'
        )
    if not run_items:
        run_items.append('<span class="muted">아직 실행 기록이 없습니다.</span>')

    approval_cards = render_approval_summary_cards(latest_run, latest_meta)
    approval_panel = render_approval_panel(latest_run, latest_meta)
    growth_cards = render_growth_summary_cards()
    channel_cards = render_channel_summary_cards()

    body = f"""
      <section class="grid">
        <section class="card">
          <h2>최신 실행</h2>
          <div class="metric run-id">{html.escape(str(latest_meta.get("run_id", "0")))}</div>
          <div class="muted">{html.escape(str(latest_meta.get("created_at", "아직 시작 전")))}</div>
        </section>
        <section class="card">
          <h2>전체 직원</h2>
          <div class="metric">{len(COMPANY_AGENTS)}</div>
          <p class="muted">클라이언트 운영팀 5명 + 커머스팀 5명</p>
        </section>
        <section class="card">
          <h2>Client Ops 로그</h2>
          <div class="metric">{client_log_count}</div>
          <p class="muted">김은보, 박실행, 이용대, 최분석, 정총괄의 운영 기록</p>
        </section>
      </section>
      {growth_cards}
      {channel_cards}
      {render_team_section("client_ops", CLIENT_OPS_AGENTS, latest_run)}
      {render_team_section("commerce", COMMERCE_AGENTS, latest_run)}
      {approval_cards}
      {approval_panel}
      {render_agent_flow(latest_run)}
      <section class="panels">
        <aside class="side-stack">
          {render_health_panel()}
          {render_security_panel()}
          <section class="panel">
            <h2>최근 실행</h2>
            <div class="run-list">{''.join(run_items)}</div>
          </section>
        </aside>
        <section class="panel">
          <h2>최신 최종 보고서</h2>
          <pre>{html.escape(latest_report)}</pre>
        </section>
      </section>
    """
    return html_page("커머스 에이전트 대시보드", body)


def render_approvals() -> str:
    runs = list_runs()
    latest_run = runs[0] if runs else None
    latest_meta = read_run_metadata(latest_run) if latest_run else {}
    decisions = load_approval_decisions()
    history_items = []
    for decision in sorted(decisions.values(), key=lambda item: str(item.get("decided_at", "")), reverse=True)[:12]:
        history_items.append(
            f"""
            <a href="/run?id={html.escape(str(decision.get("run_id", "")))}">
              <strong>{html.escape(str(decision.get("run_id", "")))}</strong>
              <br><span class="muted">{html.escape(str(decision.get("label", "")))} / {html.escape(str(decision.get("decided_at", "")))}</span>
            </a>
            """
        )
    if not history_items:
        history_items.append('<span class="muted">아직 결재 기록이 없습니다.</span>')

    body = f"""
      <section class="office-hero">
        <h2>결재 센터</h2>
        <p class="muted">에이전트 회사의 최종 진행 여부를 승인, 반려, 취소로 기록합니다.</p>
      </section>
      {render_approval_summary_cards(latest_run, latest_meta)}
      {render_approval_panel(latest_run, latest_meta)}
      <section class="panels">
        <section class="panel">
          <h2>직원들 의견서 요약</h2>
          {render_opinion_cards(latest_run)}
        </section>
        <aside class="panel">
          <h2>결재 기록</h2>
          <div class="run-list">{''.join(history_items)}</div>
        </aside>
      </section>
    """
    return html_page("결재 센터", body)


def render_opinions() -> str:
    runs = list_runs()
    latest_run = runs[0] if runs else None
    latest_meta = read_run_metadata(latest_run) if latest_run else {}
    sections = []
    for team, agent_id, title, role, _description in COMPANY_AGENTS:
        if team == "commerce":
            report = read_text(latest_run / f"{agent_id}.md", "이 에이전트의 의견서가 아직 없습니다.") if latest_run else "아직 실행 산출물이 없습니다."
        else:
            report = client_ops_agent_report(agent_id)
        sections.append(
            f"""
            <section class="panel">
              <h2>{html.escape(title)}</h2>
              <p class="muted">{html.escape(TEAM_LABELS[team])} · {html.escape(role)}</p>
              <pre>{html.escape(report)}</pre>
            </section>
            """
        )
    body = f"""
      <section class="office-hero">
        <h2>직원들 의견서</h2>
        <p class="muted">최신 커머스 실행 {html.escape(str(latest_meta.get("run_id", "아직 없음")))}와 client-ops 운영 로그 기준의 10명 판단 근거입니다.</p>
      </section>
      <div style="display:grid; gap:16px;">{''.join(sections)}</div>
    """
    return html_page("직원들 의견서", body)


def render_ops_check() -> str:
    preflight = preflight_report_summary()
    comparison = mock_real_report_summary()
    preflight_badge = "READY" if preflight["tone"] == "good" else ("NOT READY" if preflight["tone"] == "danger" else "CHECK")
    body = f"""
      <section class="office-hero">
        <h2>운영 점검</h2>
        <p class="muted">Claude client-ops 팀과 commerce 팀의 실행 준비 상태를 보는 내부 점검판입니다.</p>
      </section>
      <section class="decision-cards">
        <section class="decision-card">
          <h2>Preflight 상태</h2>
          <div class="metric decision-status">{html.escape(preflight["status"])}</div>
          <p class="muted">{html.escape(preflight["path"])}</p>
        </section>
        <section class="decision-card">
          <h2>자동 점검</h2>
          <div class="metric">{html.escape(preflight["pass"])}</div>
          <p class="muted">FAIL {html.escape(preflight["fail"])} / WARN {html.escape(preflight["warn"])} / SKIP {html.escape(preflight["skip"])}</p>
        </section>
        <section class="decision-card">
          <h2>Mock vs Real</h2>
          <div class="metric decision-status">BLOCK {html.escape(comparison["blocking"])}</div>
          <p class="muted">WARN {html.escape(comparison["warn"])} / SKIP {html.escape(comparison["skip"])}</p>
        </section>
      </section>
      <section class="ops-panels">
        <section class="panel">
          <div class="section-head">
            <div>
              <h2>Client Ops Preflight</h2>
              <p class="muted">보안, 페르소나, LLM, 컴플레인 게이트, handoff 점검 결과입니다.</p>
            </div>
            <span class="badge {html.escape(preflight["tone"])}">{preflight_badge}</span>
          </div>
          <pre>{html.escape(preflight["report"])}</pre>
        </section>
        <aside class="panel">
          <div class="section-head">
            <div>
              <h2>LLM 비교</h2>
              <p class="muted">mock 출력과 real 출력의 구조 차이 점검입니다.</p>
            </div>
            <span class="badge {html.escape(comparison["tone"])}">BLOCK {html.escape(comparison["blocking"])}</span>
          </div>
          <pre>{html.escape(comparison["report"])}</pre>
        </aside>
      </section>
    """
    return html_page("운영 점검", body)


def render_org() -> str:
    cards = []
    for item in agent_roster():
        responsibilities = item.get("responsibilities", [])
        kpis = item.get("kpi", [])
        cards.append(
            f"""
            <section class="panel">
              <div class="section-head">
                <div>
                  <h2>{html.escape(str(item.get("display_name", "")))} · {html.escape(str(item.get("rank", "")))}</h2>
                  <p class="muted">{html.escape(str(item.get("title", "")))} / {html.escape(str(item.get("primary_stage", "")))}</p>
                </div>
                <span class="badge good">{html.escape(str(item.get("team", "")))}</span>
              </div>
              <p>{html.escape(str(item.get("authority", "")))}</p>
              <h3>담당 업무</h3>
              <ul>{''.join(f'<li>{html.escape(str(value))}</li>' for value in responsibilities)}</ul>
              <h3>KPI</h3>
              <ul>{''.join(f'<li>{html.escape(str(value))}</li>' for value in kpis)}</ul>
            </section>
            """
        )
    body = f"""
      <section class="office-hero">
        <h2>직원 직제와 권한</h2>
        <p class="muted">10명의 AI 직원은 각자 직급, 역할, KPI를 갖습니다. 실제 게시와 돈이 움직이는 결정은 Adam 승인 후에만 진행됩니다.</p>
      </section>
      <div style="display:grid; gap:16px;">{''.join(cards)}</div>
    """
    return html_page("직원 직제", body)


def render_growth_pipeline() -> str:
    summary = growth_pipeline_summary()
    counts = summary.get("stage_counts", {})
    decisions = load_pipeline_approvals()
    report = read_text(GROWTH_PIPELINE_REPORT, "아직 6단계 파이프라인 보고서가 없습니다.")

    approval_cards = []
    for item in summary.get("approval_required", []):
        approval_id = str(item.get("approval_id", ""))
        decision = decisions.get(approval_id, {})
        note = decision.get("note", "")
        approval_cards.append(
            f"""
            <section class="panel approval-panel">
              <div class="section-head">
                <div>
                  <h2>{html.escape(str(item.get("product_name", "")))}</h2>
                  <p class="muted">{html.escape(str(item.get("summary", "")))}</p>
                </div>
                <span class="badge warn">{html.escape(pipeline_decision_label(approval_id))}</span>
              </div>
              <form class="approval-form" method="post" action="/pipeline-approval">
                <input type="hidden" name="approval_id" value="{html.escape(approval_id)}">
                <label>Adam 메모</label>
                <textarea name="note" rows="3" placeholder="예: 공급처 증빙 확인 후 수동 게시 승인">{html.escape(str(note))}</textarea>
                <div class="approval-actions">
                  <button class="action approve" type="submit" name="action" value="approve">승인</button>
                  <button class="action reject" type="submit" name="action" value="reject">반려</button>
                  <button class="action cancel" type="submit" name="action" value="hold">보류</button>
                </div>
              </form>
            </section>
            """
        )
    if not approval_cards:
        approval_cards.append('<section class="panel"><h2>Adam 승인 대기</h2><p class="muted">현재 승인 대기 상품이 없습니다.</p></section>')

    body = f"""
      <section class="office-hero">
        <h2>6단계 커머스 파이프라인</h2>
        <p class="muted">발굴부터 성과 추적까지 자동으로 산출물을 만들고, 라이브 게시 전에는 Adam 승인 대기 상태로 멈춥니다.</p>
        <p class="muted">최근 실행: {html.escape(str(summary.get("run_id", "없음")))} / {html.escape(str(summary.get("created_at", "")))}</p>
      </section>
      <section class="decision-cards">
        <section class="decision-card"><h2>상품 발굴</h2><div class="metric">{html.escape(str(counts.get("discovered", 0)))}</div><p class="muted">수요/경쟁 후보</p></section>
        <section class="decision-card"><h2>공급처 검증</h2><div class="metric">{html.escape(str(counts.get("supplier_checked", 0)))}</div><p class="muted">증빙 필요 {html.escape(str(counts.get("supplier_evidence_needed", 0)))}</p></section>
        <section class="decision-card"><h2>리스크 차단</h2><div class="metric">{html.escape(str(counts.get("risk_blocked", 0)))}</div><p class="muted">정책/IP/인증 차단</p></section>
        <section class="decision-card"><h2>채널 패키지</h2><div class="metric">{html.escape(str(counts.get("channel_packages", 0)))}</div><p class="muted">게시 전 초안</p></section>
      </section>
      <section class="panels">
        <section>
          <div style="display:grid; gap:16px;">{''.join(approval_cards)}</div>
        </section>
        <aside class="panel">
          <h2>파이프라인 보고서</h2>
          <pre>{html.escape(report)}</pre>
        </aside>
      </section>
    """
    return html_page("6단계 파이프라인", body)


def render_channel_ops() -> str:
    readiness = channel_readiness_summary()
    validation = channel_validation_summary()
    readiness_report = read_text(CHANNEL_READINESS_REPORT, "아직 판매자 계정 준비 점검 보고서가 없습니다.")
    validation_report = read_text(CHANNEL_VALIDATION_REPORT, "아직 채널 제출 dry-run 검증 보고서가 없습니다.")
    channels = readiness.get("channels", {})
    channel_rows = []
    for channel, result in channels.items():
        ready = "READY" if result.get("ready") else "NOT READY"
        channel_rows.append(f'<div class="kv"><span>{html.escape(str(channel))}</span><strong>{html.escape(ready)}</strong></div>')
    if not channel_rows:
        channel_rows.append('<p class="muted">아직 채널 준비 점검 기록이 없습니다.</p>')

    findings = validation.get("findings", [])
    finding_rows = []
    for finding in findings[:12]:
        finding_rows.append(
            f"""
            <tr>
              <td>{html.escape(str(finding.get("channel", "")))}</td>
              <td>{html.escape(str(finding.get("opportunity_id", "")))}</td>
              <td>{html.escape(str(finding.get("severity", "")))}</td>
              <td>{html.escape(str(finding.get("message", "")))}</td>
            </tr>
            """
        )
    if not finding_rows:
        finding_rows.append('<tr><td colspan="4">검증 기록이 없습니다.</td></tr>')

    body = f"""
      <section class="office-hero">
        <h2>판매 채널 준비 센터</h2>
        <p class="muted">판매자 가입과 API 연결 전까지 계정 준비 상태와 쿠팡/아마존 제출 패키지를 dry-run으로 점검합니다.</p>
      </section>
      <section class="decision-cards">
        <section class="decision-card">
          <h2>계정 준비 상태</h2>
          <div class="metric decision-status">{html.escape(str(readiness.get("status", "not_started")))}</div>
          <p class="muted">{html.escape(str(readiness.get("created_at", "")))}</p>
        </section>
        <section class="decision-card">
          <h2>Dry-run 검증</h2>
          <div class="metric decision-status">{html.escape(str(validation.get("status", "not_started")))}</div>
          <p class="muted">BLOCK {html.escape(str(validation.get("blocking", 0)))} / WARN {html.escape(str(validation.get("warn", 0)))}</p>
        </section>
        <section class="decision-card">
          <h2>검증 패키지</h2>
          <div class="metric">{html.escape(str(validation.get("submission_count", 0)))}</div>
          <p class="muted">외부 API 호출 없이 로컬 구조만 검사합니다.</p>
        </section>
      </section>
      <section class="panels">
        <aside class="side-stack">
          <section class="panel">
            <h2>채널별 준비</h2>
            {''.join(channel_rows)}
          </section>
          <section class="panel">
            <h2>최근 검증 결과</h2>
            <table class="data-table">
              <thead><tr><th>채널</th><th>상품</th><th>등급</th><th>내용</th></tr></thead>
              <tbody>{''.join(finding_rows)}</tbody>
            </table>
          </section>
        </aside>
        <section class="panel">
          <h2>계정 준비 보고서</h2>
          <pre>{html.escape(readiness_report)}</pre>
        </section>
        <section class="panel">
          <h2>Dry-run 검증 보고서</h2>
          <pre>{html.escape(validation_report)}</pre>
        </section>
      </section>
    """
    return html_page("판매 채널 준비 센터", body)


def render_report() -> str:
    report = read_text(REPORTS / "latest_agent_run.md", "최신 에이전트 보고서를 찾지 못했습니다.")
    body = f'<section class="panel"><h2>최신 보고서</h2><pre>{html.escape(report)}</pre></section>'
    return html_page("최신 에이전트 보고서", body)


def render_runs() -> str:
    rows = []
    for run_dir in list_runs():
        meta = read_run_metadata(run_dir)
        rows.append(
            f'<a href="/run?id={html.escape(run_dir.name)}"><strong>{html.escape(run_dir.name)}</strong>'
            f'<br><span class="muted">{html.escape(str(meta.get("created_at", "unknown")))}'
            f' / LLM: {html.escape(str(meta.get("use_llm", False)))}</span></a>'
        )
    if not rows:
        rows.append('<span class="muted">아직 실행 기록이 없습니다.</span>')
    body = f'<section class="panel"><h2>실행 기록</h2><div class="run-list">{"".join(rows)}</div></section>'
    return html_page("에이전트 실행 기록", body)


def render_run(run_id: str) -> str:
    clean_id = Path(run_id).name
    run_dir = RUNS / clean_id
    if not run_dir.exists() or not run_dir.is_dir():
        return html_page("실행 기록 없음", '<section class="panel"><h2>실행 기록을 찾지 못했습니다</h2></section>')

    sections = []
    for agent_id, title, _role, _description in AGENTS:
        report = read_text(run_dir / f"{agent_id}.md", "이 에이전트의 산출물이 없습니다.")
        sections.append(f'<section class="panel"><h2>{html.escape(title)}</h2><pre>{html.escape(report)}</pre></section>')
    body = '<div style="display:grid; gap:16px;">' + "".join(sections) + "</div>"
    return html_page(clean_id, body)


class Handler(BaseHTTPRequestHandler):
    def is_authorized(self) -> bool:
        username = os.getenv("DASHBOARD_USERNAME", "").strip()
        password = os.getenv("DASHBOARD_PASSWORD", "").strip()
        if not username or not password:
            return True

        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header.removeprefix("Basic ").strip()).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        supplied_username, separator, supplied_password = decoded.partition(":")
        if not separator:
            return False
        return hmac.compare_digest(supplied_username, username) and hmac.compare_digest(supplied_password, password)

    def request_auth(self) -> None:
        body = b"Authentication required."
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Commerce Agent Dashboard"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self.is_authorized():
            self.request_auth()
            return

        parsed = urlparse(self.path)
        if parsed.path.startswith("/assets/"):
            asset_name = Path(parsed.path.removeprefix("/assets/")).name
            asset_path = ASSETS / asset_name
            if not asset_path.is_file():
                self.send_error(404)
                return
            body = asset_path.read_bytes()
            content_type = "image/png" if asset_path.suffix.lower() == ".png" else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/":
            content = render_dashboard()
        elif parsed.path == "/channel-ops":
            content = render_channel_ops()
        elif parsed.path == "/growth-pipeline":
            content = render_growth_pipeline()
        elif parsed.path == "/org":
            content = render_org()
        elif parsed.path == "/approvals":
            content = render_approvals()
        elif parsed.path == "/opinions":
            content = render_opinions()
        elif parsed.path == "/office":
            content = render_office()
        elif parsed.path == "/ops-check":
            content = render_ops_check()
        elif parsed.path == "/report":
            content = render_report()
        elif parsed.path == "/runs":
            content = render_runs()
        elif parsed.path == "/run":
            run_id = parse_qs(parsed.query).get("id", [""])[0]
            content = render_run(run_id)
        else:
            self.send_error(404)
            return

        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        if not self.is_authorized():
            self.request_auth()
            return

        parsed = urlparse(self.path)
        if parsed.path not in {"/approval", "/pipeline-approval"}:
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(raw_body)
        run_id = form.get("run_id", [""])[0]
        action = form.get("action", [""])[0]
        note = form.get("note", [""])[0]

        if parsed.path == "/pipeline-approval":
            approval_id = form.get("approval_id", [""])[0]
            try:
                record_pipeline_approval(approval_id, action, note)
            except ValueError as exc:
                body = html_page("파이프라인 승인 오류", f'<section class="panel"><h2>파이프라인 승인 오류</h2><p>{html.escape(str(exc))}</p></section>')
                encoded = body.encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                return

            self.send_response(303)
            self.send_header("Location", "/growth-pipeline")
            self.end_headers()
            return

        try:
            record_approval(run_id, action, note)
        except ValueError as exc:
            body = html_page("결재 오류", f'<section class="panel"><h2>결재 오류</h2><p>{html.escape(str(exc))}</p></section>')
            encoded = body.encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        self.send_response(303)
        self.send_header("Location", "/approvals")
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"dashboard: {fmt % args}")


def main() -> int:
    load_env_file()

    parser = argparse.ArgumentParser(description="Run the commerce agent dashboard.")
    parser.add_argument("--host", default=os.getenv("DASHBOARD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DASHBOARD_PORT", "8080")))
    parser.add_argument("--check", action="store_true", help="Render once and exit.")
    args = parser.parse_args()

    if args.check:
        html_output = render_dashboard()
        print(f"dashboard render ok: {len(html_output)} bytes")
        return 0

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
