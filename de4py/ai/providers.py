# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_PROVIDER_LABELS = {
    "ollama": "Ollama",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "opencode": "OpenCode Zen",
    "gemini": "Google Gemini",
    "custom": "Custom (OpenAI-compatible)",
}

#: Known compatible models used as a fallback when model discovery is
#: unavailable. Keep short — discovery is preferred, this is a safety net.
KNOWN_MODELS: Dict[str, List[str]] = {
    "ollama": [
        "qwen2.5-coder:1.5b", "qwen2.5-coder:7b", "qwen2.5-coder:14b",
        "llama3.1:8b", "codellama:7b", "deepseek-coder:6.7b",
    ],
    "openai": [
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
        "gpt-5.5", "gpt-5.5-pro", "gpt-5.4-mini", "gpt-5.4-nano",
        "gpt-4o", "gpt-4o-mini", "o3", "o3-pro", "o3-mini", "o4-mini",
        "gpt-5.3-codex", "gpt-5.6-cyber", "daybreak-red", "daybreak-blue",
    ],
    "openrouter": [
        "openrouter/free", "poolside/laguna-xs-2.1:free",
        "cohere/north-mini-code:free", "openai/gpt-oss-20b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "openai/gpt-5.6-sol", "openai/gpt-5.4-mini", "openai/o4-mini",
        "openai/gpt-4o-mini", "openai/gpt-4o", "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3.7-sonnet", "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-chat",
    ],
    "opencode": [
        "deepseek-v4-flash-free", "laguna-s-2.1-free", "nemotron-3-ultra-free",
        "ling-3.0-tiny-free", "mimo-v2.5-free", "hy3-free", "big-pickle",
    ],
    "gemini": [
        "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash",
        "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro",
        "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-pro-latest",
    ],
    "custom": [],
}


def provider_label(provider: str) -> str:
    return _PROVIDER_LABELS.get(provider, provider)


def is_local_provider(provider: str) -> bool:
    """True when requests never leave the user's machine."""
    return provider == "ollama"


def _uses_max_completion_tokens(model: str) -> bool:
    """True for OpenAI reasoning models (o-series, gpt-5.x, daybreak) that
    require ``max_completion_tokens`` and reject ``max_tokens``/``temperature``.

    Matches prefixed ids such as OpenRouter's ``openai/gpt-5.6-sol``.
    """
    base = (model or "").strip().rsplit("/", 1)[-1]
    return bool(re.match(r"^(?:o\d|gpt-5|daybreak)", base))


@dataclass
class AIRequest:
    system: str
    user: str
    temperature: float = 0.0
    max_tokens: int = 4096
    json_mode: bool = False


@dataclass
class AIResponse:
    text: Optional[str] = None
    ok: bool = False
    error: str = ""
    retryable: bool = True
    retry_after: Optional[float] = None
    latency_ms: float = 0.0


@dataclass
class ProviderStatus:
    connected: bool
    provider: str
    model: str
    message: str = ""
    latency_ms: float = 0.0


class ProviderError(Exception):
    """Normalized provider failure with a retry hint and HTTP status.

    ``detail`` holds what the provider itself said (best-effort, credential-
    free). The UI prefers it over the generic fallback messages.
    """

    def __init__(self, message: str, retryable: bool = True,
                 status: Optional[int] = None, retry_after: Optional[float] = None,
                 detail: str = ""):
        super().__init__(message)
        self.retryable = retryable
        self.status = status
        self.retry_after = retry_after
        self.detail = detail

    def __str__(self) -> str:
        base = super().__str__()
        if self.detail:
            return f"{base}: {self.detail}"
        return base


