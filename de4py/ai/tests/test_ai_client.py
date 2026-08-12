# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from de4py.ai.client import AIConfig, AIClient, PROVIDERS, resolve_ai_config


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, error=None, headers=None):
        self.status_code = status_code
        self._json = json_data
        self._error = error
        self.headers = headers or {}

    def raise_for_status(self):
        if self._error:
            raise self._error
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def _settings(**overrides):
    base = dict(ai_provider="ollama")
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _isolate_credentials(monkeypatch):
    """Tests must never touch the real OS credential store."""
    stored = {}

    def fake_get(provider):
        return stored.get(provider, "")

    def fake_set(provider, key, mode="auto"):
        if key:
            stored[provider] = key
            return True
        stored.pop(provider, None)
        return True

    monkeypatch.setattr("de4py.ai.credentials.get_secret", fake_get)
    monkeypatch.setattr("de4py.ai.credentials.set_secret", fake_set)
    return stored


# -- config resolution ------------------------------------------------------

def test_resolve_ai_config_cloud_presets(_isolate_credentials):
    for pid in ("openai", "openrouter", "opencode", "gemini"):
        cfg = resolve_ai_config(_settings(ai_provider=pid))
        assert cfg.provider == pid
        assert cfg.base_url == PROVIDERS[pid]["base_url"]
        assert cfg.model == PROVIDERS[pid]["default_model"]


def test_resolve_ai_config_env_key_override(_isolate_credentials, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
    cfg = resolve_ai_config(_settings(ai_provider="openai"))
    assert cfg.api_key == "sk-env-key"


def test_stored_key_beats_env_var(_isolate_credentials, monkeypatch):
    _isolate_credentials["openai"] = "sk-stored"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
    cfg = resolve_ai_config(_settings(ai_provider="openai"))
    assert cfg.api_key == "sk-stored"


def test_resolve_ai_config_per_provider_fields(_isolate_credentials):
    cfg = resolve_ai_config(_settings(
        ai_provider="gemini", ai_gemini_model="gemini-custom",
        ai_gemini_base_url="http://proxy/v1",
    ))
    assert cfg.model == "gemini-custom"
    assert cfg.base_url == "http://proxy/v1"


def test_provider_credentials_are_isolated(_isolate_credentials):
    _isolate_credentials["gemini"] = "AIza-gemini-key"
    cfg = resolve_ai_config(_settings(ai_provider="openai"))
    assert cfg.api_key == ""


def test_resolve_ai_config_custom(_isolate_credentials):
    cfg = resolve_ai_config(_settings(
        ai_provider="custom", ai_custom_model="my-model",
        ai_custom_base_url="http://host:8000/v1",
    ))
    assert cfg.base_url == "http://host:8000/v1"
    assert cfg.model == "my-model"


def test_resolve_ai_config_unknown_provider_falls_back_to_custom(_isolate_credentials):
    cfg = resolve_ai_config(_settings(ai_provider="weird"))
    assert cfg.provider == "custom"


def test_ollama_hw_tuning_low_ram(monkeypatch):
    monkeypatch.setattr("de4py.ai.client._detect_vram_gb", lambda: 0)
    monkeypatch.setattr(
        "de4py.ai.client.psutil.virtual_memory",
        lambda: SimpleNamespace(total=4 * 1024 ** 3),
    )
    from de4py.ai.client import _ollama_hw_tuning
    _ollama_hw_tuning.cache_clear()
    cfg = resolve_ai_config(_settings(ai_provider="ollama"))
    assert cfg.is_ollama
    assert cfg.ollama_options["num_ctx"] == 512
    assert cfg.ollama_options["num_gpu"] == 0


# -- availability -----------------------------------------------------------

def test_cloud_available_requires_key_and_base_url():
    assert AIClient(AIConfig(provider="openai", base_url="x", api_key="", model="m")).available is False
    assert AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m")).available is True
    assert AIClient(AIConfig(provider="openai", base_url="", api_key="k", model="m")).available is False


def test_custom_provider_works_without_key():
    cfg = AIConfig(provider="custom", base_url="http://host:8000/v1", api_key="", model="m")
    assert AIClient(cfg).available is True
    assert AIClient(AIConfig(provider="custom", base_url="", api_key="", model="m")).available is False


def test_ollama_available_reachable(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.client.requests.get",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={
            "models": [{"name": "qwen2.5-coder:1.5b"}]
        }),
    )
    cfg = AIConfig(provider="ollama", base_url=PROVIDERS["ollama"]["base_url"],
                   model="qwen2.5-coder:1.5b", context_window=4096)
    client = AIClient(cfg)
    assert client.available is True
    assert client.ensure_model() is True


