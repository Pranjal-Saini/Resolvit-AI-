"""LLM client: Groq first, local Ollama as fallback. Both speak the OpenAI API."""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLMUnavailable(Exception):
    pass


def _providers():
    if os.getenv("GROQ_API_KEY"):
        # gzip only: old brotlicffi (e.g. Anaconda) crashes httpx's brotli decoder on Groq responses.
        yield "groq", OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"],
                             max_retries=1, timeout=30, default_headers={"Accept-Encoding": "gzip"}), \
            os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"), {"reasoning_effort": "low"}
    # reasoning_effort=none turns off qwen3 thinking: ~60s -> ~1s per call on a laptop.
    yield "ollama", OpenAI(base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama",
                           max_retries=0, timeout=180), os.getenv("OLLAMA_MODEL", "qwen3:8b"), {"reasoning_effort": "none"}


def chat(messages: list[dict], tools: list[dict] | None = None):
    """Returns the assistant message (openai ChatCompletionMessage). Raises LLMUnavailable if all providers fail."""
    errors = []
    for name, client, model, extra in _providers():
        try:
            kwargs = {"model": model, "messages": messages, "temperature": 0, **extra}
            if tools:
                kwargs["tools"] = tools
            return client.chat.completions.create(**kwargs).choices[0].message
        except Exception as e:  # rate limit, network, bad key: try the next provider
            errors.append(f"{name}: {e}")
            print(f"[llm] {name} failed, falling back: {str(e)[:200]}", file=sys.stderr)
    raise LLMUnavailable("; ".join(errors))