class AIProvider:
    """Base class shared by all providers. Subclasses own how the request is
    built and sent; retry/backoff lives in the client so it is uniform."""

    name = "provider"

    def __init__(self, config):
        self.config = config

    # -- endpoints ---------------------------------------------------------

    def _openai_base(self) -> str:
        """Base URL with a trailing /v1 guaranteed (OpenAI-compatible calls)."""
        base = (self.config.base_url or "").rstrip("/")
        if not base:
            return ""
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return base

    # -- transport ---------------------------------------------------------

    def _error_detail(self, response: requests.Response) -> str:
        """Best-effort extraction of what the provider actually said in an
        error response. Credentials are scrubbed before the text is kept."""
        raw = ""
        try:
            data = response.json()
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict):
                    raw = error.get("message") or error.get("code") or ""
                elif isinstance(error, str):
                    raw = error
                if not raw:
                    raw = data.get("message") or data.get("detail") or ""
        except ValueError:
            raw = response.text or ""
        if not isinstance(raw, str):
            raw = str(raw)
        raw = raw.strip()
        if not raw or raw.startswith("<"):
            return ""
        key = self.config.api_key or ""
        if key and key in raw:
            raw = raw.replace(key, "••••")
        return raw[:300]

    def _raise_http(self, response: requests.Response) -> None:
        """Raise a ProviderError for a non-2xx response, keeping whatever the
        provider said in ``detail``."""
        status = response.status_code
        retryable = status in (408, 429) or status >= 500
        retry_after = None
        if status == 429:
            header = response.headers.get("Retry-After")
            if header:
                try:
                    retry_after = float(header)
                except ValueError:
                    retry_after = None
        raise ProviderError(f"HTTP {status}", retryable=retryable,
                            status=status, retry_after=retry_after,
                            detail=self._error_detail(response))

    def _post(self, url: str, payload: Dict, headers: Dict,
              timeout: Optional[float] = None) -> requests.Response:
        try:
            response = requests.post(url, json=payload, headers=headers,
                                     timeout=timeout or self.config.timeout)
        except requests.Timeout:
            raise ProviderError("request timed out", retryable=True)
        except requests.ConnectionError:
            raise ProviderError("connection failed", retryable=True)
        except requests.RequestException as e:
            raise ProviderError(f"request failed: {e}", retryable=True)

        if response.status_code >= 400:
            self._raise_http(response)
        return response

    def _get(self, url: str, headers: Optional[Dict] = None,
             timeout: Optional[float] = None) -> requests.Response:
        try:
            response = requests.get(url, headers=headers or {},
                                    timeout=timeout or self.config.timeout)
        except requests.Timeout:
            raise ProviderError("request timed out", retryable=True)
        except requests.ConnectionError:
            raise ProviderError("connection failed", retryable=True)
        except requests.RequestException as e:
            raise ProviderError(f"request failed: {e}", retryable=True)
        if response.status_code >= 400:
            self._raise_http(response)
        return response

    def _headers(self, extra: Optional[Dict] = None) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        if extra:
            headers.update(extra)
        return headers

    def _chat_payload(self, request: AIRequest) -> Dict:
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
        }
        if _uses_max_completion_tokens(self.config.model):
            payload["max_completion_tokens"] = request.max_tokens
        else:
            payload["temperature"] = request.temperature
            payload["max_tokens"] = request.max_tokens
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.config.ollama_options:
            payload["options"] = self.config.ollama_options
        return payload

    def _parse_chat_response(self, response: requests.Response) -> Optional[str]:
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
            raise ProviderError(f"malformed response: {e}", retryable=False)
        return content.strip() or None

    # -- interface ---------------------------------------------------------

    def chat(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError

    def test_connection(self) -> ProviderStatus:
        raise NotImplementedError

    def list_models(self) -> List[str]:
        return list(KNOWN_MODELS.get(self.name, []))


class OpenAICompatProvider(AIProvider):
    """OpenAI, OpenRouter, and any OpenAI-compatible custom endpoint."""

    name = "openai"

    def chat(self, request: AIRequest) -> AIResponse:
        url = f"{self._openai_base()}/chat/completions"
        start = time.monotonic()
        try:
            response = self._post(url, self._chat_payload(request), self._headers())
            text = self._parse_chat_response(response)
        except ProviderError as e:
            return AIResponse(ok=False, error=str(e), retryable=e.retryable,
                              retry_after=e.retry_after)
        return AIResponse(text=text, ok=text is not None,
                          latency_ms=(time.monotonic() - start) * 1000.0)

    def list_models(self) -> List[str]:
        url = f"{self._openai_base()}/models"
        try:
            response = self._get(url, self._headers())
            data = response.json()
            models = [m["id"] for m in data.get("data", []) if isinstance(m, dict)]
            return [m for m in models if isinstance(m, str)]
        except (ProviderError, ValueError, KeyError, TypeError) as e:
            logger.warning("[AI] %s model discovery failed: %s", self.name, e)
            return super().list_models()

    def test_connection(self) -> ProviderStatus:
        if not self.config.api_key:
            return ProviderStatus(False, self.name, self.config.model,
                                  "API key not set")
        start = time.monotonic()
        try:
            response = self._post(
                f"{self._openai_base()}/chat/completions",
                self._chat_payload(AIRequest("You are a connectivity test.",
                                             "Reply with exactly one word: OK",
                                             max_tokens=512)),
                self._headers(),
            )
            text = self._parse_chat_response(response)
        except ProviderError as e:
            return ProviderStatus(False, self.name, self.config.model,
                                  _friendly_error(self.name, e),
                                  latency_ms=(time.monotonic() - start) * 1000.0)
        latency = (time.monotonic() - start) * 1000.0
        if text is None:
            return ProviderStatus(False, self.name, self.config.model,
                                  "empty response", latency_ms=latency)
        return ProviderStatus(True, self.name, self.config.model,
                              f"Connected — model replied: {text!r}",
                              latency_ms=latency)


class OpenRouterProvider(OpenAICompatProvider):
    name = "openrouter"

    def _headers(self, extra: Optional[Dict] = None) -> Dict[str, str]:
        headers = super()._headers(extra)
        headers["HTTP-Referer"] = "https://github.com/Fadi002/de4py"
        headers["X-Title"] = "de4py"
        return headers


class GeminiProvider(AIProvider):
    """Google Gemini through its native REST API (``:generateContent``).

    Authenticates with the ``x-goog-api-key`` header and uses the
    ``contents``/``parts`` payload shape documented by Google.
    """

    name = "gemini"

    def _root(self) -> str:
        """Native API root. Legacy stored configs may point at the
        OpenAI-compat shim (``/openai``) or the old ``/interactions`` preset;
        both are stripped so existing settings keep working."""
        base = (self.config.base_url or "").rstrip("/")
        for suffix in ("/openai", "/interactions"):
            if base.endswith(suffix):
                base = base[: -len(suffix)].rstrip("/")
        return base or "https://generativelanguage.googleapis.com/v1beta"

    def _generate_url(self, model: str) -> str:
        model = model.strip()
        if model.startswith("models/"):
            model = model[len("models/"):]
        if "/" in model:
            return f"{self._root()}/{model}:generateContent"
        return f"{self._root()}/models/{model}:generateContent"

    def _headers(self, extra: Optional[Dict] = None) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["x-goog-api-key"] = self.config.api_key
        if extra:
            headers.update(extra)
        return headers

    def _payload(self, request: AIRequest) -> Dict:
        payload: Dict = {"contents": [{"parts": [{"text": request.user}]}]}
        if request.system:
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}
        generation_config: Dict = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens,
        }
        if request.json_mode:
            generation_config["responseMimeType"] = "application/json"
        payload["generationConfig"] = generation_config
        return payload

    def _parse_generate_response(self, response: requests.Response) -> Optional[str]:
        try:
            data = response.json()
            candidate = data["candidates"][0]
            parts = candidate.get("content", {}).get("parts") or []
            text = (parts[0].get("text") or "").strip() if parts else ""
            reason = candidate.get("finishReason", "?")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
            raise ProviderError(f"malformed response: {e}", retryable=False)
        if not text:
            # Valid response, but the model produced no text — reasoning models
            # can hit the token budget on "thoughts" before emitting output.
            raise ProviderError(
                f"model returned no text (finishReason: {reason})", retryable=False
            )
        return text

    def chat(self, request: AIRequest) -> AIResponse:
        url = self._generate_url(self.config.model)
        start = time.monotonic()
        try:
            response = self._post(url, self._payload(request), self._headers())
            text = self._parse_generate_response(response)
        except ProviderError as e:
            return AIResponse(ok=False, error=str(e), retryable=e.retryable,
                              retry_after=e.retry_after)
        return AIResponse(text=text, ok=text is not None,
                          latency_ms=(time.monotonic() - start) * 1000.0)

    def list_models(self) -> List[str]:
        url = f"{self._root()}/models?pageSize=1000"
        try:
            data = self._get(url, self._headers()).json()
        except (ProviderError, ValueError) as e:
            logger.warning("[AI] Gemini model discovery failed: %s", e)
            return super().list_models()
        models = []
        for m in data.get("models", []):
            methods = m.get("supportedGenerationMethods") or []
            if "generateContent" in methods:
                models.append(m.get("name", "").replace("models/", ""))
        return [m for m in models if m]

    def test_connection(self) -> ProviderStatus:
        if not self.config.api_key:
            return ProviderStatus(False, self.name, self.config.model,
                                  "API key not set")
        start = time.monotonic()
        try:
            response = self._post(
                self._generate_url(self.config.model),
                self._payload(AIRequest("You are a connectivity test.",
                                        "Reply with exactly one word: OK",
                                        max_tokens=128)),
                self._headers(),
            )
            text = self._parse_generate_response(response)
        except ProviderError as e:
            return ProviderStatus(False, self.name, self.config.model,
                                  _friendly_error(self.name, e),
                                  latency_ms=(time.monotonic() - start) * 1000.0)
        latency = (time.monotonic() - start) * 1000.0
        if text is None:
            return ProviderStatus(False, self.name, self.config.model,
                                  "empty response", latency_ms=latency)
        return ProviderStatus(True, self.name, self.config.model,
                              f"Connected — model replied: {text!r}",
                              latency_ms=latency)


