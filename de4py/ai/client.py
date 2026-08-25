# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional

import psutil
import requests

from de4py.ai.providers import (
    AIProvider, AIRequest, KNOWN_MODELS, ProviderStatus,
    create_provider, provider_label,
)

logger = logging.getLogger(__name__)


OLLAMA_BASE = "http://localhost:11434"
_PULL_TIMEOUT = 600
_ENV_PROVIDER = "DE4PY_AI_PROVIDER"
_MAX_ATTEMPTS = 3

#: Presets for the built-in providers. ``env_key`` is the environment variable
#: that supplies the API key for that provider (``None`` when no key is
#: required). ``needs_key`` drives the UI and availability checks.
PROVIDERS = {
    "ollama": {
        "base_url": OLLAMA_BASE,
        "env_key": None,
        "needs_key": False,
        "default_model": "qwen2.5-coder:1.5b",
        "context_window": 4096,
        "models": KNOWN_MODELS["ollama"],
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "needs_key": True,
        "default_model": "gpt-5.4-mini",
        "context_window": 128000,
        "models": KNOWN_MODELS["openai"],
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "needs_key": True,
        "default_model": "openrouter/free",
        "context_window": 128000,
        "models": KNOWN_MODELS["openrouter"],
    },
    "opencode": {
        "base_url": "https://opencode.ai/zen/v1",
        "env_key": "OPENCODE_API_KEY",
        "needs_key": True,
        "default_model": "deepseek-v4-flash-free",
        "context_window": 128000,
        "models": KNOWN_MODELS["opencode"],
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "env_key": "GEMINI_API_KEY",
        "needs_key": True,
        "default_model": "gemini-3.5-flash",
        "context_window": 1000000,
        "models": KNOWN_MODELS["gemini"],
    },
    "custom": {
        "base_url": "",
        "env_key": "AI_API_KEY",
        "needs_key": False,
        "default_model": "",
        "context_window": 128000,
        "models": [],
    },
}


@dataclass
class AIConfig:
    provider: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    context_window: int = 4096
    timeout: int = 180
    ollama_options: Dict[str, object] = field(default_factory=dict)

    @property
    def is_ollama(self) -> bool:
        return self.provider == "ollama"


@lru_cache(maxsize=4)
def _ollama_hw_tuning(default_ctx: int):
    """Tune Ollama context/batch/GPU offload from detected hardware."""
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
    vram_gb = _detect_vram_gb()
    if vram_gb < 2 or ram_gb < 8:
        ctx, batch = 512, 128
    elif vram_gb < 4 or ram_gb < 16:
        ctx, batch = 1024, 256
    else:
        ctx, batch = default_ctx, 512
    return ctx, batch, {"num_ctx": ctx, "num_batch": batch, "num_gpu": 0 if vram_gb < 4 else -1}


def _detect_vram_gb() -> int:
    try:
        if not shutil.which("nvidia-smi"):
            return 0
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            text=True, creationflags=creationflags,
        )
        lines = [l.strip() for l in out.split("\n") if l.strip().isdigit()]
        if lines:
            return round(int(lines[0]) / 1024)
    except Exception:
        pass
    return 0


def _provider_fields(provider: str) -> tuple:
    """Per-provider settings attribute names: (model_key, base_url_key)."""
    return f"ai_{provider}_model", f"ai_{provider}_base_url"


def resolve_ai_config(settings=None, provider: Optional[str] = None) -> Optional[AIConfig]:
    """Build an AIConfig for one provider from settings + environment.

    Priority: env vars > secure credential store > legacy config key >
    provider presets. ``provider`` overrides the active provider so any
    configured provider can be probed (e.g. per-provider Test Connection).
    """
    if settings is None:
        try:
            from de4py.config.config import settings as _settings
            settings = _settings
        except Exception:
            settings = None

    def sget(key: str, default):
        try:
            return getattr(settings, key, default)
        except Exception:
            return default

    provider = (provider or os.getenv(_ENV_PROVIDER) or sget("ai_provider", "ollama")
                or "ollama")
    if provider not in PROVIDERS:
        provider = "custom"

    preset = PROVIDERS[provider]
    env_key = preset["env_key"]
    model_key, url_key = _provider_fields(provider)

    # Credential priority: session → OS store → keyring → encrypted vault →
    # environment variable → not configured. The store is never bypassed by an
    # env var, and nothing is ever persisted to plaintext.
    try:
        from de4py.ai.credentials import get_secret
        api_key = get_secret(provider)
    except Exception:
        api_key = ""
    if not api_key:
        api_key = os.getenv(env_key) if env_key else None
        api_key = api_key or os.getenv("AI_API_KEY", "") or ""

    base_url = (sget(url_key, "") or preset["base_url"])
    model = (sget(model_key, "") or preset["default_model"])
    context_window = preset["context_window"]
    ollama_options: Dict[str, object] = {}

    if provider == "ollama":
        context_window, _, ollama_options = _ollama_hw_tuning(context_window)
        logger.info(
            "[AI] Ollama tuned: context=%s gpu=%s", ollama_options.get("num_ctx"),
            ollama_options.get("num_gpu")
        )

    return AIConfig(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        context_window=context_window,
        ollama_options=ollama_options,
    )


