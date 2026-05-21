from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
MODEL_CONFIG_PATH = ROOT / "config" / "agent_models.json"


@dataclass
class LLMResult:
    used: bool
    provider: str
    model: str
    text: str
    error: str | None = None


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
        return LLMResult(True, provider, model, extract_openai_text(payload), None)
    except urllib.error.HTTPError as exc:
        return LLMResult(False, provider, model, "", summarize_http_error(exc))
    except Exception as exc:
        return LLMResult(False, provider, model, "", str(exc))
