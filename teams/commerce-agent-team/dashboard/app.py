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


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
WORKFORCE = ROOT / "workforce"
RUNS = WORKFORCE / "runs"
RUNTIME = ROOT / "runtime"
LLM_USAGE_LOG = RUNTIME / "llm_usage.jsonl"
CLIENT_OPS_HANDOFFS = RUNTIME / "client_ops_handoffs"
APPROVALS_PATH = RUNTIME / "approval_decisions.json"
APPROVAL_LOG = RUNTIME / "approval_log.jsonl"

AGENTS = [
    ("01_market_scout", "시장 탐색가", "상품 기회 발굴", "수요 신호와 카테고리 후보를 찾습니다."),
    ("02_margin_analyst", "마진 분석가", "수익성 검토", "원가, 판매가, 경쟁 강도, 리뷰 신호를 계산합니다."),
    ("03_risk_guardian", "리스크 감시자", "위험 차단", "인증, 지식재산권, 이미지 권리, 반품 리스크를 막습니다."),
    ("04_listing_builder", "리스팅 작성자", "판매 페이지 초안", "상품명, 상세페이지 구조, FAQ, 금지 표현을 정리합니다."),
    ("05_ops_manager", "운영 관리자", "최종 판단", "진행/검토/보류 결론과 다음 액션을 조율합니다."),
]

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


