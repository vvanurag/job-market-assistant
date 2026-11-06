"""The one interface to language and embedding models (FR-QA-08, NFR-25, ADR-0006).

Everything else calls ``get_llm()`` and ``get_embedder()``; only this module knows how
each provider's API works. Switching provider is configuration only:

    LLM_PROVIDER=groq|gemini|ollama      LLM_MODEL=<model name>      (chat)
    EMBEDDING_MODEL=ollama:nomic-embed-text | gemini:gemini-embedding-001

Rate limits and transient errors are retried with exponential backoff (NFR-27).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from jobmarket.settings import Settings, get_settings

DEFAULT_CHAT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.5-flash-lite",  # gemini-2.5-* is closed to new keys; full Flash is often overloaded
    "ollama": "llama3",
}
RETRY_WAITS_SECONDS = (2, 5, 15, 30)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Some embedding models are trained with task prefixes; using them improves retrieval.
EMBEDDING_PREFIXES = {
    "nomic-embed-text": ("search_document: ", "search_query: "),
    "mxbai-embed-large": ("", "Represent this sentence for searching relevant passages: "),
}


class ModelError(RuntimeError):
    """A model call failed permanently (after retries)."""


@dataclass(frozen=True)
class ChatResult:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLM(Protocol):
    provider: str
    model: str

    def chat(self, system: str, user: str, *, json_output: bool = False, max_tokens: int = 1200) -> ChatResult: ...


class Embedder(Protocol):
    name: str  # "<provider>:<model>", recorded with every index build (FR-IDX-07)
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _post(
    client: httpx.Client,
    url: str,
    *,
    json: dict,
    headers: dict | None = None,
    sleep: Callable[[float], None] = time.sleep,
    timeout: float = 120,
) -> dict:
    """POST with retries on rate limits, server errors and network failures."""
    last_error = ""
    for attempt in range(len(RETRY_WAITS_SECONDS) + 1):
        try:
            resp = client.post(url, json=json, headers=headers, timeout=timeout)
        except httpx.TransportError as exc:
            last_error = f"network error: {exc.__class__.__name__}"
        else:
            if resp.status_code < 400:
                return resp.json()
            last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in RETRYABLE_STATUS:
                break
            retry_after = resp.headers.get("retry-after")
            if retry_after and retry_after.replace(".", "", 1).isdigit() and attempt < len(RETRY_WAITS_SECONDS):
                sleep(min(float(retry_after), 60))
                continue
        if attempt < len(RETRY_WAITS_SECONDS):
            sleep(RETRY_WAITS_SECONDS[attempt])
    raise ModelError(f"{url.split('?')[0]} failed: {last_error}")


# --- chat providers ---------------------------------------------------------------


class OllamaChat:
    provider = "ollama"

    def __init__(self, settings: Settings, model: str, client: httpx.Client | None = None):
        self.model, self.base = model, settings.ollama_base_url.rstrip("/")
        self.client = client or httpx.Client()

    def chat(self, system: str, user: str, *, json_output: bool = False, max_tokens: int = 1200) -> ChatResult:
        start = time.perf_counter()
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": max_tokens},
        }
        if json_output:
            body["format"] = "json"
        data = _post(self.client, f"{self.base}/api/chat", json=body, timeout=300)
        return ChatResult(
            text=data["message"]["content"],
            provider=self.provider,
            model=self.model,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


class GroqChat:
    """Groq Cloud's OpenAI-compatible chat API."""

    provider = "groq"
    url = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, settings: Settings, model: str, client: httpx.Client | None = None):
        if not settings.groq_api_key:
            raise ModelError("GROQ_API_KEY is not set in .env")
        self.model, self.key = model, settings.groq_api_key.get_secret_value()
        self.client = client or httpx.Client()

    def chat(self, system: str, user: str, *, json_output: bool = False, max_tokens: int = 1200) -> ChatResult:
        start = time.perf_counter()
        body: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "max_completion_tokens": max_tokens,
        }
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"  # keeps latency within NFR-05
            body["max_completion_tokens"] = max_tokens + 1000  # room for the reasoning tokens
        if json_output:
            body["response_format"] = {"type": "json_object"}
        try:
            data = _post(self.client, self.url, json=body, headers={"Authorization": f"Bearer {self.key}"})
        except ModelError as exc:
            # Groq rejects a reply that isn't valid JSON in JSON mode; ask again without the
            # constraint (the prompt still asks for JSON, and callers extract it)
            if "json_validate_failed" not in str(exc):
                raise
            body.pop("response_format", None)
            data = _post(self.client, self.url, json=body, headers={"Authorization": f"Bearer {self.key}"})
        usage = data.get("usage") or {}
        return ChatResult(
            text=data["choices"][0]["message"]["content"] or "",
            provider=self.provider,
            model=self.model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


class GeminiChat:
    """Google AI Studio's generateContent API."""

    provider = "gemini"
    base = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, settings: Settings, model: str, client: httpx.Client | None = None):
        if not settings.gemini_api_key:
            raise ModelError("GEMINI_API_KEY is not set in .env")
        self.model, self.key = model, settings.gemini_api_key.get_secret_value()
        self.client = client or httpx.Client()

    def chat(self, system: str, user: str, *, json_output: bool = False, max_tokens: int = 1200) -> ChatResult:
        start = time.perf_counter()
        config: dict = {"temperature": 0, "maxOutputTokens": max_tokens}
        if "2.5" in self.model:
            config["thinkingConfig"] = {"thinkingBudget": 0}  # keeps latency within NFR-05
        if json_output:
            config["responseMimeType"] = "application/json"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": config,
        }
        data = _post(
            self.client,
            f"{self.base}/{self.model}:generateContent",
            json=body,
            headers={"x-goog-api-key": self.key},
        )
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        usage = data.get("usageMetadata") or {}
        return ChatResult(
            text="".join(p.get("text", "") for p in parts),
            provider=self.provider,
            model=self.model,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


CHAT_PROVIDERS = {"ollama": OllamaChat, "groq": GroqChat, "gemini": GeminiChat}


def get_llm(provider: str | None = None, model: str | None = None, settings: Settings | None = None) -> LLM:
    settings = settings or get_settings()
    provider = (provider or settings.llm_provider).lower()
    if provider not in CHAT_PROVIDERS:
        raise ModelError(f"unknown LLM provider {provider!r}; choose from {sorted(CHAT_PROVIDERS)}")
    model = (
        model or (settings.llm_model if provider == settings.llm_provider else None) or DEFAULT_CHAT_MODELS[provider]
    )
    return CHAT_PROVIDERS[provider](settings, model)


# --- embedding providers ----------------------------------------------------------


class OllamaEmbedder:
    def __init__(self, settings: Settings, model: str, client: httpx.Client | None = None):
        self.model, self.base = model, settings.ollama_base_url.rstrip("/")
        self.name = f"ollama:{model}"
        self.client = client or httpx.Client()
        self.doc_prefix, self.query_prefix = EMBEDDING_PREFIXES.get(model.split(":")[0], ("", ""))
        self._dimensions: int | None = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        data = _post(self.client, f"{self.base}/api/embed", json={"model": self.model, "input": texts}, timeout=600)
        return data["embeddings"]

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            self._dimensions = len(self._embed(["dimension probe"])[0])
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([self.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self.query_prefix + text])[0]


class GeminiEmbedder:
    base = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, settings: Settings, model: str, dimensions: int = 768, client: httpx.Client | None = None):
        if not settings.gemini_api_key:
            raise ModelError("GEMINI_API_KEY is not set in .env")
        self.model, self.key, self.dimensions = model, settings.gemini_api_key.get_secret_value(), dimensions
        self.name = f"gemini:{model}"
        self.client = client or httpx.Client()

    def _embed(self, text: str, task: str) -> list[float]:
        body = {
            "content": {"parts": [{"text": text}]},
            "taskType": task,
            "outputDimensionality": self.dimensions,
        }
        data = _post(
            self.client, f"{self.base}/{self.model}:embedContent", json=body, headers={"x-goog-api-key": self.key}
        )
        return data["embedding"]["values"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t, "RETRIEVAL_DOCUMENT") for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, "RETRIEVAL_QUERY")


def get_embedder(name: str | None = None, settings: Settings | None = None) -> Embedder:
    settings = settings or get_settings()
    name = name or settings.embedding_model
    provider, _, model = name.partition(":")
    if provider == "ollama":
        return OllamaEmbedder(settings, model)
    if provider == "gemini":
        return GeminiEmbedder(settings, model)
    raise ModelError(f"unknown embedding model {name!r}; use 'ollama:<model>' or 'gemini:<model>'")
