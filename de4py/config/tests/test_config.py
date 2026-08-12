# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from de4py.config.config import Settings


_PROVIDER_ATTRS = (
    "ai_ollama_model", "ai_ollama_base_url",
    "ai_openai_model", "ai_openai_base_url",
    "ai_openrouter_model", "ai_openrouter_base_url",
    "ai_opencode_model", "ai_opencode_base_url",
    "ai_gemini_model", "ai_gemini_base_url",
    "ai_custom_model", "ai_custom_base_url",
)


def _write_config(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _fresh_settings(path):
    """A Settings instance isolated from the user's live config.json: the
    module-level instance loads the real file on construction, so blank the
    per-provider AI fields the tests exercise before pointing at the fixture."""
    s = Settings()
    for attr in _PROVIDER_ATTRS:
        setattr(s, attr, "")
    s._path = path
    return s


def test_save_writes_valid_json_and_leaves_no_temp(tmp_path):
    cfg_path = os.path.join(str(tmp_path), "config.json")
    s = _fresh_settings(cfg_path)
    s.rpc = False
    s.save()
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["rpc"] is False
    assert data["language"] == "en"
    assert not os.path.exists(cfg_path + ".tmp")
