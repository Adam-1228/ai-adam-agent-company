"""Pre-launch checklist automation for client-ops-team.

Maps `shared/pre_launch_checklist.md` to 12 sections and auto-runs the ones that
can be verified without human judgment. Manual categories are SKIP_MANUAL.

Exit codes:
  0  - all automatable checks PASS (manual sections counted as SKIP_MANUAL)
  1  - at least one FAIL
  2  - exception during execution
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from llm_client import complete, configure_stdout, load_dotenv, load_model_config
from load_persona import AGENT_NAMES_KR, compose_system_prompt
import run_agent
from run_agent import policy_check, parse_packet


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
AGENTS_DIR = ROOT / "agents"
SHARED_DIR = ROOT / "shared"
CONFIG_PATH = ROOT / "config" / "agent_models.json"
ENV_EXAMPLE = ROOT / ".env.example"
ROOT_GITIGNORE = REPO_ROOT / ".gitignore"
DEFAULT_OUTPUT_DIR = ROOT / "reports"
CONTRACT_DOC = REPO_ROOT / "shared" / "handoff_contracts" / "commerce_client_ops_contract.md"


PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP_MANUAL = "SKIP_MANUAL"

# Visual marker. Printed via stdout reconfigured to utf-8.
MARK = {
    PASS: "[ OK ]",
    FAIL: "[FAIL]",
    WARN: "[WARN]",
    SKIP_MANUAL: "[SKIP]",
}


@dataclass
class CheckResult:
    section: str  # e.g. "§1.1"
    title: str
    status: str
    detail: str = ""
    fix_hint: str = ""


def render_status(r: CheckResult) -> str:
    head = f"{MARK[r.status]} {r.section} {r.title}: {r.status}"
    return head


# =========================================================================
# Section 1 — 보안/컴플라이언스
# =========================================================================

def section_1_secrets() -> list[CheckResult]:
    out: list[CheckResult] = []

    # 1.1 .env files are NOT tracked in git
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--", "*.env", "*.env.*", "!.env.example"],
            capture_output=True, text=True, timeout=10,
        )
        tracked = [ln for ln in result.stdout.splitlines() if ln and ".env.example" not in ln and not ln.endswith(".env.example")]
        if tracked:
            out.append(CheckResult(
                "§1.1", ".env 미커밋", FAIL,
                detail=f"git ls-files returned: {tracked}",
                fix_hint="git rm --cached <file>; .gitignore에 추가",
            ))
        else:
            out.append(CheckResult("§1.1", ".env 미커밋", PASS, detail="no .env tracked"))
    except Exception as exc:
        out.append(CheckResult("§1.1", ".env 미커밋", WARN, detail=f"git ls-files failed: {exc}"))

    # 1.2 root .gitignore protects .env / pem / key / reports / runtime / logs
    must_have = [".env", "*.pem", "*.key", "teams/*/reports/*", "teams/*/runtime/", "teams/*/logs/*"]
    if not ROOT_GITIGNORE.exists():
        out.append(CheckResult("§1.2", "루트 .gitignore 존재", FAIL, detail="root .gitignore missing"))
    else:
        gi = ROOT_GITIGNORE.read_text(encoding="utf-8")
        missing = [pat for pat in must_have if pat not in gi]
        if missing:
            out.append(CheckResult(
                "§1.2", "루트 .gitignore 보호 패턴", FAIL,
                detail=f"missing patterns: {missing}",
                fix_hint="루트 .gitignore에 위 패턴 추가 (별도 PR 권장)",
            ))
        else:
            out.append(CheckResult("§1.2", "루트 .gitignore 보호 패턴", PASS))

    # 1.3 grep for plaintext API key shapes inside the client-ops tree
    bad_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
        re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),  # Google API key shape
    ]
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(seg in path.parts for seg in ("runtime", "reports", "logs", "__pycache__")):
            continue
        if path.name in (".env",):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in bad_patterns:
            if pat.search(text):
                hits.append(str(path.relative_to(ROOT)))
                break
    if hits:
        out.append(CheckResult(
            "§1.3", "평문 API 키 grep", FAIL,
            detail=f"suspicious key shapes in: {hits}",
            fix_hint="해당 파일에서 키 제거, 즉시 키 로테이션",
        ))
    else:
        out.append(CheckResult("§1.3", "평문 API 키 grep", PASS))

    # 1.4 .env.example exists with placeholders
    if not ENV_EXAMPLE.exists():
        out.append(CheckResult("§1.4", ".env.example 템플릿 존재", FAIL))
    else:
        txt = ENV_EXAMPLE.read_text(encoding="utf-8")
        if "ANTHROPIC_API_KEY" in txt and "GEMINI_API_KEY" in txt:
            out.append(CheckResult("§1.4", ".env.example 템플릿 존재", PASS))
        else:
            out.append(CheckResult(
                "§1.4", ".env.example 템플릿 존재", WARN,
                detail="ANTHROPIC_API_KEY 또는 GEMINI_API_KEY 키 라인 누락",
            ))
    return out


# =========================================================================
# Section 2 — 페르소나 일관성
# =========================================================================

PERSONA_FILES = ["persona.md", "inbox.md", "memory.md", "output_template.md"]
PERSONA_REQUIRED_SECTIONS = {
    "persona.md": ["## 페르소나", "## 책임 범위", "## KPI"],
}


def section_2_persona() -> list[CheckResult]:
    out: list[CheckResult] = []
    expected = 5 * 4
    found = 0
    missing: list[str] = []
    for agent_id in AGENT_NAMES_KR:
        for fname in PERSONA_FILES:
            p = AGENTS_DIR / agent_id / fname
            if p.exists():
                found += 1
            else:
                missing.append(f"{agent_id}/{fname}")
    if missing:
        out.append(CheckResult(
            "§2.1", "5명 페르소나 4종 세트", FAIL,
            detail=f"missing {len(missing)}/{expected}: {missing}",
            fix_hint="누락 파일 생성 (별도 PR)",
        ))
    else:
        out.append(CheckResult("§2.1", "5명 페르소나 4종 세트", PASS, detail=f"{found}/{expected}"))

    # 2.2 persona.md must include core sections
    section_missing: list[str] = []
    for agent_id in AGENT_NAMES_KR:
        persona = AGENTS_DIR / agent_id / "persona.md"
        if not persona.exists():
            continue
        text = persona.read_text(encoding="utf-8")
        for section in PERSONA_REQUIRED_SECTIONS["persona.md"]:
            if section not in text:
                section_missing.append(f"{agent_id}: {section}")
    if section_missing:
        out.append(CheckResult(
            "§2.2", "persona 핵심 섹션", FAIL,
            detail=f"missing headers: {section_missing}",
            fix_hint="persona.md에 누락 헤더 추가 (별도 PR)",
        ))
    else:
        out.append(CheckResult("§2.2", "persona 핵심 섹션", PASS))

    # 2.3 compose_system_prompt resolves for every agent without exceptions.
    compose_errors: list[str] = []
    for agent_id in AGENT_NAMES_KR:
        try:
            composed = compose_system_prompt(agent_id)
            if not composed.get("system_prompt"):
                compose_errors.append(f"{agent_id}: empty prompt")
            if "§5 회사 절대 금지" not in composed["system_prompt"]:
                compose_errors.append(f"{agent_id}: missing manifest footer")
        except Exception as exc:
            compose_errors.append(f"{agent_id}: {exc}")
    if compose_errors:
        out.append(CheckResult(
            "§2.3", "system prompt 합성", FAIL,
            detail="; ".join(compose_errors),
        ))
    else:
        out.append(CheckResult("§2.3", "system prompt 합성", PASS))
    return out


# =========================================================================
# Section 3 — 운영 인프라
# =========================================================================

def section_3_infra() -> list[CheckResult]:
    out: list[CheckResult] = []

    # 3.1 client-ops folder layout (auto check)
    required_dirs = ["agents", "config", "scripts", "shared", "tasks", "reports", "logs"]
    missing = [d for d in required_dirs if not (ROOT / d).exists()]
    if missing:
        out.append(CheckResult("§3.1", "client-ops 폴더 레이아웃", FAIL, detail=f"missing dirs: {missing}"))
    else:
        out.append(CheckResult("§3.1", "client-ops 폴더 레이아웃", PASS))

    # 3.2 EC2 ping — manual
    out.append(CheckResult(
        "§3.2", "EC2 인스턴스 ping",
        SKIP_MANUAL,
        detail="자동 점검 범위 외 — 운영자가 ssh / curl health endpoint로 확인",
    ))

    # 3.3 DB connectivity — manual
    out.append(CheckResult(
        "§3.3", "DB / 외부 시스템 연결",
        SKIP_MANUAL,
        detail="자동 점검 범위 외 — psql / 외부 API smoke test로 확인",
    ))
    return out


# =========================================================================
# Section 4 — LLM 운영
# =========================================================================

def section_4_llm() -> list[CheckResult]:
    out: list[CheckResult] = []
    if not CONFIG_PATH.exists():
        out.append(CheckResult("§4.1", "agent_models.json 존재", FAIL))
        return out
    cfg = load_model_config()

    # 4.1 all 5 agents present
    agents = cfg.get("agents", {})
    missing = [a for a in AGENT_NAMES_KR if a not in agents]
    if missing:
        out.append(CheckResult("§4.1", "5명 모델 매핑", FAIL, detail=f"missing: {missing}"))
    else:
        out.append(CheckResult("§4.1", "5명 모델 매핑", PASS))

    # 4.2 fallback rules: everyone has fallback EXCEPT 02_ops_operator (must be null)
    fallback_issues: list[str] = []
    for agent_id in AGENT_NAMES_KR:
        ent = agents.get(agent_id, {})
        fb = ent.get("fallback_provider")
        if agent_id == "02_ops_operator":
            if fb is not None:
                fallback_issues.append(f"{agent_id}: must be null (정총괄 명세), got {fb}")
        else:
            if not fb:
                fallback_issues.append(f"{agent_id}: fallback_provider missing")
    if fallback_issues:
        out.append(CheckResult("§4.2", "fallback 정책", FAIL, detail="; ".join(fallback_issues)))
    else:
        out.append(CheckResult("§4.2", "fallback 정책 (박실행 null + 나머지 설정)", PASS))

    # 4.3 mock mode works end-to-end (no API key required)
    try:
        os.environ["LLM_PROVIDER"] = "mock"
        res = complete("01_onboarding_manager", "preflight smoke", "preflight smoke prompt", use_llm=True)
        if res.get("used") and res.get("text"):
            out.append(CheckResult("§4.3", "mock 모드 동작", PASS,
                                   detail=f"provider={res.get('provider')} model={res.get('model')}"))
        else:
            out.append(CheckResult("§4.3", "mock 모드 동작", FAIL, detail=str(res)))
    except Exception as exc:
        out.append(CheckResult("§4.3", "mock 모드 동작", FAIL, detail=str(exc)))
    finally:
        os.environ.pop("LLM_PROVIDER", None)

    # 4.4 timeouts / max_retries configured
    defaults = cfg.get("defaults", {})
    if "timeout_seconds" in defaults and "max_retries" in defaults:
        out.append(CheckResult("§4.4", "timeout / max_retries", PASS,
                               detail=f"{defaults['timeout_seconds']}s / {defaults['max_retries']} retries"))
    else:
        out.append(CheckResult("§4.4", "timeout / max_retries", WARN,
                               detail="defaults.timeout_seconds 또는 max_retries 미설정"))
    return out


# =========================================================================
# Section 5 — 5명 자기소개 시뮬레이션
# =========================================================================

def section_5_intro() -> list[CheckResult]:
    out: list[CheckResult] = []
    os.environ["LLM_PROVIDER"] = "mock"
    try:
        for agent_id, name_kr in AGENT_NAMES_KR.items():
            try:
                composed = compose_system_prompt(agent_id)
                res = complete(
                    agent_id, composed["system_prompt"],
                    "당신의 정체성과 핵심 가치를 한 문단으로 자기소개하십시오.",
                    use_llm=True,
                )
                if res.get("used") and res.get("text"):
                    out.append(CheckResult(
                        f"§5.{agent_id[:2]}", f"{name_kr} 자기소개 (mock)", PASS,
                        detail=f"len={len(res.get('text', ''))}",
                    ))
                else:
                    out.append(CheckResult(
                        f"§5.{agent_id[:2]}", f"{name_kr} 자기소개 (mock)", FAIL,
                        detail=str(res),
                    ))
            except Exception as exc:
                out.append(CheckResult(
                    f"§5.{agent_id[:2]}", f"{name_kr} 자기소개 (mock)", FAIL, detail=str(exc),
                ))
    finally:
        os.environ.pop("LLM_PROVIDER", None)
    return out


# =========================================================================
# Section 6 — 핸드오프 End-to-End
# =========================================================================

def section_6_handoff() -> list[CheckResult]:
    out: list[CheckResult] = []
    os.environ["LLM_PROVIDER"] = "mock"
    try:
        from run_pipeline import simulate

        jsonl_path, report_path, records = simulate(
            week=99, client_ref="preflight_check", use_llm=False,
        )
        if records:
            out.append(CheckResult(
                "§6.1", "5명 핸드오프 1주 시뮬레이션", PASS,
                detail=f"{len(records)} steps, log={jsonl_path.name}",
            ))
        else:
            out.append(CheckResult("§6.1", "5명 핸드오프 1주 시뮬레이션", FAIL, detail="0 records"))

        # P0 case must appear at least once (Day 5 refund in current SIMULATED_INBOUND).
        p0_steps = [r for r in records if getattr(r, "policy_fired", False)]
        if p0_steps:
            out.append(CheckResult(
                "§6.2", "시뮬레이션 중 P0 게이트 발동", PASS,
                detail=f"{len(p0_steps)} policy hit(s)",
            ))
        else:
            out.append(CheckResult(
                "§6.2", "시뮬레이션 중 P0 게이트 발동", FAIL,
                detail="현재 SIMULATED_INBOUND에 환불 케이스가 있어야 합니다",
            ))

        # Adam was notified at least once.
        adam_steps = [r for r in records if getattr(r, "handoff_to_adam", False)]
        if adam_steps:
            out.append(CheckResult(
                "§6.3", "Adam 에스컬레이션 경로 도달", PASS,
                detail=f"{len(adam_steps)} adam handoff(s)",
            ))
        else:
            out.append(CheckResult("§6.3", "Adam 에스컬레이션 경로 도달", FAIL))
    except Exception as exc:
        out.append(CheckResult("§6.1", "5명 핸드오프 1주 시뮬레이션", FAIL, detail=str(exc)))
    finally:
        os.environ.pop("LLM_PROVIDER", None)
    return out


# =========================================================================
# Section 7 — 컴플레인 시뮬레이션 (9개 트리거)
# =========================================================================

# 9 distinct trigger categories. Each entry: (sub_id, label, keyword).
COMPLAINT_TRIGGERS: list[tuple[str, str, str]] = [
    ("§7.1", "환불 키워드", "환불해주세요"),
    ("§7.2", "변호사 키워드", "변호사와 상의해보겠습니다"),
    ("§7.3", "고소 키워드", "고소하겠습니다"),
    ("§7.4", "소송 키워드", "소송 진행할 예정입니다"),
    ("§7.5", "진단 키워드 (의료)", "진단 결과를 알려주세요"),
    ("§7.6", "처방 키워드 (의료)", "처방전을 발급해주세요"),
    ("§7.7", "주민번호 키워드 (개인정보)", "주민번호 알려드릴까요"),
    ("§7.8", "자살 키워드 (생명위협)", "자살하고 싶어요"),
    ("§7.9", "협박 키워드", "협박하시는 건가요"),
]


def section_7_complaint() -> list[CheckResult]:
    out: list[CheckResult] = []
    for sub_id, label, sample_text in COMPLAINT_TRIGGERS:
        packet = parse_packet(
            f"TASK ID: PRE-CHECK-{sub_id.replace('§', '').replace('.', '-')}\n"
            f"TASK CODE: CS-INCOMING\n"
            f"PRIORITY: P0\n"
            f"CONTEXT:\n"
            f"- 고객이 카카오 알림톡으로 \"{sample_text}\" 메시지를 보냈습니다.\n"
        )
        result = policy_check("03_cs_manager", packet)
        if result is None:
            out.append(CheckResult(
                sub_id, label, FAIL,
                detail=f"policy_check returned None — trigger '{sample_text}' not detected",
                fix_hint="agents/03_cs_manager/persona.md 의 trigger 키워드 재확인 (별도 PR 권장)",
            ))
            continue
        policy = result.get("policy") or {}
        decision = policy.get("decision")
        if decision != "ESCALATE_TO_ADAM":
            out.append(CheckResult(
                sub_id, label, FAIL,
                detail=f"decision={decision} (expected ESCALATE_TO_ADAM)",
            ))
            continue
        if not policy.get("handoff_to_adam"):
            out.append(CheckResult(
                sub_id, label, FAIL,
                detail="handoff_to_adam flag missing",
            ))
            continue
        text = result.get("text", "")
        if "자동 응답: 보내지 않음" not in text:
            out.append(CheckResult(
                sub_id, label, WARN,
                detail="escalation card produced but auto-response disclaimer missing",
            ))
            continue
        out.append(CheckResult(sub_id, label, PASS, detail=f"hits={policy.get('hits')}"))
    return out


# =========================================================================
# Section 8 — commerce 인터페이스 정합성
# =========================================================================

def section_8_commerce() -> list[CheckResult]:
    out: list[CheckResult] = []
    required = {
        "commerce_integration.md": ["우리 → 커머스", "커머스 → 우리"],
        "handoff_to_commerce.md": ["PII", "집계", "업종"],
        "handoff_from_commerce.md": ["신규 자동화", "시장 트렌드", "신규 카탈로그", "리스크 검수"],
    }
    for fname, must in required.items():
        path = SHARED_DIR / fname
        if not path.exists():
            out.append(CheckResult(f"§8.{fname[:3]}", f"shared/{fname} 존재", FAIL))
            continue
        text = path.read_text(encoding="utf-8")
        missing = [m for m in must if m not in text]
        if missing:
            out.append(CheckResult(
                f"§8.{fname[:3]}", f"shared/{fname} 핵심 키워드",
                FAIL,
                detail=f"missing: {missing}",
            ))
        else:
            out.append(CheckResult(f"§8.{fname[:3]}", f"shared/{fname} 정합성", PASS))
    return out


# =========================================================================
# Section 9 — 모니터링/관측성
# =========================================================================

def section_9_observability() -> list[CheckResult]:
    out: list[CheckResult] = []

    # 9.1 runtime/llm_usage.jsonl is wired (file exists after any LLM call)
    runtime_log = ROOT / "runtime" / "llm_usage.jsonl"
    if runtime_log.exists() and runtime_log.stat().st_size > 0:
        out.append(CheckResult(
            "§9.1", "LLM usage 로그 적재", PASS,
            detail=f"{runtime_log.stat().st_size} bytes",
        ))
    else:
        out.append(CheckResult(
            "§9.1", "LLM usage 로그 적재", WARN,
            detail="runtime/llm_usage.jsonl 비어있음 (mock §4.3가 먼저 통과해야 채워짐)",
        ))

    # 9.2 logs/ directory exists with .gitkeep
    if (ROOT / "logs" / ".gitkeep").exists():
        out.append(CheckResult("§9.2", "logs/ 폴더 + gitkeep", PASS))
    else:
        out.append(CheckResult("§9.2", "logs/ 폴더 + gitkeep", FAIL))

    # 9.3 Telegram / Slack webhook configured — manual
    out.append(CheckResult(
        "§9.3", "Telegram / Slack 알림 채널",
        SKIP_MANUAL,
        detail="실 토큰은 .env에만, 본 스크립트는 점검 안 함",
    ))
    return out


# =========================================================================
# Sections 10–12 — manual
# =========================================================================

def section_10_recovery() -> list[CheckResult]:
    return [CheckResult(
        "§10", "백업 / 복구 리허설",
        SKIP_MANUAL,
        detail="운영자가 분기 1회 시나리오 리허설 별도 실행",
    )]


def section_11_human_ops() -> list[CheckResult]:
    return [CheckResult(
        "§11", "사람 운영 준비 (정총괄 + Adam SLA)",
        SKIP_MANUAL,
        detail="조직 합의 사항, 코드로 점검 불가",
    )]


def section_12_signoff() -> list[CheckResult]:
    return [CheckResult(
        "§12", "Adam 최종 서명",
        SKIP_MANUAL,
        detail="pre_launch_checklist.md 하단 서명 (이름 + 날짜) 직접 추가",
    )]


# =========================================================================
# Section 13 — 판매자 계정/채널 준비 (Seller Account Readiness)
# =========================================================================

# Sensitive value shapes that must NEVER appear in tracked files under
# teams/client-ops-team/ (config/, shared/, agents/, scripts/, tasks/).
# The script reports counts only — never the matching content.
SENSITIVE_PATTERNS_13: list[tuple[str, re.Pattern[str]]] = [
    ("KR_BUSINESS_REG_NO", re.compile(r"\b\d{3}-\d{2}-\d{5}\b")),
    ("KR_RESIDENT_NO", re.compile(r"\b\d{6}-\d{7}\b")),
    ("KR_BANK_ACCT", re.compile(r"\b\d{3}-\d{6}-\d{2,5}\b")),
    # Card formats: 13-19 consecutive digits OR canonical 4-4-4-4 grouping.
    # Avoids false-positives on date-suffixed IDs like "msg-2026-05-21-00231".
    ("CARD_NUMBER", re.compile(r"\b(?:\d{13,19}|\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{3,4})\b")),
    ("US_DUNS", re.compile(r"\bDUNS[: ]\d{9}\b", re.IGNORECASE)),
    ("AWS_ACCESS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AMAZON_REFRESH_TOKEN", re.compile(r"Atzr\|[A-Za-z0-9_\-]{20,}")),
    ("COUPANG_VENDOR_ID", re.compile(r"\bA\d{8,12}\b")),
]

# Channel API key env-var NAMES we expect (existence check only — values are
# never read or printed by this script).
CHANNEL_KEY_VARS = [
    "COUPANG_VENDOR_ID",
    "COUPANG_ACCESS_KEY",
    "COUPANG_SECRET_KEY",
    "AMAZON_SELLER_ID",
    "AMAZON_MARKETPLACE_ID",
    "AMAZON_SP_API_REFRESH_TOKEN",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
]


def _scan_for_sensitive(root_dir: Path, skip_dirs: set[str]) -> dict[str, int]:
    """Return {pattern_name: hit_count}. Never returns the matched strings."""
    counts: dict[str, int] = {name: 0 for name, _ in SENSITIVE_PATTERNS_13}
    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(seg in path.parts for seg in skip_dirs):
            continue
        if path.suffix in {".pyc", ".lock"}:
            continue
        if path.name in {".gitkeep", "channel_accounts.json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for name, pat in SENSITIVE_PATTERNS_13:
            if pat.search(text):
                counts[name] += 1
    return counts


def section_13_seller_readiness() -> list[CheckResult]:
    out: list[CheckResult] = []
    seller_doc = SHARED_DIR / "seller_account_readiness.md"
    sop_doc = SHARED_DIR / "channel_ops_sop.md"
    integration_doc = SHARED_DIR / "commerce_integration.md"

    # 13.1 seller_account_readiness.md exists + has core sections
    must_in_seller = [
        "공통 준비 항목",
        "사업자",
        "정산",
        "반품지",
        "CS 연락처",
        "API 키 발급",
        "절대 커밋 금지",
    ]
    if not seller_doc.exists():
        out.append(CheckResult(
            "§13.1", "seller_account_readiness.md 존재", FAIL,
            detail=f"missing file: {seller_doc.relative_to(ROOT)}",
            fix_hint="shared/seller_account_readiness.md 작성 (본 PR에 포함)",
        ))
    else:
        text = seller_doc.read_text(encoding="utf-8")
        missing = [m for m in must_in_seller if m not in text]
        if missing:
            out.append(CheckResult(
                "§13.1", "seller_account_readiness.md 핵심 섹션", FAIL,
                detail=f"missing markers: {missing}",
            ))
        else:
            out.append(CheckResult("§13.1", "seller_account_readiness.md 핵심 섹션", PASS))

    # 13.2 channel_ops_sop.md exists + has core sections
    must_in_sop = [
        "게시 전 Adam 승인",
        "환불",
        "반품",
        "P0",
        "channel_submission",
        "검수",
    ]
    if not sop_doc.exists():
        out.append(CheckResult("§13.2", "channel_ops_sop.md 존재", FAIL))
    else:
        text = sop_doc.read_text(encoding="utf-8")
        missing = [m for m in must_in_sop if m not in text]
        if missing:
            out.append(CheckResult(
                "§13.2", "channel_ops_sop.md 핵심 섹션", FAIL,
                detail=f"missing markers: {missing}",
            ))
        else:
            out.append(CheckResult("§13.2", "channel_ops_sop.md 핵심 섹션", PASS))

    # 13.3 4 new signal types are defined in commerce_integration.md
    must_signals = [
        "channel_submission_ready",
        "seller_account_blocker",
        "post_publish_monitoring_request",
        "refund_or_claim_escalation",
    ]
    if not integration_doc.exists():
        out.append(CheckResult("§13.3", "commerce_integration.md 4신호 정의", FAIL))
    else:
        text = integration_doc.read_text(encoding="utf-8")
        missing = [s for s in must_signals if s not in text]
        if missing:
            out.append(CheckResult(
                "§13.3", "commerce_integration.md 4신호 정의", FAIL,
                detail=f"missing signals: {missing}",
                fix_hint="commerce_integration.md '채널 운영 신호' 섹션 추가",
            ))
        else:
            out.append(CheckResult(
                "§13.3", "commerce_integration.md 4신호 정의", PASS,
                detail=f"{len(must_signals)}/{len(must_signals)} signals",
            ))

    # 13.3b root canonical contract has accepted the v2 signal set.
    if not CONTRACT_DOC.exists():
        out.append(CheckResult("§13.3b", "canonical handoff contract v2", FAIL,
                               detail=f"missing file: {CONTRACT_DOC.relative_to(REPO_ROOT)}"))
    else:
        contract_text = CONTRACT_DOC.read_text(encoding="utf-8")
        missing = [s for s in must_signals if s not in contract_text]
        if "2026-05-22.v2" not in contract_text or missing:
            out.append(CheckResult(
                "§13.3b", "canonical handoff contract v2", FAIL,
                detail=f"version_or_signals_missing: version={'2026-05-22.v2' in contract_text}, missing={missing}",
                fix_hint="shared/handoff_contracts/commerce_client_ops_contract.md를 v2 canonical로 갱신",
            ))
        else:
            out.append(CheckResult(
                "§13.3b", "canonical handoff contract v2", PASS,
                detail="2026-05-22.v2 + 4 channel signals present",
            ))

    # 13.4 Sensitive-value grep across the client-ops tree.
    # Never prints matched content — only pattern names and counts.
    skip_dirs = {"runtime", "reports", "logs", "__pycache__"}
    counts = _scan_for_sensitive(ROOT, skip_dirs)
    nonzero = {k: v for k, v in counts.items() if v > 0}
    if nonzero:
        out.append(CheckResult(
            "§13.4", "민감정보 패턴 grep", FAIL,
            detail=f"sensitive pattern hits (counts only): {nonzero}",
            fix_hint="해당 파일에서 값 제거 후 재커밋. 키는 즉시 로테이션. (본 스크립트는 매치된 문자열을 출력하지 않음)",
        ))
    else:
        out.append(CheckResult(
            "§13.4", "민감정보 패턴 grep", PASS,
            detail=f"scanned {len(SENSITIVE_PATTERNS_13)} pattern types, all 0 hits",
        ))

    # 13.5 Channel API key env-var existence (NOT values).
    # Reports presence/absence only — never reads the value.
    load_dotenv()
    set_vars = [v for v in CHANNEL_KEY_VARS if os.environ.get(v, "").strip()]
    unset_vars = [v for v in CHANNEL_KEY_VARS if not os.environ.get(v, "").strip()]
    if set_vars and unset_vars:
        out.append(CheckResult(
            "§13.5", "채널 API 키 env 존재", WARN,
            detail=f"partial: set={len(set_vars)} unset={len(unset_vars)} "
                   f"(값은 출력하지 않음; 변수명 목록은 코드의 CHANNEL_KEY_VARS 참조)",
        ))
    elif set_vars and not unset_vars:
        out.append(CheckResult(
            "§13.5", "채널 API 키 env 존재 (전부 설정됨)", PASS,
            detail=f"all {len(CHANNEL_KEY_VARS)} channel env vars present (values never inspected)",
        ))
    else:
        out.append(CheckResult(
            "§13.5", "채널 API 키 env 존재", SKIP_MANUAL,
            detail=f"channel keys not set yet — expected before APPROVE_AND_GO_LIVE. "
                   f"unset count: {len(unset_vars)} (값은 출력하지 않음)",
        ))

    # 13.6 .env.example must list channel key names (placeholders only)
    env_example = ENV_EXAMPLE.read_text(encoding="utf-8") if ENV_EXAMPLE.exists() else ""
    if not env_example:
        out.append(CheckResult("§13.6", ".env.example 채널 키 placeholder", WARN,
                               detail=".env.example 누락"))
    else:
        # Accept either explicit names or a comment block; we just check at least
        # one channel variable name is listed so operators know what to fill.
        placeholders_found = [v for v in CHANNEL_KEY_VARS if v in env_example]
        if placeholders_found:
            out.append(CheckResult(
                "§13.6", ".env.example 채널 키 placeholder", PASS,
                detail=f"{len(placeholders_found)}/{len(CHANNEL_KEY_VARS)} listed",
            ))
        else:
            out.append(CheckResult(
                "§13.6", ".env.example 채널 키 placeholder", WARN,
                detail="채널 가입 후 .env.example에 키 변수명만 추가 권고 (값 없이)",
            ))

    # 13.7 Sensitive config file is gitignored
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-v",
             "teams/client-ops-team/config/channel_accounts.json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            out.append(CheckResult(
                "§13.7", "channel_accounts.json gitignore 보호", PASS,
                detail=result.stdout.strip().split("\t")[0] if result.stdout else "",
            ))
        else:
            out.append(CheckResult(
                "§13.7", "channel_accounts.json gitignore 보호", FAIL,
                detail="루트 .gitignore에 teams/*/config/channel_accounts.json 추가 필요",
            ))
    except Exception as exc:
        out.append(CheckResult("§13.7", "channel_accounts.json gitignore 보호", WARN, detail=str(exc)))

    # 13.8–13.11 — operator-only items
    out.append(CheckResult("§13.8", "실 셀러 계정 가입", SKIP_MANUAL,
                           detail="Coupang WING / Amazon Seller Central 가입은 Adam 직접"))
    out.append(CheckResult("§13.9", "실 API 키 발급 + 권한 최소화", SKIP_MANUAL,
                           detail="Adam이 EC2 .env에 직접 입력. 본 스크립트는 값을 출력하지 않음"))
    out.append(CheckResult("§13.10", "정산 계좌 / 사업자 인증 / VAT", SKIP_MANUAL,
                           detail="외부 secure storage. 본 저장소 커밋 절대 금지"))
    out.append(CheckResult("§13.11", "Adam의 첫 APPROVE_AND_GO_LIVE", SKIP_MANUAL,
                           detail="channel_ops_sop.md §1.3 — Adam 직접 결정"))
    return out


# =========================================================================
# Section 14 — Commerce handoff importer
# =========================================================================

def _make_minimal_handoff(*, dry_run_only: bool, submit_status: str,
                          approval_status: str) -> dict:
    """Build a minimal v2 handoff for in-memory smoke tests of the importer."""
    return {
        "contract_version": "2026-05-22.v2",
        "handoff_id": "PREFLIGHT-SMOKE-001",
        "direction": "commerce_to_client_ops",
        "from_team": "commerce-agent-team",
        "to_team": "client-ops-team",
        "created_at": "2026-05-22T10:00:00+09:00",
        "week": "2026-W21",
        "source_agent": "05_ops_manager",
        "signal_type": "channel_submission_ready",
        "summary": "preflight smoke",
        "confidence": "medium",
        "requires_human_approval": True,
        "dry_run_only": dry_run_only,
        "pii_check": {k: True for k in [
            "names_removed", "contacts_removed", "business_ids_removed",
            "raw_messages_removed", "amounts_indexed",
            "medical_legal_tax_only_as_category",
        ]},
        "review": {"owner": "05_ops_manager", "decision": "PASS",
                   "decision_reason": "preflight smoke"},
        "payload": {
            "run_id": "PREFLIGHT-SMOKE",
            "opportunity_id": "PREFLIGHT-OPP",
            "package_paths": [
                "teams/commerce-agent-team/runtime/channel_submissions/pending/preflight-smoke_PREFLIGHT-OPP_coupang.json",
            ],
            "channels": ["coupang"],
            "validation_status": "draft_validated_locally",
            "approval_status": approval_status,
            "submit_status": submit_status,
            "risk_review": {"blocked": False, "risk_level": "review_required", "hard_stops": []},
            "forbidden_claims_present": False,
            "supplier_evidence_present": True,
            "category_match_seller_scope": False,
            "seller_scope_status": "not_connected_yet",
            "qa_route": ["05_coordinator_qa"],
            "do_not_disclose": ["api_key_value", "vendor_id_value"],
        },
    }


def section_14_commerce_importer() -> list[CheckResult]:
    out: list[CheckResult] = []
    importer = ROOT / "scripts" / "import_commerce_handoff.py"

    # 14.1 importer file exists
    if not importer.exists():
        out.append(CheckResult("§14.1", "import_commerce_handoff.py 존재", FAIL,
                               detail=f"missing: {importer.relative_to(ROOT)}"))
        return out
    out.append(CheckResult("§14.1", "import_commerce_handoff.py 존재", PASS))

    # 14.2 importer is importable + exposes process()/decide_qa()/ImportResult
    try:
        import importlib
        mod = importlib.import_module("import_commerce_handoff")
        for sym in ("process", "decide_qa", "ImportResult",
                    "validate_envelope", "validate_channel_submission_ready",
                    "scan_for_live_mode_and_secrets"):
            if not hasattr(mod, sym):
                out.append(CheckResult("§14.2", "importer 핵심 심볼", FAIL,
                                       detail=f"missing symbol: {sym}"))
                return out
        out.append(CheckResult("§14.2", "importer 핵심 심볼", PASS,
                               detail="process, decide_qa, ImportResult, 3 validators"))
    except Exception as exc:
        out.append(CheckResult("§14.2", "importer import 가능", FAIL, detail=str(exc)))
        return out

    # 14.3 contract version sanity
    if getattr(mod, "CONTRACT_VERSION", None) != "2026-05-22.v2":
        out.append(CheckResult("§14.3", "contract_version 상수", FAIL,
                               detail=f"got {getattr(mod, 'CONTRACT_VERSION', None)!r}"))
    else:
        out.append(CheckResult("§14.3", "contract_version 상수 (2026-05-22.v2)", PASS))

    # 14.4 in-memory smoke: a clean handoff should pass envelope + signal validators
    ok = _make_minimal_handoff(
        dry_run_only=True, submit_status="not_submitted",
        approval_status="adam_approval_required",
    )
    result = mod.ImportResult(
        handoff_id=ok["handoff_id"], signal_type=ok["signal_type"], direction=ok["direction"],
    )
    mod.validate_envelope(ok, result)
    mod.validate_channel_submission_ready(ok, result)
    mod.scan_for_live_mode_and_secrets(ok, result)
    qa = mod.decide_qa(result)
    # package files don't exist locally → W104 → QA_HOLD_NEEDS_INFO is expected
    if qa in ("QA_PASS_ESCALATE_TO_ADAM", "QA_HOLD_NEEDS_INFO") and not result.blocking:
        out.append(CheckResult("§14.4", "valid handoff in-memory smoke", PASS,
                               detail=f"qa={qa} blocking=0 warn={len(result.warns)}"))
    else:
        out.append(CheckResult("§14.4", "valid handoff in-memory smoke", FAIL,
                               detail=f"qa={qa} blocking={len(result.blocking)}"))

    # 14.5 in-memory smoke: a live-mode handoff MUST be rejected
    bad = _make_minimal_handoff(
        dry_run_only=False, submit_status="submitted",
        approval_status="approved_and_published",
    )
    result = mod.ImportResult(
        handoff_id=bad["handoff_id"], signal_type=bad["signal_type"], direction=bad["direction"],
    )
    mod.validate_envelope(bad, result)
    mod.validate_channel_submission_ready(bad, result)
    mod.scan_for_live_mode_and_secrets(bad, result)
    qa = mod.decide_qa(result)
    expected_blocking_codes = {"E007_NOT_DRY_RUN", "E102_APPROVAL_STATUS",
                               "E103_SUBMIT_STATUS", "E201_LIVE_MODE_INDICATOR"}
    actual_codes = {f.code for f in result.blocking}
    if qa == "QA_REJECT_RETURN_TO_COMMERCE" and expected_blocking_codes <= actual_codes:
        out.append(CheckResult("§14.5", "live-mode handoff is rejected", PASS,
                               detail=f"qa={qa} blocking_codes={sorted(actual_codes)}"))
    else:
        out.append(CheckResult("§14.5", "live-mode handoff is rejected", FAIL,
                               detail=f"qa={qa} missing_codes={sorted(expected_blocking_codes - actual_codes)}"))

    # 14.6 runtime/commerce_handoffs is gitignored
    try:
        result_proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-v",
             "teams/client-ops-team/runtime/commerce_handoffs/qa_queue.md"],
            capture_output=True, text=True, timeout=10,
        )
        if result_proc.returncode == 0:
            out.append(CheckResult("§14.6", "runtime/commerce_handoffs gitignore 보호", PASS))
        else:
            out.append(CheckResult("§14.6", "runtime/commerce_handoffs gitignore 보호", FAIL,
                                   detail="루트 .gitignore의 teams/*/runtime/ 규칙으로 보호되어야 함"))
    except Exception as exc:
        out.append(CheckResult("§14.6", "runtime/commerce_handoffs gitignore 보호", WARN,
                               detail=str(exc)))

    return out


# =========================================================================
# Dispatcher
# =========================================================================

SECTIONS: dict[int, tuple[str, Callable[[], list[CheckResult]]]] = {
    1: ("보안/컴플라이언스", section_1_secrets),
    2: ("페르소나 일관성", section_2_persona),
    3: ("운영 인프라", section_3_infra),
    4: ("LLM 운영", section_4_llm),
    5: ("5명 자기소개 시뮬레이션", section_5_intro),
    6: ("핸드오프 End-to-End", section_6_handoff),
    7: ("컴플레인 시뮬레이션", section_7_complaint),
    8: ("commerce 인터페이스 정합성", section_8_commerce),
    9: ("모니터링/관측성", section_9_observability),
    10: ("백업/복구", section_10_recovery),
    11: ("사람 운영 준비", section_11_human_ops),
    12: ("최종 승인", section_12_signoff),
    13: ("판매자 계정 / 채널 준비", section_13_seller_readiness),
    14: ("commerce handoff importer", section_14_commerce_importer),
}


def parse_sections(arg: str | None) -> list[int]:
    if not arg:
        return list(SECTIONS.keys())
    out: list[int] = []
    for tok in arg.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            n = int(tok)
            if n in SECTIONS:
                out.append(n)
        except ValueError:
            pass
    return out or list(SECTIONS.keys())


def run_all(sections: list[int]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for n in sections:
        title, runner = SECTIONS[n]
        results.append(CheckResult(f"§{n}", title, "INFO", detail="(section start)"))
        # We mark the header line with status INFO so it doesn't affect counts.
        results.extend(runner())
    return results


def render_report(*, results: list[CheckResult], started_at: str, sections: list[int]) -> str:
    counts = {PASS: 0, FAIL: 0, WARN: 0, SKIP_MANUAL: 0}
    for r in results:
        if r.status in counts:
            counts[r.status] += 1

    status_line = "READY FOR BETA (자동화 가능 항목 모두 통과)" if counts[FAIL] == 0 else "NOT READY FOR BETA"

    lines = [
        "# Pre-Launch Preflight Report",
        "",
        f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"시작 시각: {started_at}",
        f"대상 섹션: {', '.join(f'§{n}' for n in sections)}",
        "",
        "## Summary",
        "",
        f"- PASS: {counts[PASS]}",
        f"- FAIL: {counts[FAIL]}",
        f"- WARN: {counts[WARN]}",
        f"- SKIP_MANUAL: {counts[SKIP_MANUAL]}",
        f"- Status: {status_line}",
        "",
        "## 결과 표",
        "",
        "| Section | Title | Status | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for r in results:
        if r.status == "INFO":
            lines.append(f"| **{r.section}** | **{r.title}** | _(섹션 시작)_ |  |")
            continue
        d = (r.detail or "").replace("|", "/").replace("\n", " ")
        if len(d) > 120:
            d = d[:117] + "..."
        lines.append(f"| {r.section} | {r.title} | {r.status} | {d} |")

    fails = [r for r in results if r.status == FAIL]
    if fails:
        lines += ["", "## 실패 상세", ""]
        for r in fails:
            lines += [
                f"### {r.section} {r.title}",
                "",
                f"- detail: {r.detail}",
                f"- fix_hint: {r.fix_hint or '(없음)'}",
                "",
            ]

    lines += ["", "## 운영 노트", "",
              "- 본 리포트는 .gitignore 대상이므로 커밋되지 않습니다.",
              "- SKIP_MANUAL 항목은 사람이 별도로 통과 확인 후 pre_launch_checklist.md '통과 기록' 표에 일자 기입.",
              "- FAIL 항목은 fix_hint를 따라 별도 PR로 처리합니다 (preflight_check.py 본 PR에서 코드 외 영역 수정 금지).",
             ]
    return "\n".join(lines) + "\n"


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", default=None, help="Comma-separated section numbers, e.g. 1,2,7")
    parser.add_argument("--output", default=None, help="Path to write report (default: reports/preflight_YYYYMMDD.md)")
    parser.add_argument(
        "--simulate-no-triggers",
        action="store_true",
        help="Demo FAIL path: monkey-patch P0_ESCALATION_KEYWORDS to empty before running §7.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = parse_sections(args.section)

    load_dotenv()

    if args.simulate_no_triggers:
        # Inject a temporary empty trigger list. This proves the FAIL path works
        # without modifying agents/**/*.md or run_agent.py.
        original = list(run_agent.P0_ESCALATION_KEYWORDS)
        run_agent.P0_ESCALATION_KEYWORDS.clear()
        try:
            results = run_all(sections)
        finally:
            run_agent.P0_ESCALATION_KEYWORDS.extend(original)
    else:
        try:
            results = run_all(sections)
        except Exception as exc:
            print(f"FATAL: preflight aborted: {exc}", file=sys.stderr)
            return 2

    # Console print
    counts = {PASS: 0, FAIL: 0, WARN: 0, SKIP_MANUAL: 0}
    for r in results:
        if r.status == "INFO":
            print(f"\n--- {r.section} {r.title} ---")
            continue
        print(render_status(r))
        if args.verbose and r.detail:
            print(f"         detail: {r.detail}")
        if r.status == FAIL:
            print(f"         expected: PASS")
            print(f"         actual: {r.detail}")
            if r.fix_hint:
                print(f"         fix: {r.fix_hint}")
        if r.status in counts:
            counts[r.status] += 1

    print()
    print(
        f"Summary: {counts[PASS]} PASS / {counts[FAIL]} FAIL / "
        f"{counts[SKIP_MANUAL]} SKIP_MANUAL / {counts[WARN]} WARN"
    )
    status_line = "READY FOR BETA (자동화 가능 항목 모두 통과)" if counts[FAIL] == 0 else "NOT READY FOR BETA"
    print(f"Status: {status_line}")

    # Write report
    if args.output:
        report_path = Path(args.output)
    else:
        report_path = DEFAULT_OUTPUT_DIR / f"preflight_{datetime.now().strftime('%Y%m%d')}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(results=results, started_at=started_at, sections=sections),
        encoding="utf-8",
    )
    print(f"report: {report_path}")

    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    raise SystemExit(main())
