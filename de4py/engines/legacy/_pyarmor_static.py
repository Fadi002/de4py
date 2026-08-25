# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

#!/usr/bin/env python3
"""
pyarmor_static.py -- offline PyArmor 9.2.6 (trial) decryptor, Tested with: Python 3.10-3.14.

Reads an obfuscated .py file and its pyarmor_runtime.pyd, derives the AES key,
decrypts the embedded code, and prints a full disassembly. Never runs the
target -- reads and decrypts only. What looks like a custom VM is just
AES-encrypted CPython bytecode.

Needs pycryptodome.
"""

from __future__ import annotations

import argparse
import ast
import dis
import hashlib
import re
import struct
import subprocess
import sys
import types
from pathlib import Path

try:
    from Crypto.Cipher import AES
except ImportError:
    sys.exit(f"pyarmor_static.py needs pycryptodome under this interpreter "
             f"(Python {sys.version_info.major}.{sys.version_info.minor}): "
             f"py -{sys.version_info.major}.{sys.version_info.minor} -m pip install pycryptodome")


# Key derivation: every input is found by scanning for b"pyarmor-vax-" (the salt
# anchor) and reading at fixed offsets relative to it, so no per-build addresses are
# hardcoded. MD5(salt + RSA pubkey DER + license descriptor hash + unmasked 270 bytes)
# is the AES-128 key.

_SALT_ANCHOR = b"pyarmor-vax-"
_SALT_LEN = 20
_HEADER_BEFORE_SALT = 0x0C
_RAW270_DELTA_FROM_SALT = 16660
_RAW270_LEN = 270
_PAD_LEN = 16
_PAD_SEARCH_WINDOW = 16384


class DecryptError(ValueError):
    pass


def _require_len(chunk: bytes, expected: int, what: str) -> bytes:
    """A slice that came up short means the offset ran past EOF -- the runtime
    isn't shaped like a PyArmor 9.2.6-trial build (wrong version, or not PyArmor
    at all). Raising here beats a struct.error a few lines further down."""
    if len(chunk) != expected:
        raise DecryptError(
            f"key derivation failed: {what} runs past the end of the runtime file "
            f"(wanted {expected} bytes, got {len(chunk)}) -- doesn't look like a "
            f"PyArmor 9.2.6-trial runtime.pyd")
    return chunk


def derive_key(runtime_pyd_path: Path) -> bytes:
    data = runtime_pyd_path.read_bytes()

    salt_off = data.find(_SALT_ANCHOR)
    if salt_off == -1:
        raise DecryptError(
            f"key derivation failed: salt anchor {_SALT_ANCHOR!r} not found in "
            f"{runtime_pyd_path.name} -- not a PyArmor 9.2.6-trial runtime, or the "
            f"license-id marker differs from what this tool expects")
    salt = _require_len(data[salt_off:salt_off + _SALT_LEN], _SALT_LEN, "salt")

    header_off = salt_off - _HEADER_BEFORE_SALT
    if header_off < 0:
        raise DecryptError(
            "key derivation failed: salt anchor sits too close to the start of the "
            "runtime file for a valid header -- doesn't look like a PyArmor "
            "9.2.6-trial runtime.pyd")
    header = _require_len(data[header_off:header_off + 0x40], 0x40, "header")
    off_pubkey, len_pubkey, off_license_desc = struct.unpack_from("<III", header, 0x30)
    fields_base = header_off + 0x40

    pubkey_der = _require_len(
        data[fields_base + off_pubkey: fields_base + off_pubkey + len_pubkey],
        len_pubkey, "RSA pubkey field")

    license_desc_header = _require_len(
        data[fields_base + off_license_desc: fields_base + off_license_desc + 8],
        8, "license descriptor header")
    desc_hash_len = struct.unpack_from("<I", license_desc_header, 4)[0]
    license_desc_hash = _require_len(
        data[fields_base + off_license_desc + 32:
             fields_base + off_license_desc + 32 + desc_hash_len],
        desc_hash_len, "license descriptor hash")

    raw270_off = salt_off + _RAW270_DELTA_FROM_SALT
    raw270 = _require_len(data[raw270_off:raw270_off + _RAW270_LEN], _RAW270_LEN, "masked 270-byte region")

    # The pad is a run of 16 identical bytes. Zero is excluded on purpose: plain
    # zero-padding for alignment shows up first in the file and looks the same as a
    # real pad, so scanning for it too finds a false match and derives the wrong key.
    pad = None
    window = data[raw270_off:raw270_off + _PAD_SEARCH_WINDOW]
    for i in range(len(window) - _PAD_LEN):
        b0 = window[i]
        if b0 != 0 and all(window[i + j] == b0 for j in range(_PAD_LEN)):
            pad = window[i:i + _PAD_LEN]
            break
    if pad is None:
        raise DecryptError(
            f"key derivation failed: no {_PAD_LEN}-identical-byte XOR pad found within "
            f"{_PAD_SEARCH_WINDOW} bytes after the masked region -- structural layout "
            f"assumption doesn't hold for this .pyd")

    deob270 = bytes(b ^ pad[i % _PAD_LEN] for i, b in enumerate(raw270))
    return hashlib.md5(salt + pubkey_der + license_desc_hash + deob270).digest()


