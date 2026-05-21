from __future__ import annotations

from llm_client import complete


def main() -> int:
    result = complete(
        "05_ops_manager",
        "You are a minimal API health check. Reply with OK only.",
        "Return OK if this OpenAI API request works.",
        use_llm=True,
    )

    print(f"provider={result.provider}")
    print(f"model={result.model}")
    if result.used and result.text:
        print("status=ok")
        print(f"sample={result.text.strip()[:80]}")
        return 0

    print("status=failed")
    print(f"error={result.error or 'no response'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