def test_ollama_unreachable():
    cfg = AIConfig(provider="ollama", base_url=PROVIDERS["ollama"]["base_url"], model="qwen")
    client = AIClient(cfg)
    client._available = False
    assert client.available is False


# -- chat -------------------------------------------------------------------

def test_chat_builds_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "  hello world  "}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    cfg = AIConfig(provider="openai", base_url="https://api.openai.com/v1",
                   api_key="sk-x", model="gpt-4o-mini")
    client = AIClient(cfg)
    out = client.chat("sys", "usr", temperature=0.3, max_tokens=128)
    assert out == "hello world"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-x"
    assert captured["json"]["model"] == "gpt-4o-mini"
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert captured["json"]["temperature"] == 0.3
    assert captured["json"]["max_tokens"] == 128
    assert "response_format" not in captured["json"]


def test_chat_json_mode(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "{}"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    client.chat("s", "u", json_mode=True)
    assert captured["json"]["response_format"] == {"type": "json_object"}


def test_chat_o_series_payload(monkeypatch):
    """o-series reasoning models (o3-mini, o1, ...) reject max_tokens and
    temperature — they use max_completion_tokens and fix temperature at 1."""
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "42"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k",
                               model="o3-mini"))
    out = client.chat("s", "u", temperature=0.7, max_tokens=256)
    assert out == "42"
    assert captured["json"]["model"] == "o3-mini"
    assert captured["json"]["max_completion_tokens"] == 256
    assert "max_tokens" not in captured["json"]
    assert "temperature" not in captured["json"]


def test_chat_o_series_prefixed_model_payload(monkeypatch):
    """OpenRouter ids like openai/o3-mini must get the o-series payload too
    (the o3 model behind it rejects max_tokens/temperature)."""
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "42"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="openrouter", base_url="x", api_key="k",
                               model="openai/o3-mini"))
    out = client.chat("s", "u", temperature=0.7, max_tokens=256)
    assert out == "42"
    assert captured["json"]["max_completion_tokens"] == 256
    assert "max_tokens" not in captured["json"]
    assert "temperature" not in captured["json"]


def test_chat_gpt5_payload(monkeypatch):
    """gpt-5.x flagships use max_completion_tokens and reject temperature/
    max_tokens, exactly like the o-series."""
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "42"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    for model in ("gpt-5.6-sol", "gpt-5.5-pro", "gpt-5.4-mini",
                  "gpt-5.6-cyber", "daybreak-red", "openai/gpt-5.6-sol"):
        client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k",
                                   model=model))
        out = client.chat("s", "u", temperature=0.7, max_tokens=256)
        assert out == "42"
        assert captured["json"]["max_completion_tokens"] == 256, model
        assert "max_tokens" not in captured["json"], model
        assert "temperature" not in captured["json"], model


def test_chat_non_o_series_keeps_temperature_and_max_tokens(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "ok"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k",
                               model="gpt-4o-mini"))
    client.chat("s", "u", temperature=0.7, max_tokens=256)
    assert captured["json"]["temperature"] == 0.7
    assert captured["json"]["max_tokens"] == 256
    assert "max_completion_tokens" not in captured["json"]