# Blob header layout (same on every Python version):
#   [0:8]    b'PY000000'   magic       [9:11]  target Python (major, minor)
#   [20:24]  type tag: 8 = use this header; 9 = decrypt an outer region first (untested)
#   [28:32]  ciphertext offset (relative to header)   [32:36] ciphertext length
#   [36:52]  12-byte GCM IV -- PyArmor's own code overwrites [40:44] with [36:40]
#            right before reading it; kept here to match
#   [37]     low 3 bits: whether a decrypt happens
#
# No GCM tag verification runs here; the two echo checks below stand in for the
# missing tag.

def _gcm_region_decrypt(buf: bytearray, key: bytes, hdr_off: int, region_off: int, region_len: int) -> None:
    iv = bytes(buf[hdr_off + 36:hdr_off + 40]) + bytes(buf[hdr_off + 44:hdr_off + 52])
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    pt = cipher.decrypt(bytes(buf[region_off:region_off + region_len]))
    buf[region_off:region_off + region_len] = pt


def detect_target_version(blob: bytes) -> tuple[int, int]:
    """Target Python version, read straight from the blob header."""
    if len(blob) < 11 or blob[0:8] != b"PY000000":
        raise DecryptError(f"not a recognized PyArmor blob (bad magic {blob[0:8]!r})")
    major, minor = blob[9], blob[10]
    if major not in (2, 3) or not (0 <= minor < 30):
        raise DecryptError(
            f"blob reports an implausible target Python version ({major}.{minor}) -- "
            f"this likely isn't a supported PyArmor 9.2.6-trial blob")
    return major, minor


def decrypt_blob(blob: bytes, key: bytes) -> bytes:
    """Decrypt one code blob, return the raw marshal bytes."""
    buf = bytearray(blob)
    tag = struct.unpack_from("<I", buf, 20)[0]

    if tag == 8:
        hdr_off = 0
    elif tag == 9:
        # Untested: decrypt this region first, then re-read the header from
        # wherever THAT says it starts.
        predecrypt_off = struct.unpack_from("<I", buf, 28)[0]
        predecrypt_len = struct.unpack_from("<I", buf, 32)[0]
        _gcm_region_decrypt(buf, key, hdr_off=0, region_off=predecrypt_off, region_len=predecrypt_len)
        hdr_off = struct.unpack_from("<I", buf, 56)[0]
    else:
        raise DecryptError(f"unrecognized blob type tag {tag} at offset 20 (expected 8 or 9)")

    decrypt_flags = buf[hdr_off + 37]
    ciphertext_off = hdr_off + struct.unpack_from("<I", buf, hdr_off + 28)[0]
    ciphertext_len = struct.unpack_from("<I", buf, hdr_off + 32)[0]

    if decrypt_flags & 7:
        _gcm_region_decrypt(buf, key, hdr_off=hdr_off, region_off=ciphertext_off, region_len=ciphertext_len)

    # Stand-in for the missing tag: the decrypted bytes must echo the IV dword
    # and a fixed type marker (8).
    iv_echo = struct.unpack_from("<I", buf, ciphertext_off + 12)[0]
    iv_echo_expect = struct.unpack_from("<I", buf, hdr_off + 36)[0]
    type_echo = struct.unpack_from("<I", buf, ciphertext_off + 16)[0]
    if iv_echo != iv_echo_expect or type_echo != 8:
        raise DecryptError(
            "post-decrypt integrity check failed (wrong key, wrong offsets, or not a "
            "PyArmor 9.2.6-trial blob) -- refusing to marshal-load garbage"
        )

    marshal_off = (ciphertext_off
                    + struct.unpack_from("<I", buf, ciphertext_off + 4)[0]
                    + struct.unpack_from("<I", buf, ciphertext_off + 0)[0])
    marshal_len = struct.unpack_from("<I", buf, ciphertext_off + 8)[0]
    return bytes(buf[marshal_off:marshal_off + marshal_len])


