from __future__ import annotations

import argparse
import base64
import hmac
import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
WORKFORCE = ROOT / "workforce"
RUNS = WORKFORCE / "runs"

AGENTS = [
    ("01_market_scout", "Market Scout", "Find product opportunities"),
    ("02_margin_analyst", "Margin Analyst", "Check demand, margin, and competition"),
    ("03_risk_guardian", "Risk Guardian", "Block compliance, IP, and image-rights risk"),
    ("04_listing_builder", "Listing Builder", "Draft product titles and listing pages"),
    ("05_ops_manager", "Ops Manager", "Coordinate final decisions"),
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
      font-family: Arial, "Segoe UI", sans-serif;
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
      grid-template-columns: repeat(5, minmax(0, 1fr));
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
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap topbar">
      <h1>{html.escape(title)}</h1>
      <nav>
        <a href="/">Dashboard</a>
        <a href="/report">Latest Report</a>
        <a href="/runs">Runs</a>
      </nav>
    </div>
  </header>
  <main class="wrap">{body}</main>
</body>
</html>"""


def render_dashboard() -> str:
    runs = list_runs()
    latest_meta = read_run_metadata(runs[0]) if runs else {}
    latest_report = read_text(REPORTS / "latest_agent_run.md", "No report has been generated yet.")

    cards = []
    for agent_id, title, description in AGENTS:
        cards.append(
            f"""
            <section class="card">
              <h2>{html.escape(title)}</h2>
              <div class="metric">{agent_outbox_count(agent_id)}</div>
              <div class="muted">{html.escape(description)}</div>
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
            f'<br><span class="muted">{html.escape(str(created))} / candidates: {html.escape(str(count))}</span></a>'
        )
    if not run_items:
        run_items.append('<span class="muted">No runs yet.</span>')

    body = f"""
      <section class="grid">
        <section class="card">
          <h2>Latest Run</h2>
          <div class="metric run-id">{html.escape(str(latest_meta.get("run_id", "0")))}</div>
          <div class="muted">{html.escape(str(latest_meta.get("created_at", "Not started")))}</div>
        </section>
        {''.join(cards)}
      </section>
      <section class="panels">
        <aside class="panel">
          <h2>Recent Runs</h2>
          <div class="run-list">{''.join(run_items)}</div>
        </aside>
        <section class="panel">
          <h2>Latest Final Report</h2>
          <pre>{html.escape(latest_report)}</pre>
        </section>
      </section>
    """
    return html_page("Commerce Agent Dashboard", body)


def render_report() -> str:
    report = read_text(REPORTS / "latest_agent_run.md", "No latest agent report found.")
    body = f'<section class="panel"><h2>Latest Report</h2><pre>{html.escape(report)}</pre></section>'
    return html_page("Latest Agent Report", body)


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
        rows.append('<span class="muted">No runs yet.</span>')
    body = f'<section class="panel"><h2>Runs</h2><div class="run-list">{"".join(rows)}</div></section>'
    return html_page("Agent Runs", body)


def render_run(run_id: str) -> str:
    clean_id = Path(run_id).name
    run_dir = RUNS / clean_id
    if not run_dir.exists() or not run_dir.is_dir():
        return html_page("Run Not Found", '<section class="panel"><h2>Run Not Found</h2></section>')

    sections = []
    for agent_id, title, _description in AGENTS:
        report = read_text(run_dir / f"{agent_id}.md", "No output for this agent.")
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