def test_chat_o_series_json_mode(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "{}"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k",
                               model="o1-preview"))
    client.chat("s", "u", json_mode=True)
    assert captured["json"]["max_completion_tokens"] == 2048
    assert captured["json"]["response_format"] == {"type": "json_object"}


def test_chat_sends_ollama_options(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "ok"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    cfg = AIConfig(provider="ollama", base_url=PROVIDERS["ollama"]["base_url"],
                   model="qwen", ollama_options={"num_ctx": 512})
    client = AIClient(cfg)
    client.chat("s", "u")
    assert captured["json"]["options"] == {"num_ctx": 512}
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"


def test_chat_no_auth_header_for_ollama(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["headers"] = headers
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "ok"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="ollama", base_url="http://localhost:11434/v1",
                               api_key="", model="qwen"))
    client.chat("s", "u")
    assert "Authorization" not in captured["headers"]


def test_chat_timeout_returns_none(monkeypatch):
    import requests

    def boom(*a, **k):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("de4py.ai.providers.requests.post", boom)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    assert client.chat("s", "u") is None


def test_chat_unexpected_exception_returns_none(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr("de4py.ai.providers.requests.post", boom)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    assert client.chat("s", "u") is None


def test_chat_retries_transient_errors(monkeypatch):
    calls = {"n": 0}

    def flaky(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResponse(status_code=500, json_data={})
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "recovered"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", flaky)
    monkeypatch.setattr("de4py.ai.client.time.sleep", lambda s: None)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    assert client.chat("s", "u") == "recovered"
    assert calls["n"] == 2


def test_chat_does_not_retry_on_401(monkeypatch):
    calls = {"n": 0}

    def deny(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        return _FakeResponse(status_code=401, json_data={})

    monkeypatch.setattr("de4py.ai.providers.requests.post", deny)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    assert client.chat("s", "u") is None
    assert calls["n"] == 1


def test_chat_respects_retry_after(monkeypatch):
    calls = {"n": 0}

    def limited(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResponse(status_code=429, json_data={}, headers={"Retry-After": "0"})
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "ok"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", limited)
    monkeypatch.setattr("de4py.ai.client.time.sleep", lambda s: None)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    assert client.chat("s", "u") == "ok"
    assert calls["n"] == 2


def test_chat_malformed_response_returns_none(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={"unexpected": True}),
    )
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    assert client.chat("s", "u") is None


def test_ensure_model_noop_for_cloud():
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    assert client.ensure_model() is True


# -- test connection + model discovery --------------------------------------

def test_test_connection_401_shows_provider_message(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=401, json_data={
            "error": {"message": "Incorrect API key provided: sk-bad-key. Fix it."}
        }),
    )
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="sk-bad-key", model="m"))
    status = client.test_connection()
    assert status.connected is False
    # the user sees what the provider actually said, not a canned message
    assert "Incorrect API key" in status.message
    assert "Fix it" in status.message


def test_test_connection_401_redacts_echoed_key(monkeypatch):
    """A provider that echoes the API key back in its error body must not
    leak it into the UI message."""
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=401, json_data={
            "error": {"message": "Incorrect API key provided: sk-bad-key."}
        }),
    )
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="sk-bad-key", model="m"))
    status = client.test_connection()
    assert status.connected is False
    assert "sk-bad-key" not in status.message
    assert "••••" in status.message


def test_test_connection_fallback_when_no_detail(monkeypatch):
    """No usable body -> translated fallback message, never the raw key."""
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=401, json_data={}),
    )
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="bad", model="m"))
    status = client.test_connection()
    assert status.connected is False
    assert "API key" in status.message
    assert "bad" not in status.message  # credential never leaked


def test_test_connection_404_shows_provider_message(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=404, json_data={
            "error": {"message": "The model `does-not-exist` was not found."}
        }),
    )
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    status = client.test_connection()
    assert status.connected is False
    assert "does-not-exist" in status.message
    assert "was not found" in status.message