class OllamaProvider(AIProvider):
    name = "ollama"

    def _server(self) -> str:
        base = (self.config.base_url or "").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3].rstrip("/")
        return base or "http://localhost:11434"

    def chat(self, request: AIRequest) -> AIResponse:
        url = f"{self._server()}/v1/chat/completions"
        start = time.monotonic()
        try:
            response = self._post(url, self._chat_payload(request), self._headers())
            text = self._parse_chat_response(response)
        except ProviderError as e:
            return AIResponse(ok=False, error=str(e), retryable=e.retryable,
                              retry_after=e.retry_after)
        return AIResponse(text=text, ok=text is not None,
                          latency_ms=(time.monotonic() - start) * 1000.0)

    def list_models(self) -> List[str]:
        try:
            data = self._get(f"{self._server()}/api/tags", timeout=5).json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except (ProviderError, ValueError, TypeError) as e:
            logger.warning("[AI] Ollama model discovery failed: %s", e)
            return super().list_models()

    def test_connection(self) -> ProviderStatus:
        start = time.monotonic()
        try:
            data = self._get(f"{self._server()}/api/tags", timeout=5).json()
        except ProviderError as e:
            if e.detail:
                message = e.detail
            else:
                message = ("Unable to connect to Ollama. Make sure it is running and the "
                           "server URL is correct.")
            return ProviderStatus(
                False, self.name, self.config.model,
                message,
                latency_ms=(time.monotonic() - start) * 1000.0,
            )
        except ValueError:
            return ProviderStatus(False, self.name, self.config.model,
                                  "Unexpected response from Ollama server",
                                  latency_ms=(time.monotonic() - start) * 1000.0)
        latency = (time.monotonic() - start) * 1000.0
        installed = [m.get("name", "") for m in data.get("models", [])]
        if any(self.config.model in name for name in installed):
            return ProviderStatus(True, self.name, self.config.model,
                                  "Connected", latency_ms=latency)
        available = ", ".join(installed[:5]) if installed else "none"
        return ProviderStatus(True, self.name, self.config.model,
                              f"Server reachable but model '{self.config.model}' is not installed "
                              f"(available: {available})",
                              latency_ms=latency)