def extract_blobs(script_path: Path) -> list[bytes]:
    src = script_path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(script_path))
    blobs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "__pyarmor__":
            if not node.args:
                continue
            try:
                blobs.append(ast.literal_eval(node.args[-1]))
            except ValueError:
                continue
    return blobs


def find_runtime_pyd(script_path: Path) -> Path | None:
    for child in script_path.parent.iterdir():
        if child.is_dir() and child.name.startswith("pyarmor_runtime"):
            candidate = child / "pyarmor_runtime.pyd"
            if candidate.exists():
                return candidate
    return None


# marshal/CodeType layout differs by Python version -- rather than reimplementing
# every version's rules, just relaunch under a `py -X.Y` that matches the blob.

def _reexec_if_needed(target_version: tuple[int, int], argv: list[str]) -> None:
    if sys.version_info[:2] == target_version:
        return
    maj, minr = target_version
    script_path = str(Path(__file__).resolve())
    attempts = [
        ["py", f"-{maj}.{minr}", script_path, *argv],
        [f"python{maj}.{minr}", script_path, *argv],
        [f"python{maj}{minr}", script_path, *argv],
    ]
    for cmd in attempts:
        try:
            proc = subprocess.run(cmd)
        except (FileNotFoundError, OSError):
            continue
        sys.exit(proc.returncode)
    sys.exit(
        f"error: this blob targets Python {maj}.{minr}, but no matching interpreter was "
        f"found on PATH (tried 'py -{maj}.{minr}', 'python{maj}.{minr}', 'python{maj}{minr}'). "
        f"Install Python {maj}.{minr} (or make it reachable via the 'py' launcher) and retry."
    )


# marshal changed shape once, in Python 3.11 -- code objects gained localsplusnames
# (merging varnames/freevars/cellvars, with a kind byte marking which) and qualname.
# The blob's own version picks which layout to read.
#
# PyArmor also adds its own marshal type bytes (0x01-0x1f) for three live native
# PyCFunction objects it builds at import time (the C_ASSERT/C_ENTER/C_LEAVE
# handlers). No static reader can produce the object itself -- it only exists inside
# the loaded runtime -- so it's read as an opaque blob (Placeholder) and dropped;
# the neighboring __pyarmor_assert_/enter_/exit_ marker string stands in for it.

FLAG_REF = 0x80
_MODERN_KIND_FREE = 0x80
_MODERN_KIND_CELL = 0x40


class Placeholder:
    """One of PyArmor's own marshal type bytes (0x01-0x1f) -- a live native object that cannot be reconstructed statically."""

    def __init__(self, type_id: int, data: bytes):
        self.type_id = type_id
        self.data = data

    def __repr__(self):
        return f"<pyarmor-placeholder type=0x{self.type_id:02x} data={self.data.hex()}>"


class RawCode:
    """One marshaled code object's fields (superset of legacy/modern layouts).
    partial_error records why parsing stopped, without losing fields already read."""

    __slots__ = ("argcount", "posonlyargcount", "kwonlyargcount", "nlocals", "stacksize",
                 "flags", "code", "consts", "names", "varnames", "freevars", "cellvars",
                 "filename", "name", "qualname", "firstlineno", "lnotab", "linetable",
                 "exceptiontable", "partial_error")

    def __init__(self):
        for slot in self.__slots__:
            setattr(self, slot, None)


def _split_localsplus(names, kinds) -> tuple[tuple, tuple, tuple]:
    """Split a 3.11+ merged localsplusnames array into (varnames, cellvars, freevars)
    using the kind byte bitmask: 0x80 = free var, 0x40 = cell var, else a plain local."""
    if not isinstance(names, tuple) or not isinstance(kinds, (bytes, bytearray)) or len(names) != len(kinds):
        return (names if isinstance(names, tuple) else ()), (), ()
    varnames, cellvars, freevars = [], [], []
    for name, kind in zip(names, kinds):
        if kind & _MODERN_KIND_FREE:
            freevars.append(name)
        elif kind & _MODERN_KIND_CELL:
            cellvars.append(name)
        else:
            varnames.append(name)
    return tuple(varnames), tuple(cellvars), tuple(freevars)


# PyArmor sometimes serializes a shorter consts tuple than the code object's true
# size -- extra objects (a spilled nested-def pair, closing markers) follow right
# after with no header of their own. Not a reproduction of PyArmor's real loader
# (which would reject this stream too) -- this leans on the file's own
# self-consistency.
_MAX_CONSTS_TAIL_EXTEND = 64