def test_test_connection_success(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "OK"}}]
        }),
    )
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    status = client.test_connection()
    assert status.connected is True
    assert status.latency_ms >= 0.0
    # the UI shows what the API actually replied
    assert "OK" in status.message


def test_test_connection_not_configured():
    client = AIClient(AIConfig(provider="openai", base_url="", api_key="", model=""))
    status = client.test_connection()
    assert status.connected is False


def test_known_models_catalog_current_lineup():
    """The offline fallback catalog reflects the current OpenAI lineup."""
    from de4py.ai.providers import KNOWN_MODELS
    openai = KNOWN_MODELS["openai"]
    for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
                  "gpt-5.5", "gpt-5.5-pro", "gpt-5.4-mini", "gpt-5.4-nano",
                  "gpt-4o", "gpt-4o-mini", "o3", "o3-pro", "o4-mini",
                  "gpt-5.3-codex", "gpt-5.6-cyber"):
        assert model in openai, model
    assert "o3-mini" in openai
    assert "daybreak-red" in openai
    assert "daybreak-blue" in openai


def test_known_models_opencode_free_lineup():
    """The offline OpenCode Zen fallback mirrors the documented free tier."""
    from de4py.ai.providers import KNOWN_MODELS

    opencode = KNOWN_MODELS["opencode"]
    for model in (
        "deepseek-v4-flash-free", "laguna-s-2.1-free", "nemotron-3-ultra-free",
        "ling-3.0-tiny-free", "mimo-v2.5-free", "hy3-free", "big-pickle",
    ):
        assert model in opencode, model


def test_opencode_is_cloud_provider():
    """OpenCode Zen is a cloud gateway — code leaves the machine, so the
    privacy consent flow must apply (not be treated as a local provider)."""
    from de4py.ai.providers import is_local_provider
    assert not is_local_provider("opencode")


def test_opencode_default_model_and_env_key(_isolate_credentials, monkeypatch):
    """Unconfigured users land on the DeepSeek free model; OPENCODE_API_KEY
    supplies the credential."""
    assert PROVIDERS["opencode"]["base_url"] == "https://opencode.ai/zen/v1"
    assert PROVIDERS["opencode"]["env_key"] == "OPENCODE_API_KEY"
    assert PROVIDERS["opencode"]["default_model"] == "deepseek-v4-flash-free"

    cfg = resolve_ai_config(_settings(ai_provider="opencode"))
    assert cfg.model == "deepseek-v4-flash-free"
    assert cfg.api_key == ""

    monkeypatch.setenv("OPENCODE_API_KEY", "oc-zen-key")
    cfg = resolve_ai_config(_settings(ai_provider="opencode"))
    assert cfg.api_key == "oc-zen-key"


def test_chat_opencode_legacy_payload(monkeypatch):
    """OpenCode Zen free models are standard OpenAI-compatible chat models —
    they keep temperature + max_tokens."""
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "42"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="opencode",
                               base_url="https://opencode.ai/zen/v1",
                               api_key="oc-key", model="deepseek-v4-flash-free"))
    out = client.chat("s", "u", temperature=0.5, max_tokens=256)
    assert out == "42"
    assert captured["url"] == "https://opencode.ai/zen/v1/chat/completions"
    assert captured["json"]["model"] == "deepseek-v4-flash-free"
    assert captured["json"]["temperature"] == 0.5
    assert captured["json"]["max_tokens"] == 256
    assert "max_completion_tokens" not in captured["json"]
    assert captured["headers"]["Authorization"] == "Bearer oc-key"


