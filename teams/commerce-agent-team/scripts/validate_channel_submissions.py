from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
GROWTH_LATEST = RUNTIME / "growth_pipeline" / "latest.json"
CHANNEL_PENDING = RUNTIME / "channel_submissions" / "pending"
VALIDATION_DIR = RUNTIME / "channel_submissions"
REPORTS = ROOT / "reports"
LATEST_JSON = VALIDATION_DIR / "latest_validation.json"
LATEST_REPORT = REPORTS / "latest_channel_validation.md"

SECRET_KEYWORDS = ("api_key", "access_key", "secret", "token", "password", "refresh_token", "client_secret")


@dataclass
class Finding:
    channel: str
    opportunity_id: str
    severity: str
    message: str


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_payload_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.exists():
        return path
    fallback = CHANNEL_PENDING / path.name
    return fallback


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


def has_secret_shape(payload: dict) -> list[str]:
    hits = []
    for key, value in flatten(payload):
        key_lower = key.lower()
        if any(word in key_lower for word in SECRET_KEYWORDS) and value not in (None, "", False):
            hits.append(key)
    return hits


def require(payload: dict, keys: list[str]) -> list[str]:
    return [key for key in keys if key not in payload or payload.get(key) in ("", None, [])]


def validate_submission(opportunity_id: str, submission: dict) -> list[Finding]:
    channel = str(submission.get("channel", "unknown"))
    findings: list[Finding] = []
    payload_path = resolve_payload_path(str(submission.get("payload_path", "")))
    if not payload_path.exists():
        return [Finding(channel, opportunity_id, "BLOCKING", f"payload file missing: {payload_path}")]

    try:
        payload = read_json(payload_path)
    except json.JSONDecodeError as exc:
        return [Finding(channel, opportunity_id, "BLOCKING", f"payload JSON invalid: {exc}")]

    secret_hits = has_secret_shape(payload)
    if secret_hits:
        findings.append(Finding(channel, opportunity_id, "BLOCKING", f"secret-like fields present in payload: {secret_hits}"))

    approval_status = str(submission.get("approval_status", ""))
    submit_status = str(submission.get("submit_status", ""))
    validation_status = str(submission.get("validation_status", ""))

    if submit_status != "not_submitted":
        findings.append(Finding(channel, opportunity_id, "BLOCKING", "submit_status must stay not_submitted before API connection"))
    if approval_status not in {"adam_approval_required", "blocked"}:
        findings.append(Finding(channel, opportunity_id, "BLOCKING", f"unexpected approval_status: {approval_status}"))
    if validation_status not in {"draft_validated_locally", "blocked_by_risk"}:
        findings.append(Finding(channel, opportunity_id, "WARN", f"unexpected validation_status: {validation_status}"))

    mode = str(payload.get("mode", ""))
    if channel == "coupang":
        missing = require(payload, ["mode", "sellerProductName", "displayProductName", "salePrice", "externalVendorSku", "categoryHint", "content"])
        if missing:
            findings.append(Finding(channel, opportunity_id, "BLOCKING", f"missing Coupang draft fields: {missing}"))
        if mode != "draft_only_requires_adam_approval":
            findings.append(Finding(channel, opportunity_id, "BLOCKING", f"Coupang mode must be draft_only_requires_adam_approval, got {mode}"))
        if int(payload.get("salePrice") or 0) <= 0:
            findings.append(Finding(channel, opportunity_id, "BLOCKING", "Coupang salePrice must be positive"))
        content = payload.get("content", {})
        if not isinstance(content, dict) or "risk_review" not in content or "supplier_evidence" not in content:
            findings.append(Finding(channel, opportunity_id, "BLOCKING", "Coupang content must include risk_review and supplier_evidence"))
    elif channel == "amazon":
        missing = require(payload, ["mode", "sku", "productType", "requirements", "attributes"])
        if missing:
            findings.append(Finding(channel, opportunity_id, "BLOCKING", f"missing Amazon preview fields: {missing}"))
        if mode != "validation_preview_only_requires_adam_approval":
            findings.append(Finding(channel, opportunity_id, "BLOCKING", f"Amazon mode must be validation_preview_only_requires_adam_approval, got {mode}"))
        attributes = payload.get("attributes", {})
        if not isinstance(attributes, dict) or "risk_review" not in attributes or "supplier_evidence" not in attributes:
            findings.append(Finding(channel, opportunity_id, "BLOCKING", "Amazon attributes must include risk_review and supplier_evidence"))
    else:
        findings.append(Finding(channel, opportunity_id, "BLOCKING", f"unsupported channel: {channel}"))

    if "live" in mode.lower() or "publish_now" in mode.lower():
        findings.append(Finding(channel, opportunity_id, "BLOCKING", f"live/publish mode is not allowed in dry-run adapter: {mode}"))

    if not findings:
        findings.append(Finding(channel, opportunity_id, "INFO", "dry-run validation passed"))
    return findings


def evaluate() -> dict:
    if not GROWTH_LATEST.exists():
        return {
            "created_at": now(),
            "status": "not_ready",
            "blocking": 1,
            "warn": 0,
            "info": 0,
            "findings": [Finding("all", "none", "BLOCKING", "growth pipeline latest.json is missing").__dict__],
        }

    summary = read_json(GROWTH_LATEST)
    findings: list[Finding] = []
    for item in summary.get("opportunities", []):
        opportunity_id = str(item.get("opportunity_id", "unknown"))
        for submission in item.get("submissions", []):
            findings.extend(validate_submission(opportunity_id, submission))

    blocking = sum(1 for finding in findings if finding.severity == "BLOCKING")
    warn = sum(1 for finding in findings if finding.severity == "WARN")
    info = sum(1 for finding in findings if finding.severity == "INFO")
    return {
        "created_at": now(),
        "status": "valid" if blocking == 0 else "invalid",
        "growth_run_id": summary.get("run_id"),
        "submission_count": sum(len(item.get("submissions", [])) for item in summary.get("opportunities", [])),
        "blocking": blocking,
        "warn": warn,
        "info": info,
        "findings": [finding.__dict__ for finding in findings],
    }


def render_report(summary: dict) -> str:
    lines = [
        "# Channel Submission Dry-Run Validation",
        "",
        f"- Created: {summary['created_at']}",
        f"- Status: {summary['status']}",
        f"- Growth run: {summary.get('growth_run_id', 'none')}",
        f"- Submission count: {summary.get('submission_count', 0)}",
        f"- BLOCKING: {summary['blocking']}",
        f"- WARN: {summary['warn']}",
        f"- INFO: {summary['info']}",
        "",
        "| Channel | Opportunity | Severity | Message |",
        "| --- | --- | --- | --- |",
    ]
    for finding in summary["findings"]:
        message = str(finding["message"]).replace("|", "/")
        lines.append(f"| {finding['channel']} | {finding['opportunity_id']} | {finding['severity']} | {message} |")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- This validator does not call Coupang, Amazon, or any external API.",
            "- All generated packages must remain not_submitted until Adam approves and real channel credentials are configured.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated channel packages without external API calls.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    args = parser.parse_args()

    summary = evaluate()
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    LATEST_REPORT.write_text(render_report(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Channel dry-run validation: {summary['status']}")
        print(f"Submissions: {summary.get('submission_count', 0)}")
        print(f"BLOCKING: {summary['blocking']} | WARN: {summary['warn']} | INFO: {summary['info']}")
        print(f"Report: {LATEST_REPORT}")

    return 1 if summary["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