class MarshalReader:
    def __init__(self, data: bytes, version: tuple[int, int]):
        self.data = data
        self.version = version
        self.pos = 0
        self.refs: list = []
        self.all_codes: list = []  # populated as each object finishes -- survives a later parse failure

    def _rd(self, n: int) -> bytes:
        b = self.data[self.pos:self.pos + n]
        if len(b) != n:
            raise DecryptError(f"marshal stream truncated at offset {self.pos} (wanted {n} bytes, got {len(b)})")
        self.pos += n
        return b

    def _byte(self) -> int:
        return self._rd(1)[0]

    def _long(self) -> int:
        return struct.unpack("<i", self._rd(4))[0]

    def _read_consts_then_names(self) -> tuple:
        """Reads consts, then keeps folding in objects until one looks like `names`
        (a tuple of raw strings) -- names comes back already-read, never re-parsed.
        A bare tuple check isn't enough: consts can hold its own tuple values (e.g.
        default args), and a plain string tuple used as data can look like a short
        names too -- so once something's been folded in, the candidate must overlap
        with a def name already seen in consts (STORE_NAME follows MAKE_FUNCTION)."""
        consts = list(self.read())

        def _looks_like_names(v, extended: int) -> bool:
            if not (isinstance(v, tuple) and all(isinstance(x, bytes) for x in v)):
                return False
            if extended == 0:
                return True
            def_names = {c.name for c in consts if isinstance(c, RawCode) and c.name is not None}
            return bool(def_names & set(v)) if def_names else True

        nxt = self.read()
        extended = 0
        while not _looks_like_names(nxt, extended):
            if extended >= _MAX_CONSTS_TAIL_EXTEND:
                raise DecryptError(
                    f"consts tuple recovery gave up after {_MAX_CONSTS_TAIL_EXTEND} "
                    f"extra objects without finding a tuple for names")
            consts.append(nxt)
            extended += 1
            nxt = self.read()
        return tuple(consts), nxt

    def read(self):
        start = self.pos
        code = self._byte()
        t = code & ~FLAG_REF
        ref = bool(code & FLAG_REF)
        idx = len(self.refs) if ref else -1
        if ref:
            self.refs.append(None)

        def setref(v):
            if ref:
                self.refs[idx] = v
            return v

        if t in (ord("0"), ord("N")):  # TYPE_NULL (dict terminator) and TYPE_NONE both -> None
            return setref(None)
        if t == ord("T"):
            return setref(True)
        if t == ord("F"):
            return setref(False)
        if t == ord("S"):
            return setref(StopIteration)
        if t == ord("."):
            return setref(Ellipsis)
        if t == ord("i"):
            return setref(self._long())
        if t == ord("I"):
            return setref(struct.unpack("<q", self._rd(8))[0])
        if t == ord("f"):
            n = self._byte()
            return setref(float(self._rd(n)))
        if t == ord("g"):
            return setref(struct.unpack("<d", self._rd(8))[0])
        if t in (ord("x"), ord("y")):
            re_, im_ = struct.unpack("<dd", self._rd(16))
            return setref(complex(re_, im_))
        if t == ord("l"):
            n = self._long()
            digits = self._rd(2 * abs(n))
            val = 0
            for i in range(abs(n) - 1, -1, -1):
                d = struct.unpack_from("<H", digits, i * 2)[0]
                val = (val << 15) | d
            return setref(-val if n < 0 else val)
        if t in (ord(")"), ord("(")):
            n = self._byte() if t == ord(")") else self._long()
            vals = [self.read() for _ in range(n)]
            return setref(tuple(vals))
        if t == ord("["):
            n = self._long()
            return setref([self.read() for _ in range(n)])
        if t in (ord("<"), ord(">")):
            n = self._long()
            vals = [self.read() for _ in range(n)]
            return setref(frozenset(vals) if t == ord(">") else set(vals))
        if t == ord("{"):
            d = {}
            while True:
                k = self.read()
                if k is None and self.data[self.pos - 1] == ord("0"):
                    break
                v = self.read()
                d[k] = v
            return setref(d)
        if t in (ord("z"), ord("Z")):
            n = self._byte()
            return setref(self._rd(n))
        if t in (ord("a"), ord("A"), ord("u"), ord("s"), ord("t")):
            n = self._long()
            return setref(self._rd(n))
        if t == ord("r"):
            n = self._long()
            if not (0 <= n < len(self.refs)):
                raise DecryptError(f"bad backreference index {n} at offset {start} ({len(self.refs)} refs so far)")
            return self.refs[n]
        if t == ord("c"):
            rc = RawCode()
            try:
                rc.argcount = self._long()
                rc.posonlyargcount = self._long()
                rc.kwonlyargcount = self._long()
                if self.version >= (3, 11):
                    rc.stacksize = self._long()
                    rc.flags = self._long()
                    rc.code = self.read()
                    rc.consts, rc.names = self._read_consts_then_names()
                    localsplusnames = self.read()
                    localspluskinds = self.read()
                    rc.varnames, rc.cellvars, rc.freevars = _split_localsplus(localsplusnames, localspluskinds)
                    rc.filename = self.read()
                    rc.name = self.read()
                    rc.qualname = self.read()
                    rc.firstlineno = self._long()
                    rc.linetable = self.read()
                    rc.exceptiontable = self.read()
                else:
                    rc.nlocals = self._long()
                    rc.stacksize = self._long()
                    rc.flags = self._long()
                    rc.code = self.read()
                    rc.consts, rc.names = self._read_consts_then_names()
                    rc.varnames = self.read()
                    rc.freevars = self.read()
                    rc.cellvars = self.read()
                    rc.filename = self.read()
                    rc.name = self.read()
                    rc.firstlineno = self._long()
                    rc.lnotab = self.read()
            except DecryptError as e:
                # Keep whatever fields parsed before the failure (see RawCode).
                rc.partial_error = str(e)
                self.all_codes.append(rc)
                raise
            self.all_codes.append(rc)
            return setref(rc)
        if 0 < t < 0x20:
            return setref(Placeholder(t, self._rd(t)))
        raise DecryptError(f"unhandled marshal type 0x{code:02x} at offset {start} (ref={ref})")


