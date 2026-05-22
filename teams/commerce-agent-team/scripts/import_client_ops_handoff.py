from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "runtime" / "client_ops_handoffs"
TASKS_PATH = RUNTIME_DIR / "commerce_tasks.md"
CURRENT_CONTRACT_VERSION = "2026-05-22.v2.1"
SUPPORTED_CONTRACT_VERSIONS = {"2026-05-21.v1", "2026-05-22.v2", CURRENT_CONTRACT_VERSION}

CLIENT_TO_COMMERCE_TYPES = {
    "operational_performance": "02_margin_analyst",
    "catalog_usage": "04_listing_builder",
    "demand_signal": "01_market_scout",
    "complaint_patterns": "03_risk_guardian",
    "channel_trends": "01_market_scout",
    "seller_account_blocker": "05_ops_manager",
    "refund_or_claim_escalation": "03_risk_guardian",
}

AGGREGATION_SIGNALS = {
    "operational_performance",
    "catalog_usage",
    "demand_signal",
    "complaint_patterns",
    "channel_trends",
}

V2_OPERATIONAL_SIGNALS = {
    "seller_account_blocker",
    "refund_or_claim_escalation",
}

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


class ValidationError(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValidationError("handoff root must be a JSON object")
    return payload


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def require_fields(payload: dict[str, Any], fields: list[str], signal_type: str) -> None:
    for field in fields:
        require(field in payload, f"{signal_type} requires payload.{field}")


def require_string_list(payload: dict[str, Any], field: str, signal_type: str) -> None:
    value = payload.get(field)
    require(isinstance(value, list) and value, f"{signal_type} requires payload.{field} as a non-empty list")
    require(all(isinstance(item, str) and item.strip() for item in value), f"{signal_type} payload.{field} must contain strings")


def require_severity(payload: dict[str, Any], signal_type: str) -> None:
    severity = payload.get("severity")
    require(severity in {"low", "medium", "high", "critical"}, f"{signal_type} payload.severity must be low, medium, high, or critical")


def validate_handoff(handoff: dict[str, Any]) -> str:
    for field in REQUIRED_TOP_LEVEL:
        require(field in handoff, f"missing top-level field: {field}")

    require(
        handoff["contract_version"] in SUPPORTED_CONTRACT_VERSIONS,
        f"contract_version must be one of {sorted(SUPPORTED_CONTRACT_VERSIONS)}",
    )
    require(handoff["direction"] == "client_ops_to_commerce", "direction must be client_ops_to_commerce")
    require(handoff["from_team"] == "client-ops-team", "from_team must be client-ops-team")
    require(handoff["to_team"] == "commerce-agent-team", "to_team must be commerce-agent-team")
    require(isinstance(handoff["requires_human_approval"], bool), "requires_human_approval must be a boolean")
    require(isinstance(handoff["dry_run_only"], bool), "dry_run_only must be a boolean")
    require(handoff["requires_human_approval"] is True, "requires_human_approval must be true")
    require(handoff["dry_run_only"] is True, "dry_run_only must be true")

    signal_type = handoff["signal_type"]
    require(signal_type in CLIENT_TO_COMMERCE_TYPES, f"unsupported signal_type: {signal_type}")
    if signal_type in V2_OPERATIONAL_SIGNALS:
        require(
            handoff["contract_version"] in {"2026-05-22.v2", CURRENT_CONTRACT_VERSION},
            f"{signal_type} requires contract_version 2026-05-22.v2 or {CURRENT_CONTRACT_VERSION}",
        )

    review = handoff["review"]
    require(isinstance(review, dict), "review must be an object")
    require(review.get("decision") == "PASS", "review.decision must be PASS")

    pii_check = handoff["pii_check"]
    require(isinstance(pii_check, dict), "pii_check must be an object")
    for field in PII_FIELDS:
        require(pii_check.get(field) is True, f"pii_check.{field} must be true")

    payload = handoff["payload"]
    require(isinstance(payload, dict), "payload must be an object")
    if signal_type in AGGREGATION_SIGNALS:
        sample_size = payload.get("sample_size_cases")
        require(type(sample_size) is int, "payload.sample_size_cases must be an integer")
        require(sample_size >= 5, "payload.sample_size_cases must be at least 5")

    if signal_type == "operational_performance":
        require_fields(
            payload,
            ["industry", "region", "time_window", "metrics", "derived_commerce_request"],
            signal_type,
        )
        require(isinstance(payload["derived_commerce_request"], dict), "payload.derived_commerce_request must be an object")
    elif signal_type == "catalog_usage":
        require_fields(
            payload,
            [
                "catalog_or_category",
                "target_market",
                "time_window",
                "usage_indexed",
                "dropoff_or_reject_reasons",
                "requested_commerce_action",
            ],
            signal_type,
        )
    elif signal_type == "demand_signal":
        require_fields(
            payload,
            [
                "industry",
                "region",
                "time_window",
                "keyword_or_intent",
                "category_hint",
                "target_market",
                "demand_index",
                "evidence_summary",
            ],
            signal_type,
        )
    elif signal_type == "complaint_patterns":
        require_fields(
            payload,
            [
                "industry",
                "region",
                "time_window",
                "complaint_category",
                "severity",
                "affected_stage",
                "commerce_action",
                "recommended_guardrails",
            ],
            signal_type,
        )
    elif signal_type == "channel_trends":
        require_fields(
            payload,
            [
                "channel",
                "audience_segment",
                "time_window",
                "trend_type",
                "trend_index",
                "content_or_offer_hint",
                "commerce_action",
            ],
            signal_type,
        )
    elif signal_type == "seller_account_blocker":
        require_fields(
            payload,
            [
                "channel",
                "blocker_type",
                "severity",
                "discovered_at",
                "affected_opportunity_ids",
                "remediation_owner",
                "do_not_disclose",
            ],
            signal_type,
        )
        require_severity(payload, signal_type)
        require_string_list(payload, "affected_opportunity_ids", signal_type)
        require_string_list(payload, "do_not_disclose", signal_type)
    elif signal_type == "refund_or_claim_escalation":
        require_fields(
            payload,
            [
                "opportunity_id",
                "channel",
                "trigger_type",
                "severity",
                "claim_breakdown",
                "case_ids_anonymized",
                "raw_customer_messages_included",
                "recommended_commerce_action",
                "qa_decision",
                "qa_owner",
            ],
            signal_type,
        )
        require_severity(payload, signal_type)
        require(isinstance(payload["claim_breakdown"], dict), "payload.claim_breakdown must be an object")
        require_string_list(payload, "case_ids_anonymized", signal_type)
        require(payload["raw_customer_messages_included"] is False, "raw customer messages must not be included")

    return CLIENT_TO_COMMERCE_TYPES[signal_type]


def task_markdown(handoff: dict[str, Any], route: str) -> str:
    payload = handoff["payload"]
    lines = [
        f"## {handoff['handoff_id']}",
        "",
        f"- Created at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Source: {handoff['source_agent']}",
        f"- Signal type: {handoff['signal_type']}",
        f"- Route: {route}",
        f"- Confidence: {handoff['confidence']}",
        f"- Human approval required: {handoff['requires_human_approval']}",
        f"- Dry run only: {handoff['dry_run_only']}",
        f"- Summary: {handoff['summary']}",
        "",
        "### Payload Summary",
        "",
    ]
    for key in sorted(payload):
        value = payload[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        lines.append(f"- {key}: {rendered}")
    lines.extend(["", "### Next Action", "", f"- Assign to `{route}` for review and task conversion.", ""])
    return "\n".join(lines)


def save_handoff(source: Path, handoff: dict[str, Any], route: str, dry_run: bool) -> Path:
    target = RUNTIME_DIR / f"{handoff['handoff_id']}.json"
    if dry_run:
        print(f"would save: {target}")
        print(f"would route: {route}")
        return target

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    with TASKS_PATH.open("a", encoding="utf-8") as f:
        f.write(task_markdown(handoff, route))
        f.write("\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and receive client-ops handoffs for commerce.")
    parser.add_argument("handoff_json", help="Path to a client_ops_to_commerce handoff JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write runtime files")
    args = parser.parse_args()

    source = Path(args.handoff_json)
    handoff = load_json(source)
    route = validate_handoff(handoff)
    target = save_handoff(source, handoff, route, args.dry_run)
    print("status=accepted")
    print(f"handoff_id={handoff['handoff_id']}")
    print(f"signal_type={handoff['signal_type']}")
    print(f"route={route}")
    print(f"target={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