_PROVIDER_CLASSES = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatProvider,
    "openrouter": OpenRouterProvider,
    "opencode": OpenAICompatProvider,
    "gemini": GeminiProvider,
    "custom": OpenAICompatProvider,
}


def create_provider(config) -> AIProvider:
    """Instantiate the provider implementation for an AIConfig."""
    cls = _PROVIDER_CLASSES.get(config.provider, OpenAICompatProvider)
    provider = cls(config)
    provider.name = config.provider
    return provider


def _friendly_error(provider: str, error: ProviderError) -> str:
    """User-facing message for a failed provider call.

    Prefers what the provider itself said (``detail``), falling back to a
    translated hint only when the provider gave no usable message. The
    credential is never included."""
    if error.detail:
        return error.detail
    status = error.status
    if status == 400:
        return "The provider rejected the request as invalid (HTTP 400). Check the model name and configuration."
    if status in (401, 403):
        return f"Invalid API key. Check your {provider_label(provider)} API key and try again."
    if status == 404:
        return "Model not found. Check the model name and try again."
    if status == 429:
        return "Rate limited by the provider. Wait a moment and try again."
    if "timed out" in str(error):
        return "The request timed out. Try again."
    if "connection" in str(error):
        return f"Unable to reach {provider_label(provider)}. Check the server URL and your network."
    # Unmapped provider-authored errors (e.g. empty generation with a
    # finishReason) are already user-friendly and credential-free.
    return str(error) or "The provider returned an error. Check the configuration and try again."
