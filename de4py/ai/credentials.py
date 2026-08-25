# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Provider credential storage with a strict, never-plaintext fallback chain.

Resolution priority for a provider's API key:

    1. Explicit session credential (in-memory, this process only)
    2. Native OS credential store (Windows Credential Manager, macOS Keychain,
       Linux Secret Service via secret-tool)
    3. Cross-platform ``keyring`` backend, when installed
    4. User-created encrypted vault (AES-256-GCM, scrypt key derivation),
       unlocked for this session
    5. Environment variable (handled by the caller — never persisted)
    6. Not configured

There is deliberately NO plaintext fallback. If nothing above can store the
key, the credential simply is not persisted: the provider stays usable with a
session-only credential or an environment variable. Keys are never logged and
never written into config.json.
"""

import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from ctypes import wintypes
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SERVICE = "de4py/ai"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2

_LOCK = threading.Lock()
_SESSION: Dict[str, str] = {}
_VAULT_PASSWORD: Optional[str] = None
_VAULT_FILENAME = ".ai_vault"
_VAULT_PATH_OVERRIDE: Optional[str] = None

_VALID_MODES = ("auto", "native", "vault", "session")


# ---------------------------------------------------------------------------
# Native OS credential stores
# ---------------------------------------------------------------------------

class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.c_void_p),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_advapi32 = None
try:
    if sys.platform == "win32":
        _advapi32 = ctypes.windll.advapi32
        _advapi32.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIAL), wintypes.DWORD]
        _advapi32.CredWriteW.restype = wintypes.BOOL
        _advapi32.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                        ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))]
        _advapi32.CredReadW.restype = wintypes.BOOL
        _advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        _advapi32.CredDeleteW.restype = wintypes.BOOL
        _advapi32.CredFree.argtypes = [ctypes.c_void_p]
        _advapi32.CredFree.restype = None
except Exception:
    _advapi32 = None


def _target_name(provider: str) -> str:
    return f"{_SERVICE}/{provider}"


def _run(cmd: List[str]) -> Optional[str]:
    """Run a keychain helper and return stdout on success, else None."""
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                              creationflags=creationflags)
        if proc.returncode == 0:
            return proc.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _native_get(provider: str) -> Optional[str]:
    if _advapi32 is not None:
        try:
            cred = ctypes.POINTER(_CREDENTIAL)()
            ok = _advapi32.CredReadW(_target_name(provider), _CRED_TYPE_GENERIC, 0,
                                     ctypes.byref(cred))
            if ok and cred:
                try:
                    size = int(cred.contents.CredentialBlobSize)
                    if size and cred.contents.CredentialBlob:
                        buf = ctypes.string_at(cred.contents.CredentialBlob, size)
                        return buf.decode("utf-8", errors="replace")
                finally:
                    _advapi32.CredFree(cred)
        except Exception as e:
            logger.warning("[AI] Credential Manager read failed: %s", e)
        return None
    if sys.platform == "darwin" and shutil.which("security"):
        out = _run(["security", "find-generic-password", "-a", "de4py",
                    "-s", _target_name(provider), "-w"])
        return out.strip() if out is not None else None
    if sys.platform.startswith("linux") and shutil.which("secret-tool"):
        out = _run(["secret-tool", "lookup", "service", _target_name(provider)])
        return out.strip() if out is not None else None
    return None


def _native_set(provider: str, key: str) -> bool:
    if _advapi32 is not None:
        try:
            blob = key.encode("utf-8")
            cred = _CREDENTIAL()
            cred.Type = _CRED_TYPE_GENERIC
            cred.TargetName = _target_name(provider)
            cred.CredentialBlobSize = len(blob)
            cred.CredentialBlob = ctypes.cast(
                ctypes.create_string_buffer(blob), ctypes.c_void_p)
            cred.Persist = _CRED_PERSIST_LOCAL_MACHINE
            return bool(_advapi32.CredWriteW(ctypes.byref(cred), 0))
        except Exception as e:
            logger.warning("[AI] Credential Manager write failed: %s", e)
        return False
    if sys.platform == "darwin" and shutil.which("security"):
        return _run(["security", "add-generic-password", "-U", "-a", "de4py",
                     "-s", _target_name(provider), "-w", key]) is not None
    if sys.platform.startswith("linux") and shutil.which("secret-tool"):
        return _run(["secret-tool", "store", "--label=de4py", "service",
                     _target_name(provider), "key", key]) is not None
    return False


def _native_delete(provider: str) -> bool:
    if _advapi32 is not None:
        try:
            return bool(_advapi32.CredDeleteW(_target_name(provider),
                                              _CRED_TYPE_GENERIC, 0))
        except Exception:
            return False
    if sys.platform == "darwin" and shutil.which("security"):
        _run(["security", "delete-generic-password", "-a", "de4py",
              "-s", _target_name(provider)])
        return True
    if sys.platform.startswith("linux") and shutil.which("secret-tool"):
        _run(["secret-tool", "clear", "service", _target_name(provider)])
        return True
    return False


def native_backend_available() -> bool:
    """True when a native OS credential store can be reached."""
    if _advapi32 is not None:
        return True
    if sys.platform == "darwin":
        return shutil.which("security") is not None
    if sys.platform.startswith("linux"):
        return shutil.which("secret-tool") is not None
    return False


# ---------------------------------------------------------------------------
# Cross-platform keyring backend (optional dependency)
# ---------------------------------------------------------------------------

_keyring_probe: Optional[bool] = None


def keyring_backend_available() -> bool:
    global _keyring_probe
    if _keyring_probe is None:
        try:
            import keyring
            keyring.get_keyring()
            _keyring_probe = True
        except Exception:
            _keyring_probe = False
    return _keyring_probe


def _keyring_get(provider: str) -> Optional[str]:
    try:
        import keyring
        value = keyring.get_password(_SERVICE, provider)
        return value if value else None
    except Exception as e:
        logger.warning("[AI] keyring read failed: %s", e)
        return None


def _keyring_set(provider: str, key: str) -> bool:
    try:
        import keyring
        keyring.set_password(_SERVICE, provider, key)
        return True
    except Exception as e:
        logger.warning("[AI] keyring write failed: %s", e)
        return False


def _keyring_delete(provider: str) -> bool:
    try:
        import keyring
        keyring.delete_password(_SERVICE, provider)
    except Exception:
        pass
    return True


def persistent_backend_available() -> bool:
    """Any secure persistent backend (native or keyring)."""
    return native_backend_available() or keyring_backend_available()


# ---------------------------------------------------------------------------
# Encrypted local vault (explicit user opt-in, AES-256-GCM + scrypt)
# ---------------------------------------------------------------------------

_MAGIC = b"DE4PYVLT"
_VERSION = 1
_SALT_LEN = 16
_NONCE_LEN = 12
_TAG_LEN = 16
_HEADER_LEN = len(_MAGIC) + 1 + _SALT_LEN + _NONCE_LEN + _TAG_LEN
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1


def set_vault_path(path: str) -> None:
    """Override the vault file location (used by tests)."""
    global _VAULT_PATH_OVERRIDE
    _VAULT_PATH_OVERRIDE = path


def _vault_path() -> str:
    if _VAULT_PATH_OVERRIDE:
        return _VAULT_PATH_OVERRIDE
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "config", _VAULT_FILENAME)


def _derive_key(password: str, salt: bytes) -> bytes:
    from Crypto.Protocol.KDF import scrypt
    return scrypt(password.encode("utf-8"), salt, 32,
                  N=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)


def vault_enabled() -> bool:
    return os.path.exists(_vault_path())


def vault_unlocked() -> bool:
    return vault_enabled() and _VAULT_PASSWORD is not None


def _vault_ciphertext(data: Dict[str, str], password: str) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    salt = get_random_bytes(_SALT_LEN)
    nonce = get_random_bytes(_NONCE_LEN)
    key = _derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(
        json.dumps(data, separators=(",", ":")).encode("utf-8"))
    return _MAGIC + bytes([_VERSION]) + salt + nonce + tag + ct


def _vault_decrypt(password: str) -> Optional[Dict[str, str]]:
    try:
        with open(_vault_path(), "rb") as f:
            raw = f.read()
        if len(raw) < _HEADER_LEN or not raw.startswith(_MAGIC):
            logger.warning("[AI] Vault file is malformed or truncated")
            return None
        salt = raw[len(_MAGIC) + 1: len(_MAGIC) + 1 + _SALT_LEN]
        nonce = raw[len(_MAGIC) + 1 + _SALT_LEN: len(_MAGIC) + 1 + _SALT_LEN + _NONCE_LEN]
        tag = raw[_HEADER_LEN - _TAG_LEN: _HEADER_LEN]
        ct = raw[_HEADER_LEN:]
        from Crypto.Cipher import AES
        key = _derive_key(password, salt)
        plaintext = AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)
        data = json.loads(plaintext.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("[AI] Vault could not be unlocked: %s", e)
        return None


def create_vault(password: str) -> bool:
    """Create a new encrypted vault. Refuses when a vault already exists — an
    existing vault may hold credentials and must never be silently destroyed.
    The password is kept in memory for this session only and never stored."""
    if not password or vault_enabled():
        return False
    try:
        with open(_vault_path(), "wb") as f:
            f.write(_vault_ciphertext({}, password))
    except OSError as e:
        logger.error("[AI] Vault creation failed: %s", e)
        return False
    global _VAULT_PASSWORD
    _VAULT_PASSWORD = password
    return True


def unlock_vault(password: str) -> bool:
    if not vault_enabled():
        return False
    data = _vault_decrypt(password)
    if data is None:
        return False
    global _VAULT_PASSWORD
    _VAULT_PASSWORD = password
    return True


def lock_vault() -> None:
    global _VAULT_PASSWORD
    _VAULT_PASSWORD = None


def delete_vault() -> bool:
    global _VAULT_PASSWORD
    _VAULT_PASSWORD = None
    try:
        if os.path.exists(_vault_path()):
            os.remove(_vault_path())
        return True
    except OSError as e:
        logger.error("[AI] Vault deletion failed: %s", e)
        return False


def _vault_get(provider: str) -> Optional[str]:
    if not vault_unlocked():
        return None
    data = _vault_decrypt(_VAULT_PASSWORD)
    if data is None:
        return None
    return data.get(provider)


def _vault_set(provider: str, key: str) -> bool:
    if not vault_unlocked():
        return False
    data = _vault_decrypt(_VAULT_PASSWORD)
    if data is None:
        return False
    data[provider] = key
    try:
        with open(_vault_path(), "wb") as f:
            f.write(_vault_ciphertext(data, _VAULT_PASSWORD))
        return True
    except OSError as e:
        logger.error("[AI] Vault write failed: %s", e)
        return False


def _vault_delete(provider: str) -> bool:
    if not vault_unlocked():
        return False
    data = _vault_decrypt(_VAULT_PASSWORD)
    if data is None:
        return False
    if provider not in data:
        return True
    del data[provider]
    try:
        with open(_vault_path(), "wb") as f:
            f.write(_vault_ciphertext(data, _VAULT_PASSWORD))
        return True
    except OSError as e:
        logger.error("[AI] Vault write failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Public credential API
# ---------------------------------------------------------------------------

def get_secret(provider: str) -> str:
    """Resolve the stored credential for a provider (session → OS store →
    keyring → vault). Environment variables are intentionally NOT part of
    this lookup; the caller resolves them as a lower-priority fallback."""
    with _LOCK:
        if provider in _SESSION:
            return _SESSION[provider]
        value = _native_get(provider)
        if value:
            return value
        if keyring_backend_available():
            value = _keyring_get(provider)
            if value:
                return value
        value = _vault_get(provider)
        return value or ""


def set_secret(provider: str, key: str, mode: str = "auto") -> bool:
    """Persist a credential. ``mode`` is one of:

    - ``auto``: best available persistent backend (OS store, keyring, vault)
    - ``native``: OS store / keyring only (no vault fallback)
    - ``vault``: encrypted vault only
    - ``session``: memory only, never persisted

    Returns False when the requested persistence was not possible — the caller
    must then decide (vault prompt / session-only), never plaintext.
    """
    if not key:
        return delete_secret(provider)
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid credential mode: {mode}")
    with _LOCK:
        if mode == "session":
            _SESSION[provider] = key
            return True
        if mode in ("auto", "native"):
            if _native_set(provider, key):
                return True
            if keyring_backend_available() and _keyring_set(provider, key):
                return True
            if mode == "native":
                return False
        if mode in ("auto", "vault") and _vault_set(provider, key):
            return True
        return False


def set_session_secret(provider: str, key: str) -> None:
    with _LOCK:
        if key:
            _SESSION[provider] = key
        else:
            _SESSION.pop(provider, None)


def get_session_secret(provider: str) -> str:
    with _LOCK:
        return _SESSION.get(provider, "")


def clear_session_secrets() -> None:
    with _LOCK:
        _SESSION.clear()


def delete_secret(provider: str) -> bool:
    """Remove a credential from every backend that holds it. Returns True only
    once the credential is actually gone everywhere."""
    with _LOCK:
        _SESSION.pop(provider, None)
        _native_delete(provider)
        if keyring_backend_available():
            _keyring_delete(provider)
        _vault_delete(provider)
    return get_secret(provider) == ""


def credential_source(provider: str, env_key: Optional[str] = None) -> str:
    """Where the credential for a provider currently comes from. Returns one
    of ``session`` / ``stored`` / ``vault`` / ``env`` / ``vault_locked`` /
    ``none`` — never the credential itself."""
    with _LOCK:
        if provider in _SESSION:
            return "session"
        if _native_get(provider) or (keyring_backend_available()
                                     and bool(_keyring_get(provider))):
            return "stored"
        if _vault_get(provider):
            return "vault"
    if env_key and os.getenv(env_key):
        return "env"
    if vault_enabled() and not vault_unlocked():
        return "vault_locked"
    return "none"


def storage_summary() -> str:
    """Human-readable status of the available credential backends."""
    parts = []
    if _advapi32 is not None:
        parts.append("Windows Credential Manager")
    elif sys.platform == "darwin":
        parts.append("macOS Keychain" if shutil.which("security") else "")
    elif sys.platform.startswith("linux"):
        parts.append("Secret Service" if shutil.which("secret-tool") else "")
    if keyring_backend_available():
        parts.append("keyring")
    if vault_enabled():
        parts.append("encrypted vault")
    return ", ".join(p for p in parts if p) or "no secure storage"


def mask_key(key: str) -> str:
    """Human-friendly masked form for display, e.g. ``sk-••••abcd``."""
    if not key:
        return ""
    if len(key) <= 8:
        return "••••"
    return f"{key[:4]}••••{key[-4:]}"
