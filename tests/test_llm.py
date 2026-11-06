import json

import httpx
import pytest
from pydantic import SecretStr

from jobmarket import llm
from jobmarket.settings import Settings


def settings(**kw):
    return Settings(_env_file=None, groq_api_key=SecretStr("k"), gemini_api_key=SecretStr("k"), **kw)


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_provider_is_chosen_by_configuration_only():
    assert isinstance(llm.get_llm(settings=settings(llm_provider="groq")), llm.GroqChat)
    assert isinstance(llm.get_llm(settings=settings(llm_provider="gemini")), llm.GeminiChat)
    model = llm.get_llm(settings=settings(llm_provider="ollama", llm_model="gemma2:9b"))
    assert isinstance(model, llm.OllamaChat) and model.model == "gemma2:9b"
    with pytest.raises(llm.ModelError):
        llm.get_llm("unknown", settings=settings())


def test_groq_chat_parses_text_and_tokens():
    def handler(request):
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert request.headers["authorization"] == "Bearer k"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 7, "completion_tokens": 2}},
        )

    chat = llm.GroqChat(settings(), "openai/gpt-oss-20b", client=client(handler))
    result = chat.chat("sys", "user", json_output=True)
    assert (result.text, result.input_tokens, result.output_tokens) == ("{}", 7, 2)


def test_rate_limits_are_retried_then_succeed(monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})

    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)
    chat = llm.GeminiChat(settings(), "gemini-3.5-flash-lite", client=client(handler))
    assert chat.chat("s", "u").text == "hi" and len(calls) == 3


def test_permanent_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, text="bad key")

    with pytest.raises(llm.ModelError, match="401"):
        llm.GroqChat(settings(), "m", client=client(handler)).chat("s", "u")
    assert len(calls) == 1


def test_nomic_embeddings_use_task_prefixes():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content)["input"])
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]] * len(seen[-1])})

    emb = llm.OllamaEmbedder(settings(), "nomic-embed-text", client=client(handler))
    emb.embed_documents(["a"])
    emb.embed_query("b")
    assert seen == [["search_document: a"], ["search_query: b"]]
    assert emb.name == "ollama:nomic-embed-text"


def test_groq_invalid_json_is_retried_without_json_mode(monkeypatch):
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": {"code": "json_validate_failed"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}}]})

    result = llm.GroqChat(settings(), "m", client=client(handler)).chat("s", "u", json_output=True)
    assert result.text == '{"ok": 1}' and len(bodies) == 2 and "response_format" not in bodies[1]