def render_approval_summary_cards(latest_run: Path | None, latest_meta: dict) -> str:
    run_id = str(latest_meta.get("run_id", latest_run.name if latest_run else ""))
    decision = approval_for_run(run_id) if run_id else {}
    status = str(decision.get("status", "pending" if latest_run else "canceled"))
    pending_count = "1" if latest_run and status == "pending" else "0"
    opinions_count = "0"
    if latest_run:
        opinions_count = str(sum(1 for agent_id, *_rest in AGENTS if (latest_run / f"{agent_id}.md").exists()))
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
    for agent_id, title, role, _description in AGENTS:
        summary = agent_opinion_summary(agent_id, latest_run)
        cards.append(
            f"""
            <article class="opinion-card">
              <h3>{html.escape(title)}</h3>
              <p class="muted">{html.escape(role)}</p>
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


def render_agent_flow(latest_run: Path | None) -> str:
    nodes = []
    for index, (agent_id, title, role, description) in enumerate(AGENTS, start=1):
        state = agent_run_state(agent_id, latest_run)
        nodes.append(
            f"""
            <div class="agent-node {html.escape(state["tone"])}">
              <div class="node-step">{index:02d}</div>
              <h3>{html.escape(title)}</h3>
              <p class="node-role">{html.escape(role)}</p>
              <p class="node-desc">{html.escape(description)}</p>
              <div class="node-meta">
                <span class="badge {html.escape(state["tone"])}">{html.escape(state["label"])}</span>
                <span>산출물 {html.escape(state["outbox"])}개</span>
              </div>
            </div>
            """
        )
        if index < len(AGENTS):
            nodes.append('<div class="flow-arrow" aria-hidden="true">&rarr;</div>')

    return f"""
      <section class="panel agent-map">
        <div class="section-head">
          <div>
            <h2>에이전트 운영 흐름</h2>
            <p class="muted">발굴에서 최종 판단까지 5명의 에이전트가 순서대로 산출물을 넘깁니다.</p>
          </div>
        </div>
        <div class="agent-flow">{''.join(nodes)}</div>
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
    return f"""
      <section class="panel">
        <h2>시스템 상태</h2>
        <div class="kv"><span>LLM 제공자</span><strong>{html.escape(env["provider"])}</strong></div>
        <div class="kv"><span>대시보드 인증</span><strong>{html.escape(env["dashboard_auth"])}</strong></div>
        <div class="kv"><span>저장된 실행</span><strong>{run_count}</strong></div>
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
        <a href="/">대시보드</a>
        <a href="/approvals">결재 센터</a>
        <a href="/office">AI 에이전트 오피스</a>
        <a href="/report">최신 보고서</a>
        <a href="/runs">실행 기록</a>
      </nav>
    </div>
  </header>
  <main class="wrap">{body}</main>
</body>
</html>"""


def render_office_room(agent_id: str, title: str, role: str, description: str, latest_run: Path | None) -> str:
    layout = OFFICE_LAYOUT[agent_id]
    state = agent_run_state(agent_id, latest_run)
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
          <span>산출물 {html.escape(state["outbox"])}개</span>
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
          <span>클로드 팀의 신호를 commerce 팀으로 넘기는 입구입니다.</span>
          <span>수신 {html.escape(handoff["received"])}건</span>
          <span>작업 로그 {html.escape(handoff["task_log"])}</span>
        </div>
        <div class="office-desk">
          <div class="monitor"></div>
          <div class="desk-paper"></div>
        </div>
        <div class="avatar ops" aria-hidden="true"></div>
      </section>
    """


def render_office() -> str:
    runs = list_runs()
    latest_run = runs[0] if runs else None
    latest_meta = read_run_metadata(latest_run) if latest_run else {}
    rooms = [
        render_office_room(agent_id, title, role, description, latest_run)
        for agent_id, title, role, description in AGENTS
    ]
    body = f"""
      <section class="office-hero">
        <h2>AI 에이전트 오피스</h2>
        <p class="muted">
          커머스 에이전트들이 어떤 방에서 어떤 업무를 맡는지 한눈에 보는 시각화 화면입니다.
          운영 상태를 설명하거나, 자동화 회사를 제품처럼 보여줄 때 사용할 수 있습니다.
        </p>
        <p class="muted">최신 실행: {html.escape(str(latest_meta.get("run_id", "아직 없음")))}</p>
      </section>
      <section class="office-shell">
        <div class="office-floor">
          {rooms[0]}
          {rooms[1]}
          {rooms[2]}
          <div class="hallway">
            <div class="handoff-doc" aria-hidden="true"></div>
            Commerce Handoff Hall
          </div>
          {render_client_room()}
          {rooms[3]}
          {rooms[4]}
        </div>
      </section>
      <section class="office-legend">
        <div class="legend-item"><strong>초록 배지</strong><span class="muted">최근 실행에서 산출물이 확인된 에이전트입니다.</span></div>
        <div class="legend-item"><strong>문서 이동</strong><span class="muted">팀 간 handoff가 검증 후 업무로 넘어가는 흐름을 뜻합니다.</span></div>
        <div class="legend-item"><strong>클릭 흐름</strong><span class="muted">상단 실행 기록에서 각 에이전트 산출물을 확인할 수 있습니다.</span></div>
      </section>
    """
    return html_page("AI 에이전트 오피스", body)


def render_dashboard() -> str:
    runs = list_runs()
    latest_run = runs[0] if runs else None
    latest_meta = read_run_metadata(latest_run) if latest_run else {}
    latest_report = read_text(REPORTS / "latest_agent_run.md", "아직 생성된 보고서가 없습니다.")

    cards = []
    for agent_id, title, role, description in AGENTS:
        state = agent_run_state(agent_id, latest_run)
        cards.append(
            f"""
            <section class="card">
              <h2>{html.escape(title)}</h2>
              <div class="metric">{html.escape(state["outbox"])}</div>
              <p class="muted">{html.escape(role)}</p>
              <p class="muted">{html.escape(description)}</p>
            </section>
            """
        )

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

    body = f"""
      <section class="grid">
        <section class="card">
          <h2>최신 실행</h2>
          <div class="metric run-id">{html.escape(str(latest_meta.get("run_id", "0")))}</div>
          <div class="muted">{html.escape(str(latest_meta.get("created_at", "아직 시작 전")))}</div>
        </section>
        {''.join(cards)}
      </section>
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
    for agent_id, title, role, _description in AGENTS:
        report = read_text(latest_run / f"{agent_id}.md", "이 에이전트의 의견서가 아직 없습니다.") if latest_run else "아직 실행 산출물이 없습니다."
        sections.append(
            f"""
            <section class="panel">
              <h2>{html.escape(title)}</h2>
              <p class="muted">{html.escape(role)}</p>
              <pre>{html.escape(report)}</pre>
            </section>
            """
        )
    body = f"""
      <section class="office-hero">
        <h2>직원들 의견서</h2>
        <p class="muted">최신 실행 {html.escape(str(latest_meta.get("run_id", "아직 없음")))} 기준의 에이전트별 판단 근거입니다.</p>
      </section>
      <div style="display:grid; gap:16px;">{''.join(sections)}</div>
    """
    return html_page("직원들 의견서", body)


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
        if parsed.path == "/":
            content = render_dashboard()
        elif parsed.path == "/approvals":
            content = render_approvals()
        elif parsed.path == "/opinions":
            content = render_opinions()
        elif parsed.path == "/office":
            content = render_office()
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
        if parsed.path != "/approval":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(raw_body)
        run_id = form.get("run_id", [""])[0]
        action = form.get("action", [""])[0]
        note = form.get("note", [""])[0]

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
