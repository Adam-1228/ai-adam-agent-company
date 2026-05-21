from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

DEFAULTS = {
    "LLM_PROVIDER": "mock",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "https://api.openai.com/v1",
    "COMMERCE_AGENT_ENV": "local",
    "COMMERCE_AGENT_TIMEZONE": "Asia/Seoul",
    "DASHBOARD_HOST": "0.0.0.0",
    "DASHBOARD_PORT": "8080",
    "DASHBOARD_USERNAME": "adam",
    "DASHBOARD_PASSWORD": "",
}

ORDER = [
    "LLM_PROVIDER",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "COMMERCE_AGENT_ENV",
    "COMMERCE_AGENT_TIMEZONE",
    "DASHBOARD_HOST",
    "DASHBOARD_PORT",
    "DASHBOARD_USERNAME",
    "DASHBOARD_PASSWORD",
]


def load_env() -> dict[str, str]:
    values = dict(DEFAULTS)
    if not ENV_PATH.exists():
        return values

    for raw_line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            if line.startswith("sk-"):
                values["OPENAI_API_KEY"] = line
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def save_env(values: dict[str, str]) -> None:
    lines = [f"{key}={values.get(key, '')}" for key in ORDER]
    lines.extend(f"{key}={values[key]}" for key in sorted(k for k in values if k not in ORDER))
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV_PATH, 0o600)
    except PermissionError:
        pass


def masked(value: str, keep: int = 4) -> str:
    if not value:
        return "<empty>"
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}"


def show(values: dict[str, str]) -> None:
    for key in ORDER:
        value = values.get(key, "")
        if "KEY" in key or "PASSWORD" in key:
            print(f"{key}={masked(value)} len={len(value)}")
        else:
            print(f"{key}={value}")


def configure_openai(values: dict[str, str]) -> None:
    api_key = getpass.getpass("OpenAI API key: ").strip()
    if not api_key.startswith("sk-"):
        raise SystemExit("OpenAI API key should start with sk-. Nothing was saved.")
    if len(api_key) < 40:
        raise SystemExit("OpenAI API key looks too short. Nothing was saved.")

    values["LLM_PROVIDER"] = "openai"
    values["OPENAI_API_KEY"] = api_key
    values.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1")


def configure_dashboard_password(values: dict[str, str]) -> None:
    username = input(f"Dashboard username [{values.get('DASHBOARD_USERNAME', 'adam')}]: ").strip()
    if username:
        values["DASHBOARD_USERNAME"] = username
    password = getpass.getpass("Dashboard password: ").strip()
    if password:
        values["DASHBOARD_PASSWORD"] = password


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely configure commerce agent .env values.")
    parser.add_argument("--show", action="store_true", help="Show current config with secrets masked.")
    parser.add_argument("--openai", action="store_true", help="Prompt for OpenAI API key and enable OpenAI provider.")
    parser.add_argument("--mock", action="store_true", help="Switch LLM provider back to mock.")
    parser.add_argument("--dashboard-password", action="store_true", help="Prompt for dashboard username/password.")
    args = parser.parse_args()

    values = load_env()

    changed = False
    if args.openai:
        configure_openai(values)
        changed = True
    if args.mock:
        values["LLM_PROVIDER"] = "mock"
        changed = True
    if args.dashboard_password:
        configure_dashboard_password(values)
        changed = True

    if changed:
        save_env(values)
        print(f"Saved: {ENV_PATH}")

    if args.show or changed:
        show(load_env())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
