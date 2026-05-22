from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
RUNTIME = ROOT / "runtime"
GROWTH_LATEST = RUNTIME / "growth_pipeline" / "latest.json"
HANDOFF_DIR = RUNTIME / "commerce_to_client_ops_handoffs"
VALIDATION_DIR = RUNTIME / "commerce_handoffs"
REPORTS = ROOT / "reports"
LATEST_JSON = VALIDATION_DIR / "latest_validation.json"
LATEST_REPORT = REPORTS / "latest_commerce_handoff_validation.md"

CURRENT_CONTRACT_VERSION = "2026-05-22.v2.1"
SUPPORTED_CONTRACT_VERSIONS = {"2026-05-22.v2", CURRENT_CONTRACT_VERSION}
ALLOWED_SIGNAL_TYPES = {"channel_submission_ready"}
SECRET_KEYWORDS = ("api_key", "access_key", "secret", "token", "password", "refresh_token", "client_secret")

REQUIRED_TOP_LEVEL = [
    "contract_version",
    "handoff_id",
    "direction",
    "from_team",
    "to_team",
    "created_at",
    "source_agent",
    "signal_type",
    "summary",
    "confidence",
    "requires_human_approval",
    "dry_run_only",
    "pii_check",
    "review",
    "payload",
]

PII_FIELDS = [
    "names_removed",
    "contacts_removed",
    "business_ids_removed",
    "raw_messages_removed",
    "amounts_indexed",
    "medical_legal_tax_only_as_category",
]

CHANNEL_READY_FIELDS = [
    "run_id",
    "opportunity_id",
    "package_paths",
    "channels",
    "validation_status",
    "approval_status",
    "submit_status",
    "risk_review",
    "forbidden_claims_present",
    "supplier_evidence_present",
    "category_match_seller_scope",
    "qa_route",
    "do_not_disclose",
]