def test_known_models_openrouter_free_lineup():
    """The offline OpenRouter fallback leads with the free tier: the dynamic
    openrouter/free auto-router plus the documented :free coding models."""
    from de4py.ai.providers import KNOWN_MODELS

    openrouter = KNOWN_MODELS["openrouter"]
    for model in (
        "openrouter/free", "poolside/laguna-xs-2.1:free",
        "cohere/north-mini-code:free", "openai/gpt-oss-20b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ):
        assert model in openrouter, model
    assert openrouter[0] == "openrouter/free"


def test_openrouter_default_model_is_free_router(_isolate_credentials):
    """New users default to OpenRouter's dynamic free auto-router, which
    failovers between free providers automatically."""
    assert PROVIDERS["openrouter"]["default_model"] == "openrouter/free"
    cfg = resolve_ai_config(_settings(ai_provider="openrouter"))
    assert cfg.model == "openrouter/free"


def test_chat_openrouter_free_models_legacy_payload(monkeypatch):
    """Free-tier models (openrouter/free and :free variants) are standard
    OpenAI-compatible chat models — they keep temperature + max_tokens."""
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "42"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    for model in ("openrouter/free", "meta-llama/llama-3.3-70b-instruct:free",
                  "openai/gpt-oss-20b:free"):
        client = AIClient(AIConfig(provider="openrouter", base_url="x", api_key="k",
                                   model=model))
        out = client.chat("s", "u", temperature=0.5, max_tokens=256)
        assert out == "42"
        assert captured["json"]["temperature"] == 0.5, model
        assert captured["json"]["max_tokens"] == 256, model
        assert "max_completion_tokens" not in captured["json"], model


def test_chat_openrouter_free_suffix_keeps_reasoning_payload(monkeypatch):
    """A :free variant of a gpt-5.x model is still gpt-5.x — it must keep the
    max_completion_tokens payload even with the :free suffix on the id."""
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "choices": [{"message": {"content": "42"}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="openrouter", base_url="x", api_key="k",
                               model="openai/gpt-5.6-sol:free"))
    out = client.chat("s", "u", temperature=0.7, max_tokens=256)
    assert out == "42"
    assert captured["json"]["max_completion_tokens"] == 256
    assert "max_tokens" not in captured["json"]
    assert "temperature" not in captured["json"]


def test_list_models_falls_back_to_known(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("offline")

    monkeypatch.setattr("de4py.ai.providers.requests.get", boom)
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    models = client.list_models()
    assert "gpt-4o-mini" in models


def test_list_models_discovers(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.get",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={
            "data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}, {"id": "o3-mini"}]
        }),
    )
    client = AIClient(AIConfig(provider="openai", base_url="x", api_key="k", model="m"))
    models = client.list_models()
    assert "gpt-4o" in models
    assert "gpt-4o-mini" in models


def test_ollama_test_connection_model_missing(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.get",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={"models": []}),
    )
    client = AIClient(AIConfig(provider="ollama", base_url="http://localhost:11434",
                               model="qwen2.5-coder:1.5b"))
    status = client.test_connection()
    assert status.connected is True
    assert "not installed" in status.message


# -- Gemini native REST API --------------------------------------------------

