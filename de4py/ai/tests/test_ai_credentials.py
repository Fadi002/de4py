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

import pytest

import de4py.ai.credentials as cred


@pytest.fixture
def vault_path(tmp_path):
    path = os.path.join(str(tmp_path), "vault.bin")
    cred.set_vault_path(path)
    yield path
    cred.set_vault_path(None)
    cred.delete_vault()
    cred.lock_vault()
    cred.clear_session_secrets()


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Isolate every test from the machine's real credential store. Tests that
    exercise the native/keyring backends override these defaults explicitly."""
    monkeypatch.setattr(cred, "_native_get", lambda p: None)
    monkeypatch.setattr(cred, "_native_set", lambda p, k: False)
    monkeypatch.setattr(cred, "_native_delete", lambda p: True)
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: False)
    cred.clear_session_secrets()
    cred.lock_vault()
    yield
    cred.clear_session_secrets()
    cred.lock_vault()


# -- backend fallback matrix ------------------------------------------------

def test_native_store_used_when_available(monkeypatch, clean_state):
    monkeypatch.setattr(cred, "_native_get", lambda p: "native-key")
    monkeypatch.setattr(cred, "_native_set", lambda p, k: True)
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: False)
    assert cred.get_secret("openai") == "native-key"
    assert cred.credential_source("openai") == "stored"


def test_keyring_used_when_native_unavailable(monkeypatch, clean_state):
    monkeypatch.setattr(cred, "_native_get", lambda p: None)
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: True)
    monkeypatch.setattr(cred, "_keyring_get", lambda p: "ring-key")
    assert cred.get_secret("openai") == "ring-key"
    assert cred.credential_source("openai") == "stored"


def test_vault_used_when_no_os_backend(monkeypatch, clean_state, vault_path):
    monkeypatch.setattr(cred, "_native_get", lambda p: None)
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: False)
    assert cred.create_vault("vault-pass")
    assert cred.set_secret("gemini", "vault-key", mode="vault")
    assert cred.get_secret("gemini") == "vault-key"
    assert cred.credential_source("gemini") == "vault"


def test_nothing_available_means_not_configured(monkeypatch, clean_state, vault_path):
    monkeypatch.setattr(cred, "_native_get", lambda p: None)
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: False)
    monkeypatch.setattr(cred, "_native_set", lambda p, k: False)
    assert cred.get_secret("openai") == ""
    assert cred.set_secret("openai", "sk-xxx") is False  # no plaintext write
    assert cred.credential_source("openai") == "none"


def test_keychain_failure_never_falls_back_to_plaintext(monkeypatch, clean_state, vault_path):
    monkeypatch.setattr(cred, "_native_get", lambda p: None)
    monkeypatch.setattr(cred, "_native_set", lambda p, k: False)
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: False)
    assert cred.set_secret("openai", "sk-secret", mode="native") is False
    # nothing was persisted anywhere
    assert cred.get_secret("openai") == ""
    for root, _dirs, files in os.walk(os.path.dirname(cred._vault_path())):
        for name in files:
            if name.endswith((".json", ".txt")):
                with open(os.path.join(root, name), "r", encoding="utf-8") as f:
                    assert "sk-secret" not in f.read()


def test_env_credential_is_never_persisted(monkeypatch, clean_state, vault_path, tmp_path):
    monkeypatch.setattr(cred, "_native_get", lambda p: None)
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: False)
    monkeypatch.setattr(os, "environ", {"GEMINI_API_KEY": "AIza-env-only"}, raising=False)
    assert cred.credential_source("gemini", env_key="GEMINI_API_KEY") == "env"
    assert cred.get_secret("gemini") == ""
    # config dir has no trace of the key
    for root, _dirs, files in os.walk(str(tmp_path)):
        for name in files:
            with open(os.path.join(root, name), "rb") as f:
                assert b"AIza-env-only" not in f.read()


# -- session credentials ----------------------------------------------------

def test_session_credential_priority(monkeypatch, clean_state, vault_path):
    monkeypatch.setattr(cred, "_native_get", lambda p: "native-key")
    cred.set_session_secret("openai", "session-key")
    assert cred.get_secret("openai") == "session-key"
    assert cred.credential_source("openai") == "session"
    cred.clear_session_secrets()
    assert cred.get_secret("openai") == "native-key"


# -- vault security ---------------------------------------------------------

def test_vault_wrong_password_does_not_destroy_vault(clean_state, vault_path):
    assert cred.create_vault("right-pass")
    assert cred.set_secret("gemini", "secret", mode="vault")
    with open(vault_path, "rb") as f:
        before = f.read()
    cred.lock_vault()
    assert cred.unlock_vault("wrong-pass") is False
    assert cred.get_secret("gemini") == ""
    with open(vault_path, "rb") as f:
        assert f.read() == before  # untouched
    assert cred.unlock_vault("right-pass") is True
    assert cred.get_secret("gemini") == "secret"


def test_malformed_vault_cannot_crash(clean_state, vault_path):
    with open(vault_path, "wb") as f:
        f.write(b"garbage-not-a-vault")
    assert cred.unlock_vault("any") is False
    assert cred.get_secret("gemini") == ""
    assert cred.set_secret("gemini", "k", mode="vault") is False


def test_missing_vault_does_not_crash(clean_state, vault_path):
    assert cred.unlock_vault("any") is False
    assert cred.get_secret("gemini") == ""
    assert cred.delete_vault() is True  # idempotent: nothing to delete


def test_vault_data_is_encrypted_at_rest(clean_state, vault_path):
    assert cred.create_vault("pass")
    assert cred.set_secret("openai", "sk-plaintext-never", mode="vault")
    with open(vault_path, "rb") as f:
        raw = f.read()
    assert b"sk-plaintext-never" not in raw
    assert not raw.startswith(b"{")


def test_vault_password_never_stored_alongside(clean_state, vault_path):
    assert cred.create_vault("ultra-secret-passphrase")
    with open(vault_path, "rb") as f:
        raw = f.read()
    assert b"ultra-secret-passphrase" not in raw


def test_locked_vault_returns_nothing(clean_state, vault_path):
    assert cred.create_vault("pass")
    assert cred.set_secret("gemini", "k", mode="vault")
    cred.lock_vault()
    assert cred.credential_source("gemini") == "vault_locked"
    assert cred.get_secret("gemini") == ""


def test_vault_locked_state_disappears_after_unlock(clean_state, vault_path):
    assert cred.create_vault("pass")
    assert cred.set_secret("gemini", "k", mode="vault")
    cred.lock_vault()
    assert cred.credential_source("gemini") == "vault_locked"
    assert cred.unlock_vault("pass") is True
    assert cred.credential_source("gemini") == "vault"


def test_create_vault_refuses_when_vault_exists(clean_state, vault_path):
    assert cred.create_vault("first-pass")
    assert cred.set_secret("gemini", "keep-me", mode="vault")
    # a second create must not silently destroy stored credentials
    assert cred.create_vault("second-pass") is False
    assert cred.get_secret("gemini") == "keep-me"


def test_delete_secret_false_when_store_delete_fails(monkeypatch, clean_state, vault_path):
    monkeypatch.setattr(cred, "_native_delete", lambda p: False)
    monkeypatch.setattr(cred, "_native_get", lambda p: "still-there")
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: False)
    assert cred.delete_secret("openai") is False
    assert cred.get_secret("openai") == "still-there"


def test_delete_secret_true_when_gone(monkeypatch, clean_state, vault_path):
    monkeypatch.setattr(cred, "_native_delete", lambda p: True)
    monkeypatch.setattr(cred, "_native_get", lambda p: None)
    monkeypatch.setattr(cred, "keyring_backend_available", lambda: False)
    assert cred.delete_secret("openai") is True


# -- masking ----------------------------------------------------------------

def test_mask_key():
    assert cred.mask_key("") == ""
    assert cred.mask_key("short") == "••••"
    masked = cred.mask_key("sk-abcdefgh12345678")
    assert "abcdefgh12345678" not in masked
    assert masked == "sk-a••••5678"
