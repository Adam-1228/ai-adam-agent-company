from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
MODEL_CONFIG_PATH = ROOT / "config" / "agent_models.json"
RUNTIME_DIR = ROOT / "runtime"
LLM_USAGE_LOG = RUNTIME_DIR / "llm_usage.jsonl"

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_TOKENS = 1024


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_model_config() -> dict:
    if not MODEL_CONFIG_PATH.exists():
        return {
            "default_provider": "mock",
            "default_model": "claude-sonnet-4-6",
            "defaults": {"timeout_seconds": DEFAULT_TIMEOUT, "max_retries": DEFAULT_MAX_RETRIES},
            "agents": {},
        }
    return json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))


def agent_model(agent_id: str) -> dict:
    config = load_model_config()
    agent = config.get("agents", {}).get(agent_id, {})
    defaults = config.get("defaults", {})
    env_override = (os.environ.get("LLM_PROVIDER") or "").strip().lower() or None

    provider = env_override or agent.get("provider") or config.get("default_provider", "mock")
    model = agent.get("model") or config.get("default_model", "claude-sonnet-4-6")
    temperature = float(agent.get("temperature", 0.2))

    if env_override and env_override == "mock":
        fallback_provider, fallback_model = None, None
    else:
        fallback_provider = agent.get("fallback_provider")
        fallback_model = agent.get("fallback_model")

    return {
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "fallback_provider": fallback_provider,
        "fallback_model": fallback_model,
        "timeout": int(defaults.get("timeout_seconds", DEFAULT_TIMEOUT)),
        "max_retries": int(defaults.get("max_retries", DEFAULT_MAX_RETRIES)),
    }


def empty_usage() -> dict:
    return {"input_tokens": None, "output_tokens": None, "total_tokens": None}


def log_llm_event(
    *,
    agent_id: str,
    provider: str,
    model: str,
    status: str,
    prompt: str,
    output_text: str = "",
    error: str | None = None,
    usage: dict | None = None,
    fallback_used: bool = False,
) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    usage = usage or empty_usage()
    event = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "agent_id": agent_id,
        "provider": provider,
        "model": model,
        "status": status,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8", errors="replace")).hexdigest(),
        "input_chars": len(prompt),
        "output_chars": len(output_text),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "fallback_used": fallback_used,
        "error": error,
    }
    with LLM_USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _result(
    *,
    text: str,
    model: str,
    provider: str,
    used: bool,
    error: str | None = None,
    usage: dict | None = None,
    fallback_used: bool = False,
) -> dict:
    return {
        "text": text,
        "model": model,
        "provider": provider,
        "used": used,
        "error": error,
        "usage": usage or empty_usage(),
        "fallback_used": fallback_used,
    }


