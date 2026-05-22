from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
EXAMPLE_CONFIG = CONFIG_DIR / "channel_accounts.example.json"
LOCAL_CONFIG = CONFIG_DIR / "channel_accounts.local.json"
RUNTIME_DIR = ROOT / "runtime" / "channel_readiness"
REPORTS_DIR = ROOT / "reports"
LATEST_JSON = RUNTIME_DIR / "latest.json"
LATEST_REPORT = REPORTS_DIR / "latest_channel_readiness.md"

SECRET_KEYWORDS = ("secret", "token", "password", "access_key", "refresh", "client_secret")

GLOBAL_REQUIRED = [
    "business_registration_ready",
    "settlement_bank_ready",
    "return_address_ready",
    "cs_contact_ready",
    "privacy_policy_ready",
    "shipping_policy_ready",
    "adam_final_approval_required",
]

CHANNEL_REQUIRED = {
    "coupang": [
        "seller_account_created",
        "wing_login_verified",
        "business_profile_verified",
        "settlement_profile_ready",
        "return_address_ready",
        "shipping_policy_ready",
        "cs_contact_ready",
        "api_access_requested",
        "api_keys_stored_in_env",
        "draft_submission_only",
    ],
    "amazon": [
        "seller_account_created",
        "seller_central_login_verified",
        "business_profile_verified",
        "settlement_profile_ready",
        "return_address_ready",
        "shipping_policy_ready",
        "cs_contact_ready",
        "sp_api_developer_profile_ready",
        "sp_api_app_authorized",
        "api_keys_stored_in_env",
        "validation_preview_only",
    ],
}

ENV_REQUIRED = {
    "coupang": ["COUPANG_ACCESS_KEY", "COUPANG_SECRET_KEY", "COUPANG_VENDOR_ID"],
    "amazon": [
        "AMAZON_SP_CLIENT_ID",
        "AMAZON_SP_CLIENT_SECRET",
        "AMAZON_SP_REFRESH_TOKEN",
        "AMAZON_SP_AWS_ACCESS_KEY_ID",
        "AMAZON_SP_AWS_SECRET_ACCESS_KEY",
        "AMAZON_SP_ROLE_ARN",
        "AMAZON_SELLER_ID",
        "AMAZON_MARKETPLACE_ID",
    ],
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> tuple[dict, str]:
    if LOCAL_CONFIG.exists():
        return read_json(LOCAL_CONFIG), "local"
    return read_json(EXAMPLE_CONFIG), "example"


def flatten_keys(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(payload, dict):
        rows: list[tuple[str, Any]] = []
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(flatten_keys(value, next_prefix))
        return rows
    if isinstance(payload, list):
        rows = []
        for index, value in enumerate(payload):
            rows.extend(flatten_keys(value, f"{prefix}[{index}]"))
        return rows
    return [(prefix, payload)]


def secret_shape_checks(payload: dict) -> list[Check]:
    checks = []
    for key, value in flatten_keys(payload):
        key_lower = key.lower()
        if any(word in key_lower for word in SECRET_KEYWORDS) and isinstance(value, str) and value.strip():
            checks.append(Check(key, False, "secret-like value must not be stored in channel account JSON"))
    if not checks:
        checks.append(Check("secret_scan", True, "no secret-like values found in JSON"))
    return checks


def boolean_checks(scope: str, payload: dict, required: list[str]) -> list[Check]:
    checks = []
    for key in required:
        value = payload.get(key)
        if isinstance(value, bool):
            checks.append(Check(f"{scope}.{key}", value is True, "true" if value is True else "not ready"))
        else:
            checks.append(Check(f"{scope}.{key}", False, "missing or not boolean"))
    return checks


def env_checks(channel: str) -> list[Check]:
    checks = []
    for name in ENV_REQUIRED[channel]:
        checks.append(Check(f"env.{name}", bool(os.getenv(name, "").strip()), "present" if os.getenv(name, "").strip() else "missing"))
    return checks


def evaluate() -> dict:
    config, source = load_config()
    checks: list[Check] = []
    checks.extend(secret_shape_checks(config))
    checks.extend(boolean_checks("global", config.get("global", {}), GLOBAL_REQUIRED))

    channel_results = {}
    for channel, required in CHANNEL_REQUIRED.items():
        channel_payload = config.get("channels", {}).get(channel, {})
        channel_checks = boolean_checks(channel, channel_payload, required)
        channel_checks.extend(env_checks(channel))
        channel_ready = all(check.ok for check in channel_checks)
        channel_results[channel] = {
            "ready": channel_ready,
            "checks": [check.__dict__ for check in channel_checks],
        }
        checks.extend(channel_checks)

    blocking = [check for check in checks if not check.ok]
    status = "ready" if not blocking and source == "local" else "not_ready"
    if any(check.detail.startswith("secret-like") for check in blocking):
        status = "unsafe_config"

    return {
        "created_at": now(),
        "status": status,
        "config_source": source,
        "config_path": str(LOCAL_CONFIG if source == "local" else EXAMPLE_CONFIG),
        "blocking_count": len(blocking),
        "channels": channel_results,
        "checks": [check.__dict__ for check in checks],
    }


def render_report(summary: dict) -> str:
    lines = [
        "# Channel Readiness Report",
        "",
        f"- Created: {summary['created_at']}",
        f"- Status: {summary['status']}",
        f"- Config source: {summary['config_source']}",
        f"- Config path: {summary['config_path']}",
        f"- Blocking count: {summary['blocking_count']}",
        "",
        "## Channel Summary",
        "",
    ]
    for channel, result in summary["channels"].items():
        lines.append(f"- {channel}: {'READY' if result['ready'] else 'NOT READY'}")
    lines.extend(["", "## Checks", "", "| Check | OK | Detail |", "| --- | --- | --- |"])
    for check in summary["checks"]:
        lines.append(f"| {check['name']} | {check['ok']} | {check['detail']} |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This report intentionally does not print API keys or sensitive account values.",
            "- Missing account/API items are expected before seller signup is complete.",
            "- Live publishing remains blocked until Adam approves and channel credentials are configured safely.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check seller channel readiness without revealing secrets.")
    parser.add_argument("--strict", action="store_true", help="Return exit 1 unless every readiness item is complete.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    args = parser.parse_args()

    summary = evaluate()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    LATEST_REPORT.write_text(render_report(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Channel readiness: {summary['status']}")
        print(f"Blocking count: {summary['blocking_count']}")
        print(f"Report: {LATEST_REPORT}")

    return 1 if args.strict and summary["status"] != "ready" else 0


if __name__ == "__main__":
    raise SystemExit(main())