# co_code between __pyarmor_enter_/exit_ markers is ordinary CPython bytecode,
# AES-GCM-encrypted in place. The const right after the enter marker is a 20-byte
# descriptor: [8] flag (1 or 3, picks the IV source), [11] span_start, [12:14]
# span_len (u16 LE). flag==3 -> IV=co_code[:12]; flag==1 -> IV is the 12 bytes
# right after the ciphertext. Same key/no-tag scheme as the outer blob. The
# descriptor's const index varies by Python version, so it's found by content
# match, not a fixed index.

def decrypt_vm_span(co_code: bytes, consts: tuple, key: bytes) -> tuple[bytes | None, str | None]:
    """(decrypted co_code, None) if VM-protected and decrypted, (None, None) if
    not VM-protected, (None, reason) if VM-protected but not understood."""
    enter_idx = None
    for i, c in enumerate(consts):
        if isinstance(c, bytes) and c.startswith(b"__pyarmor_enter_"):
            enter_idx = i
            break
    if enter_idx is None:
        return None, None
    if enter_idx + 1 >= len(consts) or not isinstance(consts[enter_idx + 1], bytes) or len(consts[enter_idx + 1]) != 20:
        return None, (f"found enter marker at co_consts[{enter_idx}] but co_consts[{enter_idx + 1}] "
                       f"isn't the expected 20-byte descriptor")
    desc = consts[enter_idx + 1]
    flag = desc[8]
    span_start = desc[11]
    span_len = int.from_bytes(desc[12:14], "little")
    if span_start + span_len > len(co_code):
        return None, f"descriptor span [{span_start}:{span_start + span_len}] exceeds co_code length {len(co_code)}"
    if flag == 3:
        iv = co_code[0:12]
    elif flag == 1:
        iv = co_code[span_start + span_len: span_start + span_len + 12]
    else:
        return None, f"unhandled descriptor flag byte {flag} (only 1 and 3 are known)"
    ciphertext = co_code[span_start:span_start + span_len]
    try:
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        plaintext = cipher.decrypt(ciphertext)
    except Exception as e:
        return None, f"AES-GCM decrypt raised {type(e).__name__}: {e}"
    return co_code[:span_start] + plaintext + co_code[span_start + span_len:], None


# .replace() on a throwaway template, not CodeType(...) directly -- the
# constructor's argument order differs per Python version, .replace() takes
# keywords. co_nlocals must always be passed explicitly: without it, .replace()
# silently breaks the object on <=3.10 or raises on >=3.11.

_CODE_TEMPLATE = compile("0", "<pyarmor-emu-template>", "eval")


def _decode_str(b, default=""):
    if isinstance(b, bytes):
        return b.decode("utf-8", "surrogateescape")
    return default


def _tuple_of_str(v):
    if isinstance(v, tuple) and all(isinstance(x, bytes) for x in v):
        return tuple(_decode_str(x) for x in v)
    return None