@dataclass
class Finding:
    handoff_id: str
    signal_type: str
    severity: str
    message: str


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def flatten(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(payload, dict):
        rows: list[tuple[str, Any]] = []
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(flatten(value, next_prefix))
        return rows
    if isinstance(payload, list):
        rows = []
        for index, value in enumerate(payload):
            rows.extend(flatten(value, f"{prefix}[{index}]"))
        return rows
    return [(prefix, payload)]


def secret_field_hits(payload: dict) -> list[str]:
    hits = []
    for key, value in flatten(payload):
        key_lower = key.lower()
        if any(word in key_lower for word in SECRET_KEYWORDS) and value not in (None, "", False, []):
            hits.append(key)
    return hits


def add(findings: list[Finding], handoff_id: str, signal_type: str, severity: str, message: str) -> None:
    findings.append(Finding(handoff_id, signal_type, severity, message))


def validate_package_path(handoff_id: str, signal_type: str, path_text: str, findings: list[Finding]) -> None:
    if Path(path_text).is_absolute():
        add(findings, handoff_id, signal_type, "WARN", "package path should be repo-relative, not absolute")

    path = resolve_repo_path(path_text)
    if not path.exists():
        add(findings, handoff_id, signal_type, "BLOCKING", f"package file missing: {path_text}")
        return

    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        add(findings, handoff_id, signal_type, "BLOCKING", f"package JSON invalid: {path_text} ({exc})")
        return

    secret_hits = secret_field_hits(payload)
    if secret_hits:
        add(findings, handoff_id, signal_type, "BLOCKING", f"secret-like package fields present: {secret_hits}")

    mode = str(payload.get("mode", ""))
    if "live" in mode.lower() or "publish_now" in mode.lower():
        add(findings, handoff_id, signal_type, "BLOCKING", f"package mode is not dry-run safe: {mode}")
    if mode not in {"draft_only_requires_adam_approval", "validation_preview_only_requires_adam_approval"}:
        add(findings, handoff_id, signal_type, "WARN", f"unexpected package mode: {mode}")


def validate_channel_submission_ready(path: Path, handoff: dict, findings: list[Finding]) -> None:
    handoff_id = str(handoff.get("handoff_id", path.stem))
    signal_type = str(handoff.get("signal_type", "unknown"))
    payload = handoff.get("payload")
    if not isinstance(payload, dict):
        add(findings, handoff_id, signal_type, "BLOCKING", "payload must be an object")
        return

    for field in CHANNEL_READY_FIELDS:
        if field not in payload:
            add(findings, handoff_id, signal_type, "BLOCKING", f"missing payload field: {field}")

    if payload.get("approval_status") != "adam_approval_required":
        add(findings, handoff_id, signal_type, "BLOCKING", "approval_status must stay adam_approval_required")
    if payload.get("submit_status") != "not_submitted":
        add(findings, handoff_id, signal_type, "BLOCKING", "submit_status must stay not_submitted")
    if payload.get("validation_status") != "draft_validated_locally":
        add(findings, handoff_id, signal_type, "WARN", f"unexpected validation_status: {payload.get('validation_status')}")
    if payload.get("forbidden_claims_present") is not False:
        add(findings, handoff_id, signal_type, "BLOCKING", "forbidden_claims_present must be false")

    risk_review = payload.get("risk_review", {})
    if not isinstance(risk_review, dict):
        add(findings, handoff_id, signal_type, "BLOCKING", "risk_review must be an object")
    elif risk_review.get("blocked") is not False:
        add(findings, handoff_id, signal_type, "BLOCKING", "blocked risk reviews must not be escalated as channel_submission_ready")

    package_paths = payload.get("package_paths")
    if not isinstance(package_paths, list) or not package_paths:
        add(findings, handoff_id, signal_type, "BLOCKING", "package_paths must be a non-empty list")
    else:
        for path_text in package_paths:
            if not isinstance(path_text, str) or not path_text.strip():
                add(findings, handoff_id, signal_type, "BLOCKING", "package_paths must contain strings")
                continue
            validate_package_path(handoff_id, signal_type, path_text, findings)

    for field in ("channels", "qa_route", "do_not_disclose"):
        value = payload.get(field)
        if not isinstance(value, list) or not value:
            add(findings, handoff_id, signal_type, "BLOCKING", f"{field} must be a non-empty list")

    if payload.get("supplier_evidence_present") is not True:
        add(findings, handoff_id, signal_type, "WARN", "supplier evidence is not yet present")
    if payload.get("category_match_seller_scope") is not True:
        add(findings, handoff_id, signal_type, "WARN", "seller category scope is not yet confirmed")


def validate_handoff(path: Path) -> list[Finding]:
    handoff_id = path.stem
    signal_type = "unknown"
    findings: list[Finding] = []
    try:
        handoff = read_json(path)
    except json.JSONDecodeError as exc:
        return [Finding(handoff_id, signal_type, "BLOCKING", f"handoff JSON invalid: {exc}")]

    if not isinstance(handoff, dict):
        return [Finding(handoff_id, signal_type, "BLOCKING", "handoff root must be an object")]

    handoff_id = str(handoff.get("handoff_id", handoff_id))
    signal_type = str(handoff.get("signal_type", signal_type))

    for field in REQUIRED_TOP_LEVEL:
        if field not in handoff:
            add(findings, handoff_id, signal_type, "BLOCKING", f"missing top-level field: {field}")

    if handoff.get("contract_version") not in SUPPORTED_CONTRACT_VERSIONS:
        add(findings, handoff_id, signal_type, "BLOCKING", f"contract_version must be one of {sorted(SUPPORTED_CONTRACT_VERSIONS)}")
    if handoff.get("direction") != "commerce_to_client_ops":
        add(findings, handoff_id, signal_type, "BLOCKING", "direction must be commerce_to_client_ops")
    if handoff.get("from_team") != "commerce-agent-team" or handoff.get("to_team") != "client-ops-team":
        add(findings, handoff_id, signal_type, "BLOCKING", "from_team/to_team mismatch")
    if signal_type not in ALLOWED_SIGNAL_TYPES:
        add(findings, handoff_id, signal_type, "BLOCKING", f"unsupported signal_type: {signal_type}")
    if handoff.get("requires_human_approval") is not True:
        add(findings, handoff_id, signal_type, "BLOCKING", "requires_human_approval must be true")
    if handoff.get("dry_run_only") is not True:
        add(findings, handoff_id, signal_type, "BLOCKING", "dry_run_only must be true")

    pii_check = handoff.get("pii_check")
    if not isinstance(pii_check, dict):
        add(findings, handoff_id, signal_type, "BLOCKING", "pii_check must be an object")
    else:
        for field in PII_FIELDS:
            if pii_check.get(field) is not True:
                add(findings, handoff_id, signal_type, "BLOCKING", f"pii_check.{field} must be true")

    review = handoff.get("review")
    if not isinstance(review, dict) or review.get("decision") != "PASS":
        add(findings, handoff_id, signal_type, "BLOCKING", "review.decision must be PASS")

    secret_hits = secret_field_hits(handoff)
    if secret_hits:
        add(findings, handoff_id, signal_type, "BLOCKING", f"secret-like handoff fields present: {secret_hits}")

    if signal_type == "channel_submission_ready":
        validate_channel_submission_ready(path, handoff, findings)

    if not any(finding.severity == "BLOCKING" for finding in findings):
        add(findings, handoff_id, signal_type, "INFO", "handoff validation passed")
    return findings


def handoff_paths() -> list[Path]:
    if GROWTH_LATEST.exists():
        try:
            latest = read_json(GROWTH_LATEST)
        except json.JSONDecodeError:
            latest = {}
        paths = []
        for item in latest.get("commerce_to_client_ops_handoffs", []):
            path_text = str(item.get("path", ""))
            if path_text:
                paths.append(resolve_repo_path(path_text))
        if paths:
            return paths
    if not HANDOFF_DIR.exists():
        return []
    return sorted(HANDOFF_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]


def evaluate() -> dict:
    paths = handoff_paths()
    findings: list[Finding] = []
    if not paths:
        findings.append(Finding("none", "none", "WARN", "no commerce_to_client_ops handoffs found"))
    for path in paths:
        if not path.exists():
            findings.append(Finding(path.stem, "unknown", "BLOCKING", f"handoff file missing: {path}"))
            continue
        findings.extend(validate_handoff(path))

    blocking = sum(1 for finding in findings if finding.severity == "BLOCKING")
    warn = sum(1 for finding in findings if finding.severity == "WARN")
    info = sum(1 for finding in findings if finding.severity == "INFO")
    return {
        "created_at": now(),
        "status": "valid" if blocking == 0 else "invalid",
        "handoff_count": len(paths),
        "blocking": blocking,
        "warn": warn,
        "info": info,
        "findings": [finding.__dict__ for finding in findings],
    }


def render_report(summary: dict) -> str:
    lines = [
        "# Commerce to Client Ops Handoff Validation",
        "",
        f"- Created: {summary['created_at']}",
        f"- Status: {summary['status']}",
        f"- Handoff count: {summary.get('handoff_count', 0)}",
        f"- BLOCKING: {summary['blocking']}",
        f"- WARN: {summary['warn']}",
        f"- INFO: {summary['info']}",
        "",
        "| Handoff | Signal | Severity | Message |",
        "| --- | --- | --- | --- |",
    ]
    for finding in summary["findings"]:
        lines.append(
            "| {handoff_id} | {signal_type} | {severity} | {message} |".format(
                handoff_id=finding["handoff_id"],
                signal_type=finding["signal_type"],
                severity=finding["severity"],
                message=str(finding["message"]).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- `channel_submission_ready` is QA-only and must remain `dry_run_only=true`.",
            "- Channel packages must remain `submit_status=not_submitted` before Adam approval.",
            "- This validator reports field names and counts only; it must not print secret values.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate commerce_to_client_ops handoff packets.")
    parser.add_argument("--json", action="store_true", help="Print full JSON summary.")
    args = parser.parse_args()

    summary = evaluate()
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    LATEST_REPORT.write_text(render_report(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Commerce handoff validation: {summary['status']}")
        print(f"Handoffs: {summary['handoff_count']}")
        print(f"BLOCKING: {summary['blocking']} | WARN: {summary['warn']} | INFO: {summary['info']}")
        print(f"Report: {LATEST_REPORT}")
    return 1 if summary["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
