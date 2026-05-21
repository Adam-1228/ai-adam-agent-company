from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
ENV_PATH = ROOT / ".env"
SERVICES = [
    "commerce-dashboard.service",
    "commerce-agents.timer",
    "commerce-cleanup.timer",
]
SECRET_PATTERNS = [
    "sk-" + "proj",
    "-----" + "BEGIN",
]


def run(command: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return 127, "command not found"
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def load_env_keys() -> set[str]:
    keys = set()
    if not ENV_PATH.exists():
        return keys
    for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _value = stripped.split("=", 1)
        keys.add(key.strip())
    return keys


def status_line(name: str, ok: bool, detail: str) -> str:
    marker = "OK" if ok else "CHECK"
    return f"[{marker}] {name}: {detail}"


def check_env() -> list[str]:
    lines = []
    keys = load_env_keys()
    lines.append(status_line(".env present", ENV_PATH.exists(), "found" if ENV_PATH.exists() else "missing"))
    if ENV_PATH.exists():
        mode = ENV_PATH.stat().st_mode & 0o777
        lines.append(status_line(".env permissions", mode <= 0o600, oct(mode)))
    lines.append(status_line("dashboard auth", {"DASHBOARD_USERNAME", "DASHBOARD_PASSWORD"} <= keys, "configured" if {"DASHBOARD_USERNAME", "DASHBOARD_PASSWORD"} <= keys else "missing"))
    provider = "openai" if "OPENAI_API_KEY" in keys else "mock-or-unset"
    lines.append(status_line("LLM key", provider == "openai", provider))
    return lines


def check_git_hygiene() -> list[str]:
    lines = []
    code, tracked = run(["git", "ls-files"], cwd=REPO_ROOT)
    if code != 0:
        return [status_line("git tracked files", False, tracked or "unable to inspect")]

    tracked_paths = [Path(line) for line in tracked.splitlines() if line.strip()]
    risky_files = [
        str(path)
        for path in tracked_paths
        if path.name in {".env", "id_rsa", "id_rsa.pub"} or path.suffix in {".pem", ".key", ".p12", ".pfx"}
    ]
    lines.append(status_line("secret files tracked", not risky_files, ", ".join(risky_files) if risky_files else "none"))

    findings = []
    for path in tracked_paths:
        full_path = REPO_ROOT / path
        if not full_path.is_file() or full_path.stat().st_size > 500_000:
            continue
        text = full_path.read_text(encoding="utf-8", errors="replace")
        if any(pattern in text for pattern in SECRET_PATTERNS):
            findings.append(str(path))
    lines.append(status_line("secret-like tracked text", not findings, ", ".join(findings) if findings else "none"))
    return lines


def check_systemd() -> list[str]:
    lines = []
    for service in SERVICES:
        code, output = run(["systemctl", "is-active", service])
        lines.append(status_line(service, code == 0 and output == "active", output or "not active"))
    return lines


def check_disk() -> list[str]:
    total, used, free = shutil.disk_usage(ROOT)
    used_pct = round((used / total) * 100, 1) if total else 0
    ok = used_pct < 85
    detail = f"{used_pct}% used, {free / (1024 ** 3):.1f} GB free"
    return [status_line("disk", ok, detail)]


def check_ufw() -> list[str]:
    if os.name == "nt":
        return [status_line("ufw", False, "not available on Windows")]
    code, output = run(["sudo", "ufw", "status"])
    if code != 0:
        return [status_line("ufw", False, output or "unable to inspect")]
    has_restricted_8080 = "8080" in output and "59.13.218.189" in output
    has_public_8050 = "8050" in output and "0.0.0.0/0" in output
    return [
        status_line("ufw 8080", has_restricted_8080, "restricted to ADAM IP" if has_restricted_8080 else "review rule"),
        status_line("ufw 8050", not has_public_8050, "not publicly allowed" if not has_public_8050 else "public rule found"),
    ]


def main() -> int:
    sections = [
        ("Environment", check_env()),
        ("Git Hygiene", check_git_hygiene()),
        ("Systemd", check_systemd()),
        ("Disk", check_disk()),
        ("UFW", check_ufw()),
    ]

    has_check = False
    for title, lines in sections:
        print(f"\n## {title}")
        for line in lines:
            print(line)
            if line.startswith("[CHECK]"):
                has_check = True

    return 1 if has_check else 0


if __name__ == "__main__":
    raise SystemExit(main())