def _decode_tuple_field(v, field_name: str, path: str, raw_name, notes: list[str]) -> tuple:
    """varnames/freevars/cellvars, defaulting to () -- noted when it wasn't a clean
    string tuple, since that's usually a Placeholder, not real data."""
    t = _tuple_of_str(v)
    if t is not None:
        return t
    if isinstance(v, Placeholder):
        notes.append(f"{path} ({_decode_str(raw_name)!r}): {field_name} replaced with () "
                      f"-- was a placeholder {v!r}")
    return ()


def build_code_object(rc: RawCode, notes: list[str], seen_rc: set[int], key: bytes,
                       unsafe: dict[int, bytes], built_cache: dict[int, types.CodeType],
                       path: str = "<module>") -> types.CodeType:
    if id(rc) in built_cache:
        return built_cache[id(rc)]
    seen_rc.add(id(rc))

    def _build_const(c):
        if not isinstance(c, RawCode):
            return c
        return build_code_object(c, notes, seen_rc, key, unsafe, built_cache, path=f"{path}.<const>")

    consts = tuple(_build_const(c) for c in (rc.consts or ()))
    names = _tuple_of_str(rc.names) or ()
    varnames = _tuple_of_str(rc.varnames) or ()
    freevars = _decode_tuple_field(rc.freevars, "freevars", path, rc.name, notes)
    cellvars = _decode_tuple_field(rc.cellvars, "cellvars", path, rc.name, notes)

    filename = _decode_str(rc.filename, "<unknown>")
    name = _decode_str(rc.name, "<unknown>")

    if rc.partial_error is not None:
        notes.append(f"{path} ({name!r}): PARTIAL RECOVERY -- this record stopped parsing "
                      f"before it finished ({rc.partial_error}). Fields read before the "
                      f"failure (typically co_code and co_consts, read early) are shown "
                      f"as recovered; anything after that point falls back to an empty/"
                      f"unknown default rather than being lost along with the whole record.")

    # Must run before placeholders are dropped -- decrypt_vm_span scans consts for
    # the raw marker bytes.
    code_bytes = rc.code if isinstance(rc.code, bytes) else b""
    raw_ciphertext = None
    decrypted, reason = decrypt_vm_span(code_bytes, consts, key)
    if decrypted is not None:
        notes.append(f"{path} ({name!r}): VM span decrypted in place ({len(decrypted)} byte "
                      f"co_code, real CPython bytecode below)")
        code_bytes = decrypted
    if reason is not None:
        notes.append(f"{path} ({name!r}): VM-PROTECTED but NOT decrypted -- {reason}. "
                      f"co_code is still ciphertext, so a safe placeholder is used instead: "
                      f"passing raw ciphertext to .replace()/dis.dis() as bytecode has been "
                      f"seen to crash the interpreter outright on Python 3.12 and 3.14 "
                      f"(not a catchable exception). The real bytes are kept for the "
                      f"report's hex dump, never executed as bytecode.")
        raw_ciphertext = code_bytes
        code_bytes = _CODE_TEMPLATE.co_code

    consts = _drop_marshal_placeholders(consts)

    # `or 0` guards partial records where these were never reached -- rare, but
    # keeps .replace() from raising on a None where it wants an int.
    kwargs = dict(
        co_argcount=rc.argcount or 0,
        co_posonlyargcount=rc.posonlyargcount or 0,
        co_kwonlyargcount=rc.kwonlyargcount or 0,
        co_nlocals=rc.nlocals if rc.nlocals is not None else len(varnames),
        co_stacksize=rc.stacksize or 0,
        co_flags=rc.flags or 0,
        co_code=code_bytes,
        co_consts=consts,
        co_names=names,
        co_varnames=varnames,
        co_freevars=freevars,
        co_cellvars=cellvars,
        co_filename=filename,
        co_name=name,
        co_firstlineno=rc.firstlineno or 0,
    )
    # co_lnotab isn't settable via .replace() -- line numbers may be approximate
    # on <=3.10, opcodes unaffected.
    if rc.linetable is not None:
        kwargs["co_linetable"] = rc.linetable if isinstance(rc.linetable, bytes) else b""
    if rc.exceptiontable is not None:
        kwargs["co_exceptiontable"] = rc.exceptiontable if isinstance(rc.exceptiontable, bytes) else b""
    if rc.qualname is not None:
        kwargs["co_qualname"] = _decode_str(rc.qualname, name)

    built = _CODE_TEMPLATE.replace(**kwargs)
    if raw_ciphertext is not None:
        unsafe[id(built)] = raw_ciphertext
    built_cache[id(rc)] = built
    return built


# build_code_object already decrypted VM spans, so co_code is real bytecode here.

