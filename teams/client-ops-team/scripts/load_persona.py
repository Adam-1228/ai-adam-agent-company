from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
MANIFEST_PATH = ROOT / "company_manifest.md"

AGENT_NAMES_KR = {
    "01_onboarding_manager": "김은보",
    "02_ops_operator": "박실행",
    "03_cs_manager": "이용대",
    "04_data_analyst": "최분석",
    "05_coordinator_qa": "정총괄",
}

PERSONA_FILES = ["persona.md", "inbox.md", "memory.md", "output_template.md"]
SECTION_HEADERS = {
    "persona.md": "## §1 페르소나 (정체성)",
    "inbox.md": "## §2 인박스 (수신 가능 작업)",
    "memory.md": "## §3 메모리 (누적 주의사항)",
    "output_template.md": "## §4 출력 형식",
}

MANIFEST_SECTION_TITLE = "절대 금지"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def extract_manifest_section(manifest_text: str, title: str) -> str:
    """Return the body of the `## {title}` section, up to the next `## ` header."""
    lines = manifest_text.splitlines()
    capture = False
    captured: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            if heading == title:
                capture = True
                captured.append(line)
                continue
            if capture:
                break
        if capture:
            captured.append(line)
    return "\n".join(captured).rstrip()


def compose_system_prompt(agent_id: str) -> dict:
    if agent_id not in AGENT_NAMES_KR:
        raise ValueError(f"Unknown agent_id: {agent_id}")

    agent_dir = AGENTS_DIR / agent_id
    if not agent_dir.is_dir():
        raise FileNotFoundError(f"Agent folder not found: {agent_dir}")

    name_kr = AGENT_NAMES_KR[agent_id]
    parts: list[str] = [
        f"# 당신은 client-ops-team의 {agent_id} ({name_kr})입니다.",
        "",
        "아래 §1~§4는 당신의 정체성과 책임, 인박스, 누적 메모리, 출력 형식입니다.",
        "마지막 §5는 회사 전체의 절대 금지 사항이며, 위 모든 것에 우선합니다.",
        "",
    ]

    for filename in PERSONA_FILES:
        body = read_text(agent_dir / filename)
        header = SECTION_HEADERS[filename]
        parts.append(header)
        parts.append("")
        parts.append(body if body else "_(파일 없음 또는 비어 있음)_")
        parts.append("")

    manifest_text = read_text(MANIFEST_PATH)
    forbidden = extract_manifest_section(manifest_text, MANIFEST_SECTION_TITLE)
    parts.append("## §5 회사 절대 금지 (모든 결정에 우선)")
    parts.append("")
    parts.append(forbidden if forbidden else "_(company_manifest.md에서 '절대 금지' 섹션을 찾지 못했습니다.)_")
    parts.append("")
    parts.append(
        "위 절대 금지 중 하나라도 걸리는 케이스는 자기 페르소나 톤과 무관하게 즉시 "
        "05_coordinator_qa(정총괄)에게 에스컬레이션하십시오."
    )

    system_prompt = "\n".join(parts).strip() + "\n"
    return {
        "system_prompt": system_prompt,
        "agent_id": agent_id,
        "agent_name_kr": name_kr,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Compose a system prompt for one client-ops agent.")
    parser.add_argument("agent_id", help=f"One of: {', '.join(AGENT_NAMES_KR)}")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of plain text.")
    args = parser.parse_args()

    if args.agent_id not in AGENT_NAMES_KR:
        print(f"Unknown agent_id: {args.agent_id}", file=sys.stderr)
        print(f"Valid: {', '.join(AGENT_NAMES_KR)}", file=sys.stderr)
        return 1

    composed = compose_system_prompt(args.agent_id)
    if args.json:
        print(json.dumps(composed, ensure_ascii=False, indent=2))
    else:
        print(composed["system_prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