def test_gemini_chat_native_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse(status_code=200, json_data={
            "candidates": [{
                "content": {"parts": [{"text": "  hello  "}], "role": "model"},
                "finishReason": "STOP",
            }],
            "usageMetadata": {"totalTokenCount": 4},
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    cfg = AIConfig(
        provider="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="AIza-x", model="gemini-2.5-flash",
    )
    client = AIClient(cfg)
    out = client.chat("sys", "usr", temperature=0.2, max_tokens=1024)
    assert out == "hello"
    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.5-flash:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "AIza-x"
    assert "Authorization" not in captured["headers"]
    assert captured["json"] == {
        "contents": [{"parts": [{"text": "usr"}]}],
        "systemInstruction": {"parts": [{"text": "sys"}]},
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }


def test_gemini_json_mode_uses_response_mime_type(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="k", model="m"))
    client.chat("s", "u", json_mode=True)
    assert captured["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert "response_format" not in captured["json"]


def test_gemini_omits_system_instruction_when_empty(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(status_code=200, json_data={
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="k", model="m"))
    client.chat("", "u")
    assert "systemInstruction" not in captured["json"]


def test_gemini_handles_tuned_model_url(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        return _FakeResponse(status_code=200, json_data={
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="k", model="tunedModels/my-model"))
    assert client.chat("s", "u") == "ok"
    assert captured["url"] == "https://g/v1beta/tunedModels/my-model:generateContent"


def test_gemini_stored_legacy_base_url_normalized(monkeypatch):
    """Old configs pointing at the OpenAI-compat shim or the /interactions
    preset still hit the native endpoint."""
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        return _FakeResponse(status_code=200, json_data={
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        })

    monkeypatch.setattr("de4py.ai.providers.requests.post", fake_post)
    for legacy in (
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    ):
        client = AIClient(AIConfig(provider="gemini", base_url=legacy,
                                   api_key="k", model="gemini-2.5-flash"))
        assert client.chat("s", "u") == "ok"
        assert captured["url"].startswith(
            "https://generativelanguage.googleapis.com/v1beta/models/")


def test_gemini_test_connection_success(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={
            "candidates": [{"content": {"parts": [{"text": "OK"}]}}]
        }),
    )
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="k", model="gemini-2.5-flash"))
    status = client.test_connection()
    assert status.connected is True
    assert "OK" in status.message


def test_gemini_empty_generation_reports_finish_reason(monkeypatch):
    """A reasoning model that spends its whole budget on thoughts returns
    content: {} with finishReason MAX_TOKENS — surface that, don't call it
    malformed or show a generic error."""
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={
            "candidates": [{"content": {}, "finishReason": "MAX_TOKENS", "index": 0}]
        }),
    )
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="k", model="gemini-3.5-flash"))
    status = client.test_connection()
    assert status.connected is False
    assert "MAX_TOKENS" in status.message
    assert "malformed" not in status.message


def test_gemini_test_connection_403_shows_provider_message(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=403, json_data={
            "error": {
                "code": 403,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "PERMISSION_DENIED",
            }
        }),
    )
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="AIza-bad", model="gemini-2.5-flash"))
    status = client.test_connection()
    assert status.connected is False
    assert "API key not valid" in status.message


def test_gemini_test_connection_429_rate_limit_message(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.post",
        lambda *a, **k: _FakeResponse(status_code=429, json_data={
            "error": {
                "code": 429,
                "message": "Rapid Update Rate Limit exceeded. Please try again later.",
                "status": "RESOURCE_EXHAUSTED",
            }
        }),
    )
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="k", model="gemini-2.5-flash"))
    status = client.test_connection()
    assert status.connected is False
    assert "Rapid Update Rate Limit" in status.message


def test_gemini_list_models_native(monkeypatch):
    monkeypatch.setattr(
        "de4py.ai.providers.requests.get",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={
            "models": [
                {"name": "models/gemini-2.5-flash",
                 "supportedGenerationMethods": ["generateContent", "countTokens"]},
                {"name": "models/gemini-2.5-pro",
                 "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-embedding-001",
                 "supportedGenerationMethods": ["embedContent"]},
            ]
        }),
    )
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="k", model="m"))
    models = client.list_models()
    assert "gemini-2.5-flash" in models
    assert "gemini-2.5-pro" in models
    assert "gemini-embedding-001" not in models  # no generateContent support


def test_gemini_list_models_uses_header_not_query_key(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse(status_code=200, json_data={"models": []})

    monkeypatch.setattr("de4py.ai.providers.requests.get", fake_get)
    client = AIClient(AIConfig(provider="gemini", base_url="https://g/v1beta",
                               api_key="AIza-secret", model="m"))
    client.list_models()
    assert "AIza-secret" not in captured["url"]  # key must never appear in URLs
    assert captured["headers"]["x-goog-api-key"] == "AIza-secret"
