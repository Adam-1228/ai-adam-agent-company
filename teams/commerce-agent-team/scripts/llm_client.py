from __future__ import annotations

import json
import os
import hashlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
MODEL_CONFIG_PATH = ROOT / "config" / "agent_models.json"
RUNTIME_DIR = ROOT / "runtime"
LLM_USAGE_LOG = RUNTIME_DIR / "llm_usage.jsonl"


@dataclass
class LLMResult:
    used: bool
    provider: str
    model: str
    text: str
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_model_config() -> dict:
    if not MODEL_CONFIG_PATH.exists():
        return {"default_provider": "mock", "default_model": "gpt-5.4-mini", "agents": {}}
    return json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))


def agent_model(agent_id: str) -> tuple[str, str, float]:
    config = load_model_config()
    agent = config.get("agents", {}).get(agent_id, {})
    provider = os.environ.get("LLM_PROVIDER") or agent.get("provider") or config.get("default_provider", "mock")
    model = agent.get("model") or config.get("default_model", "gpt-5.4-mini")
    temperature = float(agent.get("temperature", 0.2))
    return provider, model, temperature


def extract_openai_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def summarize_http_error(exc: urllib.error.HTTPError) -> str:
    detail = exc.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return f"HTTP {exc.code}"

    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = error.get("code") or payload.get("status") or "unknown_error"
    error_type = error.get("type") or "openai_error"
    message = error.get("message") or ""

    if code == "invalid_api_key" or "Incorrect API key" in message:
        return "HTTP 401 invalid_api_key: OpenAI API key was rejected."
    if exc.code == 429:
        return f"HTTP 429 {code}: rate limit or quota issue."
    if exc.code >= 500:
        return f"HTTP {exc.code} {error_type}: OpenAI service error."
    return f"HTTP {exc.code} {code}: {error_type}"


def parse_usage(payload: dict) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None, None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    return input_tokens, output_tokens, total_tokens


def log_llm_event(
    *,
    agent_id: str,
    provider: str,
    model: str,
    status: str,
    prompt: str,
    output_text: str = "",
    error: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "agent_id": agent_id,
        "provider": provider,
        "model": model,
        "status": status,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8", errors="replace")).hexdigest(),
        "input_chars": len(prompt),
        "output_chars": len(output_text),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "error": error,
    }
    with LLM_USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def complete(agent_id: str, instructions: str, prompt: str, use_llm: bool) -> LLMResult:
    load_dotenv()
    provider, model, temperature = agent_model(agent_id)

    if not use_llm or provider == "mock":
        return LLMResult(False, provider, model, "", None)

    if provider != "openai":
        return LLMResult(False, provider, model, "", f"Unsupported provider: {provider}")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return LLMResult(False, provider, model, "", "OPENAI_API_KEY is not set")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = {
        "model": model,
        "instructions": instructions,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    }
                ],
            }
        ],
        "temperature": temperature,
    }

    request = urllib.request.Request(
        f"{base_url}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = extract_openai_text(payload)
        input_tokens, output_tokens, total_tokens = parse_usage(payload)
        log_llm_event(
            agent_id=agent_id,
            provider=provider,
            model=model,
            status="ok",
            prompt=prompt,
            output_text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        return LLMResult(True, provider, model, text, None, input_tokens, output_tokens, total_tokens)
    except urllib.error.HTTPError as exc:
        error = summarize_http_error(exc)
        log_llm_event(agent_id=agent_id, provider=provider, model=model, status="error", prompt=prompt, error=error)
        return LLMResult(False, provider, model, "", error)
    except Exception as exc:
        error = str(exc)
        log_llm_event(agent_id=agent_id, provider=provider, model=model, status="error", prompt=prompt, error=error)
        return LLMResult(False, provider, model, "", error)
