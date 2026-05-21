from __future__ import annotations

import argparse
import base64
import hmac
import html
import json
import os
import shutil
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

AGENTS = [
    ("01_market_scout", "시장 탐색가", "상품 기회 발굴", "수요 신호와 카테고리 후보를 찾습니다."),
    ("02_margin_analyst", "마진 분석가", "수익성 검토", "원가, 판매가, 경쟁 강도, 리뷰 신호를 계산합니다."),
    ("03_risk_guardian", "리스크 감시자", "위험 차단", "인증, 지식재산권, 이미지 권리, 반품 리스크를 막습니다."),
    ("04_listing_builder", "리스팅 작성자", "판매 페이지 초안", "상품명, 상세페이지 구조, FAQ, 금지 표현을 정리합니다."),
    ("05_ops_manager", "운영 관리자", "최종 판단", "진행/검토/보류 결론과 다음 액션을 조율합니다."),
]


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
    @media (max-width: 920px) {{
      .grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .panels {{
        grid-template-columns: 1fr;
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
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap topbar">
      <h1>{html.escape(title)}</h1>
      <nav>
        <a href="/">대시보드</a>
        <a href="/report">최신 보고서</a>
        <a href="/runs">실행 기록</a>
      </nav>
    </div>
  </header>
  <main class="wrap">{body}</main>
</body>
</html>"""


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

    body = f"""
      <section class="grid">
        <section class="card">
          <h2>최신 실행</h2>
          <div class="metric run-id">{html.escape(str(latest_meta.get("run_id", "0")))}</div>
          <div class="muted">{html.escape(str(latest_meta.get("created_at", "아직 시작 전")))}</div>
        </section>
        {''.join(cards)}
      </section>
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
