"""Receive and QA a commerce-to-client-ops handoff JSON.

Validates the v2 canonical envelope and signal-specific payload, with extra
hard rules for `channel_submission_ready` (the only signal type whose payload
references actual channel packages that could go live by mistake).

Outputs one of three QA states:
  - QA_PASS_ESCALATE_TO_ADAM       (exit 0)
  - QA_REJECT_RETURN_TO_COMMERCE   (exit 1)
  - QA_HOLD_NEEDS_INFO             (exit 0, but flagged in the queue)

On any non-REJECT outcome the handoff is copied to
`runtime/commerce_handoffs/<handoff_id>.json` and a card is appended to
`runtime/commerce_handoffs/qa_queue.md`. Both are gitignored.

This script never publishes, never contacts a channel, and never prints the
content of fields it considers sensitive — only field names and counts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_client import configure_stdout


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
RUNTIME_DIR = ROOT / "runtime" / "commerce_handoffs"
QA_QUEUE_PATH = RUNTIME_DIR / "qa_queue.md"

CONTRACT_VERSION = "2026-05-22.v2"
EXPECTED_DIRECTION = "commerce_to_client_ops"
EXPECTED_TO_TEAM = "client-ops-team"
EXPECTED_FROM_TEAM = "commerce-agent-team"

# Signal types this importer recognizes. channel_submission_ready is the
# primary path; others are accepted with structural validation only.
PRIMARY_SIGNAL = "channel_submission_ready"
KNOWN_SIGNAL_TYPES = {
    "new_automation_candidate",
    "market_trend",
    "tool_change_alert",
    "rejected_for_info",
    "collaboration_request",
    PRIMARY_SIGNAL,
    "post_publish_monitoring_request",
}

PII_CHECK_FIELDS = [
    "names_removed",
    "contacts_removed",
    "business_ids_removed",
    "raw_messages_removed",
    "amounts_indexed",
    "medical_legal_tax_only_as_category",
]

REQUIRED_PAYLOAD_FOR_PRIMARY = {
    "run_id",
    "opportunity_id",
    "package_paths",
    "validation_status",
    "approval_status",
    "risk_review",
    "forbidden_claims_present",
    "supplier_evidence_present",
}

# Live-mode indicators anywhere in the serialized JSON. Presence of any of
# these strings is BLOCKING — this importer must never see a live publish.
LIVE_MODE_STRINGS = [
    '"submit_status": "submitted"',
    '"submit_status": "live"',
    '"submit_status": "publishing"',
    '"submit_status": "sent_to_channel"',
    '"approval_status": "approved_and_published"',
    '"mode": "production"',
    '"mode": "live"',
    '"mode": "publish"',
    '"dry_run_only": false',
    '"requires_human_approval": false',
]

# Sensitive-VALUE shapes. We never print the matched bytes — only the pattern
# name and a count, so an operator can investigate via secure tooling.
SENSITIVE_VALUE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("KR_BUSINESS_REG_NO", re.compile(r"\b\d{3}-\d{2}-\d{5}\b")),
    ("KR_RESIDENT_NO", re.compile(r"\b\d{6}-\d{7}\b")),
    ("KR_BANK_ACCT", re.compile(r"\b\d{3}-\d{6}-\d{2,5}\b")),
    ("CARD_NUMBER", re.compile(r"\b(?:\d{13,19}|\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{3,4})\b")),
    ("AWS_ACCESS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AMAZON_SP_REFRESH", re.compile(r"Atzr\|[A-Za-z0-9_\-]{20,}")),
    ("OPENAI_KEY", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("ANTHROPIC_KEY", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("GOOGLE_KEY", re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}")),
    ("RAW_PHONE_KR", re.compile(r"\b01[0-9][- ]?\d{3,4}[- ]?\d{4}\b")),
    ("EMAIL_ADDRESS", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
]


# ---------------------- finding model ----------------------

BLOCKING = "BLOCKING"
WARN = "WARN"
INFO = "INFO"


@dataclass
class Finding:
    severity: str  # BLOCKING / WARN / INFO
    code: str
    field_path: str
    message: str


@dataclass
class ImportResult:
    handoff_id: str | None
    signal_type: str | None
    direction: str | None
    findings: list[Finding] = field(default_factory=list)
    qa_status: str = ""
    stored_path: str | None = None

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == BLOCKING]

    @property
    def warns(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARN]


# ---------------------- validators ----------------------

def validate_envelope(handoff: dict, result: ImportResult) -> None:
    cv = handoff.get("contract_version")
    if cv != CONTRACT_VERSION:
        result.add(Finding(BLOCKING, "E001_CONTRACT_VERSION", "contract_version",
                           f"expected {CONTRACT_VERSION}, got {cv!r}"))

    direction = handoff.get("direction")
    if direction != EXPECTED_DIRECTION:
        result.add(Finding(BLOCKING, "E002_WRONG_DIRECTION", "direction",
                           f"expected {EXPECTED_DIRECTION!r}, got {direction!r}"))

    if handoff.get("from_team") != EXPECTED_FROM_TEAM:
        result.add(Finding(BLOCKING, "E003_FROM_TEAM", "from_team",
                           f"expected {EXPECTED_FROM_TEAM!r}"))
    if handoff.get("to_team") != EXPECTED_TO_TEAM:
        result.add(Finding(BLOCKING, "E004_TO_TEAM", "to_team",
                           f"expected {EXPECTED_TO_TEAM!r}"))

    if not handoff.get("handoff_id"):
        result.add(Finding(BLOCKING, "E005_HANDOFF_ID_MISSING", "handoff_id", "missing"))

    if not handoff.get("created_at"):
        result.add(Finding(WARN, "W001_CREATED_AT_MISSING", "created_at", "missing"))

    if handoff.get("requires_human_approval") is not True:
        result.add(Finding(BLOCKING, "E006_REQUIRES_APPROVAL", "requires_human_approval",
                           "must be true"))
    if handoff.get("dry_run_only") is not True:
        result.add(Finding(BLOCKING, "E007_NOT_DRY_RUN", "dry_run_only",
                           "must be true"))

    pii_check = handoff.get("pii_check") or {}
    for k in PII_CHECK_FIELDS:
        if pii_check.get(k) is not True:
            result.add(Finding(BLOCKING, "E008_PII_CHECK_FALSE",
                               f"pii_check.{k}",
                               f"pii_check.{k} must be true"))

    review = handoff.get("review") or {}
    if review.get("decision") not in ("PASS",):
        result.add(Finding(BLOCKING, "E009_REVIEW_DECISION",
                           "review.decision",
                           f"expected 'PASS', got {review.get('decision')!r}"))

    signal = handoff.get("signal_type")
    if signal not in KNOWN_SIGNAL_TYPES:
        result.add(Finding(BLOCKING, "E010_UNKNOWN_SIGNAL", "signal_type",
                           f"unknown signal_type {signal!r}"))


def validate_channel_submission_ready(handoff: dict, result: ImportResult) -> None:
    payload = handoff.get("payload") or {}
    missing = REQUIRED_PAYLOAD_FOR_PRIMARY - set(payload.keys())
    for k in sorted(missing):
        result.add(Finding(BLOCKING, "E101_PAYLOAD_MISSING_FIELD",
                           f"payload.{k}", "required field missing"))

    if payload.get("approval_status") != "adam_approval_required":
        result.add(Finding(BLOCKING, "E102_APPROVAL_STATUS",
                           "payload.approval_status",
                           f"expected 'adam_approval_required', got {payload.get('approval_status')!r}"))

    submit_status = payload.get("submit_status", "not_submitted")
    if submit_status != "not_submitted":
        result.add(Finding(BLOCKING, "E103_SUBMIT_STATUS",
                           "payload.submit_status",
                           f"must be 'not_submitted', got {submit_status!r}"))

    validation_status = payload.get("validation_status")
    if validation_status not in ("draft_validated_locally", "draft_pending_review"):
        result.add(Finding(WARN, "W101_VALIDATION_STATUS",
                           "payload.validation_status",
                           f"unexpected value {validation_status!r}"))

    risk_review = payload.get("risk_review") or {}
    if risk_review.get("blocked") is True:
        result.add(Finding(BLOCKING, "E104_RISK_BLOCKED",
                           "payload.risk_review.blocked",
                           "risk_review.blocked=true must not reach client-ops QA"))

    if payload.get("forbidden_claims_present") is True:
        result.add(Finding(BLOCKING, "E105_FORBIDDEN_CLAIMS",
                           "payload.forbidden_claims_present",
                           "forbidden_claims_present must be false"))

    # supplier_evidence_present false is a meaningful WARN — Adam should know.
    if payload.get("supplier_evidence_present") is False:
        result.add(Finding(WARN, "W102_NO_SUPPLIER_EVIDENCE",
                           "payload.supplier_evidence_present",
                           "supplier evidence missing — request before go-live"))

    # category_match_seller_scope: False is currently expected (no sellers
    # connected). We only warn so the QA card surfaces it.
    if payload.get("category_match_seller_scope") is False:
        seller_scope = payload.get("seller_scope_status")
        if seller_scope == "not_connected_yet":
            result.add(Finding(INFO, "I101_SELLER_SCOPE_PRE_LAUNCH",
                               "payload.seller_scope_status",
                               "no seller connected yet — re-check after API keys issued"))
        else:
            result.add(Finding(WARN, "W103_SELLER_SCOPE_MISMATCH",
                               "payload.category_match_seller_scope",
                               f"category outside connected seller scope ({seller_scope!r})"))

    # do_not_disclose must be a list of field NAMES — never actual values.
    do_not_disclose = payload.get("do_not_disclose") or []
    if not isinstance(do_not_disclose, list):
        result.add(Finding(BLOCKING, "E106_DO_NOT_DISCLOSE_SHAPE",
                           "payload.do_not_disclose",
                           "must be a list of field names"))
    else:
        # Field names must be short tokens like "api_key_value". Reject any
        # entry that looks like an actual key (long alphanumeric, presence of
        # url-like or token-like patterns).
        suspicious = [
            i for i, v in enumerate(do_not_disclose)
            if not isinstance(v, str) or len(v) > 60 or any(c.isspace() for c in v)
        ]
        if suspicious:
            result.add(Finding(BLOCKING, "E107_DO_NOT_DISCLOSE_VALUE",
                               "payload.do_not_disclose",
                               f"entries at {suspicious} look like values, not field names"))

    package_paths = payload.get("package_paths") or []
    if not isinstance(package_paths, list) or not package_paths:
        result.add(Finding(BLOCKING, "E108_PACKAGE_PATHS_EMPTY",
                           "payload.package_paths",
                           "must list at least one channel package path"))
    else:
        missing_files: list[str] = []
        for rel in package_paths:
            if not isinstance(rel, str):
                result.add(Finding(BLOCKING, "E109_PATH_NOT_STRING",
                                   "payload.package_paths", "non-string entry"))
                continue
            # Paths must stay inside commerce runtime (read-only access).
            if not rel.startswith("teams/commerce-agent-team/runtime/channel_submissions/"):
                result.add(Finding(BLOCKING, "E110_PATH_OUTSIDE_COMMERCE",
                                   f"payload.package_paths[{rel!r}]",
                                   "must point inside commerce runtime channel_submissions"))
                continue
            absolute = REPO_ROOT / rel
            if not absolute.exists():
                missing_files.append(rel)
        if missing_files:
            # Channel packages live in commerce gitignored runtime/ — on a
            # fresh checkout they may not be present locally. We surface as
            # WARN so QA can request them from commerce instead of rejecting.
            result.add(Finding(WARN, "W104_PACKAGE_FILES_MISSING",
                               "payload.package_paths",
                               f"{len(missing_files)} of {len(package_paths)} package file(s) not "
                               "accessible from this checkout"))


def scan_for_live_mode_and_secrets(handoff: dict, result: ImportResult) -> None:
    raw = json.dumps(handoff, ensure_ascii=False)

    for needle in LIVE_MODE_STRINGS:
        if needle in raw:
            result.add(Finding(BLOCKING, "E201_LIVE_MODE_INDICATOR",
                               "(serialized handoff)",
                               f"live/publish indicator detected: {needle!r}"))

    counts: dict[str, int] = {}
    for name, pat in SENSITIVE_VALUE_PATTERNS:
        n = len(pat.findall(raw))
        if n:
            counts[name] = n
    # EMAIL_ADDRESS may have benign cases like "support@example.com" in v2
    # samples; we still surface as WARN so QA can examine.
    if counts:
        only_email = list(counts.keys()) == ["EMAIL_ADDRESS"]
        sev = WARN if only_email else BLOCKING
        code = "W202_EMAIL_DETECTED" if only_email else "E202_SENSITIVE_VALUE"
        result.add(Finding(
            sev, code, "(serialized handoff)",
            f"sensitive value patterns (counts only): {counts}",
        ))


# ---------------------- QA decision ----------------------

def decide_qa(result: ImportResult) -> str:
    if result.blocking:
        return "QA_REJECT_RETURN_TO_COMMERCE"
    if result.warns:
        return "QA_HOLD_NEEDS_INFO"
    return "QA_PASS_ESCALATE_TO_ADAM"


# ---------------------- side effects ----------------------

def store_handoff(handoff: dict, src_path: Path) -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    handoff_id = handoff.get("handoff_id") or f"unknown-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    safe_id = re.sub(r"[^A-Za-z0-9._\-]", "_", handoff_id)
    dest = RUNTIME_DIR / f"{safe_id}.json"
    dest.write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def append_qa_card(result: ImportResult, stored_path: Path, source: Path) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    findings_lines = []
    for f in result.findings:
        findings_lines.append(f"  - [{f.severity}] {f.code} @ {f.field_path}: {f.message}")
    findings_block = "\n".join(findings_lines) if findings_lines else "  - (no findings)"
    block = (
        "\n\n"
        f"## {result.handoff_id or '(unknown)'}\n\n"
        f"- received_at: {datetime.now().isoformat(timespec='seconds')}\n"
        f"- direction: {result.direction}\n"
        f"- signal_type: {result.signal_type}\n"
        f"- qa_status: {result.qa_status}\n"
        f"- source_path: {source.as_posix()}\n"
        f"- stored_path: {stored_path.relative_to(REPO_ROOT).as_posix()}\n"
        f"- findings ({len(result.findings)}):\n{findings_block}\n"
        f"- next_owner: "
        + ("Adam (via 05_coordinator_qa)" if result.qa_status == "QA_PASS_ESCALATE_TO_ADAM"
           else "05_coordinator_qa" if result.qa_status == "QA_HOLD_NEEDS_INFO"
           else "commerce-agent-team (return)") + "\n"
    )
    with QA_QUEUE_PATH.open("a", encoding="utf-8", newline="\n") as f:
        f.write(block)


# ---------------------- top-level driver ----------------------

def process(handoff_path: Path) -> ImportResult:
    text = handoff_path.read_text(encoding="utf-8")
    handoff = json.loads(text)

    result = ImportResult(
        handoff_id=handoff.get("handoff_id"),
        signal_type=handoff.get("signal_type"),
        direction=handoff.get("direction"),
    )

    validate_envelope(handoff, result)
    if handoff.get("signal_type") == PRIMARY_SIGNAL:
        validate_channel_submission_ready(handoff, result)
    scan_for_live_mode_and_secrets(handoff, result)

    result.qa_status = decide_qa(result)
    return result


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff_path", help="Path to commerce-emitted handoff JSON")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate only; do not write to runtime/commerce_handoffs/")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable result on stdout")
    args = parser.parse_args()

    src = Path(args.handoff_path).resolve()
    if not src.exists():
        print(f"FATAL: handoff path not found: {src}", file=sys.stderr)
        return 2

    try:
        result = process(src)
    except json.JSONDecodeError as exc:
        print(f"FATAL: invalid JSON in {src}: {exc}", file=sys.stderr)
        return 2

    # Read handoff one more time for storage (re-parse keeps us defensive).
    handoff = json.loads(src.read_text(encoding="utf-8"))

    if not args.dry_run and result.qa_status != "QA_REJECT_RETURN_TO_COMMERCE":
        dest = store_handoff(handoff, src)
        result.stored_path = str(dest.relative_to(REPO_ROOT).as_posix())
        append_qa_card(result, dest, src)
    elif not args.dry_run:
        # Even rejects get a queue card so commerce can find the reason.
        append_qa_card(
            result,
            stored_path=RUNTIME_DIR / "(not stored — rejected)",
            source=src,
        )

    if args.json:
        out = {
            "handoff_id": result.handoff_id,
            "signal_type": result.signal_type,
            "direction": result.direction,
            "qa_status": result.qa_status,
            "stored_path": result.stored_path,
            "blocking_count": len(result.blocking),
            "warn_count": len(result.warns),
            "findings": [
                {"severity": f.severity, "code": f.code,
                 "field_path": f.field_path, "message": f.message}
                for f in result.findings
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"=== commerce handoff import ===")
        print(f"  source       : {src}")
        print(f"  handoff_id   : {result.handoff_id}")
        print(f"  signal_type  : {result.signal_type}")
        print(f"  direction    : {result.direction}")
        print(f"  qa_status    : {result.qa_status}")
        if result.stored_path:
            print(f"  stored_path  : {result.stored_path}")
        print(f"  findings     : blocking={len(result.blocking)} warn={len(result.warns)} "
              f"info={len(result.findings) - len(result.blocking) - len(result.warns)}")
        for f in result.findings:
            print(f"    [{f.severity:8}] {f.code} @ {f.field_path}: {f.message}")

    return 1 if result.qa_status == "QA_REJECT_RETURN_TO_COMMERCE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