_PYARMOR_MARKER_RE = re.compile(rb"^__pyarmor_(enter|exit)_\d+__$")
_PYARMOR_ANY_MARKER_RE = re.compile(rb"^__pyarmor_(assert|enter|exit)_\d+__$")
_NATIVE_STUB_NAME = {b"assert": "C_ASSERT_ARMORED_INDEX", b"enter": "C_ENTER_CO_OBJECT_INDEX",
                      b"exit": "C_LEAVE_CO_OBJECT_INDEX"}


def vm_protected_markers(code: types.CodeType) -> list[str]:
    return [c.decode("ascii") for c in code.co_consts
            if isinstance(c, bytes) and _PYARMOR_MARKER_RE.match(c)]


def _describe_const(c) -> str:
    """One-line form of a const for the Constants: listing -- dis.dis() only shows a
    value on the instruction that loads it, so this is the only place some appear."""
    if isinstance(c, bytes):
        m = _PYARMOR_ANY_MARKER_RE.match(c)
        if m:
            kind = _NATIVE_STUB_NAME[m.group(1)]
            return (f"<lives here at runtime: the native C function {kind} -- marker "
                     f"{c.decode()!r}. PyArmor swaps this slot for a live function pointer "
                     f"when the module runs; a tool that only reads the file, never runs it, "
                     f"can point at where it goes but can't produce the function itself.>")
        try:
            return repr(c.decode("utf-8"))
        except UnicodeDecodeError:
            return f"<{len(c)} raw bytes> {c.hex()}"
    if isinstance(c, tuple):
        inner = ", ".join(_describe_const(x) for x in c)
        if len(c) == 1:
            inner += ","  # (64,) not (64) -- a bare paren silently drops the tuple-ness
        return f"({inner})"
    return repr(c)


def _drop_marshal_placeholders(consts: tuple) -> tuple:
    """Drop PyArmor's own marshal placeholders (0x01-0x1f) from consts -- every real
    element lines up at the same index once these are gone; leaving them in shifts
    every LOAD_CONST after them out of alignment."""
    return tuple(c for c in consts if not isinstance(c, Placeholder))