def _backoff_delay(attempt: int, retry_after: Optional[float]) -> float:
    if retry_after:
        return min(float(retry_after), 30.0)
    return min(2 ** attempt + random.uniform(0, 0.5), 15.0)


class AIClient:

    def __init__(self, config: AIConfig):
        self.config = config
        self._provider: AIProvider = create_provider(config)
        self._available: Optional[bool] = None
        self._model_checked = False
        self._model_present = False
        self._model_lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return provider_label(self.config.provider)

    @property
    def available(self) -> bool:
        if self._available is None:
            if self.config.is_ollama:
                self._available = self._ollama_reachable()
            else:
                needs_key = PROVIDERS.get(self.config.provider, {}).get("needs_key", True)
                self._available = bool(
                    self.config.base_url and self.config.model
                    and (not needs_key or self.config.api_key)
                )
        return self._available

    def _ollama_server(self) -> str:
        base = (self.config.base_url or "").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3].rstrip("/")
        return base or OLLAMA_BASE

    def _ollama_reachable(self) -> bool:
        try:
            return requests.get(f"{self._ollama_server()}/api/tags", timeout=3).status_code == 200
        except Exception:
            return False

    def ensure_model(self) -> bool:
        """Make sure the model is usable. For Ollama this checks the local model
        list and pulls a missing model once with a bounded timeout; for cloud
        providers this is a no-op once the key is present."""
        if not self.config.is_ollama:
            return self.available
        if self._model_checked:
            return self._model_present
        with self._model_lock:
            if self._model_checked:
                return self._model_present
            self._model_checked = True
            model_base = self.config.model.split(":")[0]
            server = self._ollama_server()
            try:
                data = requests.get(f"{server}/api/tags", timeout=5).json()
                if any(model_base in m.get("name", "") for m in data.get("models", [])):
                    self._model_present = True
                    return True
            except Exception:
                self._model_present = False
                return False
            logger.info(
                "[AI] Model '%s' missing — pulling (max %ss)", self.config.model, _PULL_TIMEOUT
            )
            try:
                response = requests.post(
                    f"{server}/api/pull",
                    json={"name": self.config.model, "stream": False},
                    timeout=_PULL_TIMEOUT,
                )
                self._model_present = response.status_code == 200
            except Exception as e:
                logger.error("[AI] Model pull failed: %s", e)
                self._model_present = False
            return self._model_present

    def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Single chat completion with retry/backoff. Returns the text or None;
        never raises."""
        request = AIRequest(system, user, temperature, max_tokens, json_mode)
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._provider.chat(request)
            except Exception as e:
                logger.warning("[AI] %s request crashed: %s",
                               self.provider_name, e)
                return None
            if response.ok:
                return response.text
            if not response.retryable or attempt == _MAX_ATTEMPTS - 1:
                logger.warning(
                    "[AI] %s request failed: %s", self.provider_name, response.error
                )
                return None
            delay = _backoff_delay(attempt, response.retry_after)
            logger.warning(
                "[AI] %s request failed (%s) — retrying in %.1fs",
                self.provider_name, response.error, delay,
            )
            time.sleep(delay)
        return None

    def test_connection(self) -> ProviderStatus:
        """Probe the configured provider with the smallest reasonable request."""
        if not self.config.base_url or not self.config.model:
            return ProviderStatus(False, self.config.provider, self.config.model,
                                  "Not configured")
        try:
            return self._provider.test_connection()
        except Exception as e:
            logger.error("[AI] %s connection test failed: %s",
                         self.provider_name, e)
            return ProviderStatus(False, self.config.provider, self.config.model,
                                  "Connection test failed")

    def list_models(self) -> List[str]:
        """Discover available models, falling back to known models."""
        try:
            models = self._provider.list_models()
        except Exception as e:
            logger.warning("[AI] %s model discovery failed: %s",
                           self.provider_name, e)
            models = []
        known = list(KNOWN_MODELS.get(self.config.provider, []))
        return list(dict.fromkeys(models + known))
