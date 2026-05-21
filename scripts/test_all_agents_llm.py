from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMMERCE = ROOT / "teams" / "commerce-agent-team"
CLIENT_OPS = ROOT / "teams" / "client-ops-team"

COMMERCE_AGENTS = [
    "01_market_scout",
    "02_margin_analyst",
    "03_risk_guardian",
    "04_listing_builder",
    "05_ops_manager",
]
CLIENT_OPS_AGENTS = [
    "01_onboarding_manager",
    "02_ops_operator",
    "03_cs_manager",
    "04_data_analyst",
    "05_coordinator_qa",
]


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_commerce(use_real: bool) -> list[dict[str, Any]]:
    module = load_module("commerce_llm_client_for_smoke", COMMERCE / "scripts" / "llm_client.py")
    rows = []
    for agent_id in COMMERCE_AGENTS:
        result = module.complete(
            agent_id,
            "You are running a short smoke test. Reply with one short Korean sentence.",
            "LLM 연결 점검입니다. 한 문장으로 답하세요.",
            use_llm=use_real,
        )
        rows.append(
            {
                "team": "commerce-agent-team",
                "agent_id": agent_id,
                "provider": result.provider,
                "model": result.model,
                "used": result.used,
                "ok": result.error is None if use_real else True,
                "error": result.error,
            }
        )
    return rows


def run_client_ops(use_real: bool) -> list[dict[str, Any]]:
    module = load_module("client_ops_llm_client_for_smoke", CLIENT_OPS / "scripts" / "llm_client.py")
    rows = []
    for agent_id in CLIENT_OPS_AGENTS:
        result = module.complete(
            agent_id,
            "LLM 연결 점검입니다. 반드시 한 문장으로 답하세요.",
            "짧은 한국어 한 문장으로 smoke test 응답을 작성하세요.",
            use_llm=use_real,
        )
        rows.append(
            {
                "team": "client-ops-team",
                "agent_id": agent_id,
                "provider": result.get("provider"),
                "model": result.get("model"),
                "used": result.get("used"),
                "ok": not result.get("error") if use_real else True,
                "error": result.get("error"),
                "fallback_used": result.get("fallback_used"),
            }
        )
    return rows


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Smoke-test LLM reachability for all 10 company agents.")
    parser.add_argument("--real", action="store_true", help="Make real provider calls when API keys are available.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    args = parser.parse_args()

    rows = run_commerce(args.real) + run_client_ops(args.real)
    failed = [row for row in rows if not row["ok"]]

    if args.json:
        print(json.dumps({"real": args.real, "failed": len(failed), "rows": rows}, ensure_ascii=False, indent=2))
    else:
        mode = "real provider calls" if args.real else "dry smoke"
        print(f"LLM smoke mode: {mode}")
        for row in rows:
            status = "OK" if row["ok"] else "CHECK"
            print(
                f"[{status}] {row['team']} / {row['agent_id']} "
                f"provider={row['provider']} model={row['model']} used={row['used']}"
            )
            if row.get("error"):
                print(f"      error={row['error']}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