def print_report(code: types.CodeType, unsafe: dict[int, bytes], out, printed: set[int],
                  depth: int = 0, path: str = "<module>") -> None:
    printed.add(id(code))
    indent = "  " * depth
    out.write(f"{indent}=== {path}  name={code.co_name!r}  file={code.co_filename!r}  "
              f"line={code.co_firstlineno}  flags={hex(code.co_flags)} ===\n")
    markers = vm_protected_markers(code)
    if markers:
            out.write(f"{indent}  [VM-PROTECTED: found {', '.join(markers)} in co_consts -- "
                      f"the encrypted span has been decrypted in place; the disassembly "
                      f"below is real CPython bytecode, not ciphertext]\n")

    scalar_consts = [(i, c) for i, c in enumerate(code.co_consts) if not isinstance(c, types.CodeType)]
    if scalar_consts:
        out.write(f"{indent}  Constants:\n")
        for i, c in scalar_consts:
            out.write(f"{indent}    [{i}] {_describe_const(c)}\n")

    if id(code) in unsafe:
        # Still ciphertext -- dis.dis() has been seen to crash outright on this.
        out.write(f"{indent}  [skipping dis.dis(): co_code is still ciphertext (VM span "
                   f"decrypt failed for this function/version, see the note above) -- "
                   f"raw ciphertext hex: {unsafe[id(code)].hex()}]\n")
    else:
        try:
            # depth=0: our own recursion below already covers every nested object
            # once, each with its own Constants: listing -- dis's default
            # auto-recursion would just duplicate that, without the listing.
            dis.dis(code, file=out, depth=0)
        except Exception as e:
            # Don't let one malformed function take down the whole report.
            out.write(f"{indent}  [dis.dis failed: {type(e).__name__}: {e} -- "
                       f"co_code hex: {code.co_code.hex()}]\n")
    out.write("\n")
    for i, c in enumerate(code.co_consts):
        if isinstance(c, types.CodeType):
            const_path = f"{path}.consts[{i}]:{c.co_name}"
            if id(c) in printed:
                out.write(f"{indent}  [{const_path} -- already shown elsewhere in this report, "
                          f"not repeating it]\n\n")
                continue
            try:
                print_report(c, unsafe, out, printed, depth + 1, path=const_path)
            except Exception as e:
                out.write(f"{indent}  [failed to report {path}.consts[{i}]: "
                          f"{type(e).__name__}: {e}]\n")


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else list(argv)

    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    ap.add_argument("script", type=Path, help="obfuscated .py file to decrypt")
    ap.add_argument("--runtime", type=Path, default=None,
                     help="path to pyarmor_runtime.pyd (auto-discovered next to the "
                          "script if omitted)")
    ap.add_argument("-o", "--output", type=Path, default=None,
                     help="write the disassembly report here instead of stdout")
    ap.add_argument("--dump-plaintext", type=Path, default=None,
                     help="also write the raw decrypted marshal bytes here")
    args = ap.parse_args(argv)

    runtime_path = args.runtime or find_runtime_pyd(args.script)
    if runtime_path is None:
        sys.exit(f"error: no pyarmor_runtime.pyd found next to {args.script}; pass --runtime")
    if not runtime_path.exists():
        sys.exit(f"error: runtime not found: {runtime_path}")

    blobs = extract_blobs(args.script)
    if not blobs:
        sys.exit(f"error: no __pyarmor__(...) blob literal found in {args.script}")

    try:
        target_version = detect_target_version(blobs[0])
    except DecryptError as e:
        sys.exit(f"error: {e}")
    print(f"[*] blob targets Python {target_version[0]}.{target_version[1]}"
          f" (running under {sys.version_info.major}.{sys.version_info.minor})", file=sys.stderr)
    _reexec_if_needed(target_version, argv)
    # If we're still here, sys.version_info[:2] == target_version already.

    try:
        key = derive_key(runtime_path)
    except DecryptError as e:
        sys.exit(f"error: {e}")
    print(f"[*] derived key from {runtime_path.name}: {key.hex()}", file=sys.stderr)

    out = args.output.open("w", encoding="utf-8") if args.output else sys.stdout

    for bi, blob in enumerate(blobs):
        print(f"[*] blob {bi}: {len(blob)} bytes", file=sys.stderr)
        try:
            marshal_bytes = decrypt_blob(blob, key)
        except (DecryptError, struct.error, IndexError) as e:
            print(f"[!] blob {bi}: decrypt failed: {e}", file=sys.stderr)
            continue

        if args.dump_plaintext:
            dump_path = args.dump_plaintext if len(blobs) == 1 else args.dump_plaintext.with_name(
                f"{args.dump_plaintext.stem}.{bi}{args.dump_plaintext.suffix}")
            dump_path.write_bytes(marshal_bytes)
            print(f"[*] blob {bi}: wrote decrypted marshal bytes to {dump_path}", file=sys.stderr)

        blob_version = detect_target_version(blob)
        reader = MarshalReader(marshal_bytes, blob_version)
        root = None
        try:
            root = reader.read()
        except (DecryptError, struct.error, IndexError) as e:
            pct = 100 * reader.pos / max(len(marshal_bytes), 1)
            print(f"[!] blob {bi}: marshal parse failed at offset {reader.pos}: {e}", file=sys.stderr)
            print(f"    successfully parsed {reader.pos}/{len(marshal_bytes)} bytes ({pct:.1f}%) "
                  f"before this point. Falling back to reporting every fully-parsed code "
                  f"object found along the way.", file=sys.stderr)

        notes: list[str] = []
        seen_rc: set[int] = set()
        unsafe: dict[int, bytes] = {}
        built_cache: dict[int, types.CodeType] = {}
        printed: set[int] = set()
        reported = 0
        if isinstance(root, RawCode):
            code = build_code_object(root, notes, seen_rc, key, unsafe, built_cache)
            print_report(code, unsafe, out, printed, path=f"blob[{bi}]")
            reported = 1
        else:
            # Partial recovery: everything that finished parsing is already in
            # reader.all_codes, even records that are themselves partial
            # (RawCode.partial_error). built_cache/printed dedup objects that show
            # up both as their own top-level entry and nested under a full parent.
            for i, rc in enumerate(reader.all_codes):
                if id(rc) in seen_rc:
                    continue
                try:
                    code = build_code_object(rc, notes, seen_rc, key, unsafe, built_cache,
                                              path=f"blob[{bi}].code[{i}]")
                    print_report(code, unsafe, out, printed, path=f"blob[{bi}].code[{i}]")
                    reported += 1
                except Exception as e:
                    print(f"[!] blob {bi}: code[{i}] ({_decode_str(rc.name)!r}) failed to "
                          f"report: {type(e).__name__}: {e}", file=sys.stderr)
            if reported == 0:
                print(f"[!] blob {bi}: no code objects recovered at all", file=sys.stderr)

        for n in notes:
            print(f"[note] blob {bi}: {n}", file=sys.stderr)
        print(f"[*] blob {bi}: reported {reported} top-level code object(s) "
              f"({len(reader.refs)} total backreferenced objects seen)", file=sys.stderr)

    if args.output:
        out.close()


if __name__ == "__main__":
    main()