def _http_post(url: str, headers: dict, body: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _format_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            payload = {"raw": detail[:200]}
    except Exception:
        payload = {}
    return f"HTTP {exc.code}: {json.dumps(payload, ensure_ascii=False)[:300]}"


def mock_response(agent_id: str, model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8", errors="replace")).hexdigest()[:8]
    text = (
        f"[MOCK::{agent_id}::{digest}]\n"
        "이것은 mock 응답입니다. 실 API 키 없이 흐름 검증용으로 생성되었습니다.\n"
        "실제 LLM 호출이 필요하면 .env에 ANTHROPIC_API_KEY 또는 GEMINI_API_KEY를 설정하세요.\n"
    )
    return _result(text=text, model=f"mock:{model}", provider="mock", used=True)


def call_anthropic(
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    instructions: str,
    prompt: str,
    timeout: int,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    url = f"{base_url.rstrip('/')}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }
    body: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if instructions:
        body["system"] = instructions

    payload = _http_post(url, headers, body, timeout)
    chunks: list[str] = []
    for block in payload.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                chunks.append(text)
    text = "\n".join(chunks).strip()

    raw_usage = payload.get("usage") or {}
    input_tokens = raw_usage.get("input_tokens")
    output_tokens = raw_usage.get("output_tokens")
    total = None
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        total = input_tokens + output_tokens

    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
    }
    return _result(text=text, model=model, provider="anthropic", used=True, usage=usage)


def call_google(
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    instructions: str,
    prompt: str,
    timeout: int,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    url = f"{base_url.rstrip('/')}/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if instructions:
        body["systemInstruction"] = {"parts": [{"text": instructions}]}

    payload = _http_post(url, headers, body, timeout)
    chunks: list[str] = []
    for candidate in payload.get("candidates", []) or []:
        for part in (candidate.get("content") or {}).get("parts", []) or []:
            text = part.get("text") if isinstance(part, dict) else None
            if isinstance(text, str):
                chunks.append(text)
    text = "\n".join(chunks).strip()

    meta = payload.get("usageMetadata") or {}
    usage = {
        "input_tokens": meta.get("promptTokenCount"),
        "output_tokens": meta.get("candidatesTokenCount"),
        "total_tokens": meta.get("totalTokenCount"),
    }
    return _result(text=text, model=model, provider="google", used=True, usage=usage)


def _call_one(
    *,
    provider: str,
    model: str,
    temperature: float,
    instructions: str,
    prompt: str,
    timeout: int,
    max_retries: int,
) -> dict:
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return _result(text="", model=model, provider=provider, used=False, error="ANTHROPIC_API_KEY is not set")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        caller = lambda: call_anthropic(
            api_key=api_key, base_url=base_url, model=model, temperature=temperature,
            instructions=instructions, prompt=prompt, timeout=timeout,
        )
    elif provider == "google":
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return _result(text="", model=model, provider=provider, used=False, error="GEMINI_API_KEY is not set")
        base_url = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
        caller = lambda: call_google(
            api_key=api_key, base_url=base_url, model=model, temperature=temperature,
            instructions=instructions, prompt=prompt, timeout=timeout,
        )
    else:
        return _result(text="", model=model, provider=provider, used=False, error=f"Unsupported provider: {provider}")

    last_error: str | None = None
    for attempt in range(max_retries + 1):
        try:
            return caller()
        except urllib.error.HTTPError as exc:
            last_error = _format_http_error(exc)
            if exc.code < 500 and exc.code != 429:
                break
        except Exception as exc:
            last_error = str(exc)
        if attempt < max_retries:
            time.sleep(min(2 ** attempt, 8))

    return _result(text="", model=model, provider=provider, used=False, error=last_error)


def _no_api_keys_present() -> bool:
    """True when no provider keys are configured. Triggers the mock safety net."""
    return not (
        os.environ.get("ANTHROPIC_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )


def complete(agent_id: str, instructions: str, prompt: str, use_llm: bool = True) -> dict:
    """Run a single completion for the given agent.

    Returns a dict with keys: text, model, provider, used, error, usage, fallback_used.
    `use_llm=False` or provider="mock" returns a deterministic mock response with used=True.
    Safety net: if no API keys are present in env, the caller falls back to mock
    even when provider is anthropic/google. This honors the spec "mock 모드가 기본값".
    """
    load_dotenv()
    settings = agent_model(agent_id)
    provider = settings["provider"]
    model = settings["model"]

    if not use_llm or provider == "mock" or _no_api_keys_present():
        result = mock_response(agent_id, model, prompt)
        log_llm_event(
            agent_id=agent_id, provider=result["provider"], model=result["model"],
            status="mock", prompt=prompt, output_text=result["text"], usage=result["usage"],
        )
        return result

    primary = _call_one(
        provider=provider,
        model=model,
        temperature=settings["temperature"],
        instructions=instructions,
        prompt=prompt,
        timeout=settings["timeout"],
        max_retries=settings["max_retries"],
    )

    if primary["used"]:
        log_llm_event(
            agent_id=agent_id, provider=primary["provider"], model=primary["model"],
            status="ok", prompt=prompt, output_text=primary["text"], usage=primary["usage"],
        )
        return primary

    fallback_provider = settings["fallback_provider"]
    fallback_model = settings["fallback_model"]
    if not fallback_provider or not fallback_model:
        log_llm_event(
            agent_id=agent_id, provider=primary["provider"], model=primary["model"],
            status="error", prompt=prompt, error=primary["error"],
        )
        return primary

    fallback = _call_one(
        provider=fallback_provider,
        model=fallback_model,
        temperature=settings["temperature"],
        instructions=instructions,
        prompt=prompt,
        timeout=settings["timeout"],
        max_retries=settings["max_retries"],
    )
    fallback["fallback_used"] = True

    status = "fallback_ok" if fallback["used"] else "fallback_error"
    error_for_log = None if fallback["used"] else f"primary={primary['error']}; fallback={fallback['error']}"
    log_llm_event(
        agent_id=agent_id, provider=fallback["provider"], model=fallback["model"],
        status=status, prompt=prompt, output_text=fallback["text"], usage=fallback["usage"],
        error=error_for_log, fallback_used=True,
    )
    return fallback


__all__ = [
    "agent_model",
    "call_anthropic",
    "call_google",
    "complete",
    "load_dotenv",
    "load_model_config",
    "log_llm_event",
    "mock_response",
]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Smoke-test the client-ops LLM client.")
    parser.add_argument("--agent", default="01_onboarding_manager")
    parser.add_argument("--prompt", default="자기 소개를 한 줄로 해줘.")
    parser.add_argument("--mock", action="store_true", help="Force mock (no API call).")
    args = parser.parse_args()

    res = complete(args.agent, "테스트 instructions", args.prompt, use_llm=not args.mock)
    print(json.dumps(res, ensure_ascii=False, indent=2))
