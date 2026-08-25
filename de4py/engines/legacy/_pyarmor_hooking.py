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
pyarmor_hook.py -- dump tool PyArmor 9.2.6 (trial), Only for Python 3.11+.

Detours the runtime's C_ENTER handler to capture every code object as it
decrypts, then force-calls the target's functions to reach nested bodies.
Run under the same Python version the target was obfuscated with.

Actually imports and executes the target file. de4py only invokes this
script as an isolated subprocess, under an interpreter matching the
target's Python version, and only after the user has explicitly chosen
the dynamic/hooking recovery mode over the static (non-executing) one.
"""

import argparse
import ast
import builtins
import ctypes
import dis
import importlib.util
import os
import re
import struct
import subprocess
import sys
import types

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _peek_target_version(target_path):
    """Read the target's Python version from the blob header, no exec involved."""
    try:
        tree = ast.parse(open(target_path, encoding="utf-8").read(), filename=target_path)
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "__pyarmor__" and node.args:
            try:
                blob = ast.literal_eval(node.args[-1])
            except ValueError:
                continue
            if isinstance(blob, bytes) and len(blob) >= 11 and blob[:8] == b"PY000000":
                return blob[9], blob[10]
    return None


def _reexec_if_needed(target_version, argv):
    if sys.version_info[:2] == target_version:
        return
    maj, minr = target_version
    script_path = os.path.abspath(__file__)
    for cmd in (["py", f"-{maj}.{minr}", script_path, *argv],
                [f"python{maj}.{minr}", script_path, *argv]):
        try:
            proc = subprocess.run(cmd)
        except (FileNotFoundError, OSError):
            continue
        sys.exit(proc.returncode)
    sys.exit(f"error: this target was obfuscated for Python {maj}.{minr}, but no matching "
              f"interpreter was found on PATH (tried 'py -{maj}.{minr}', 'python{maj}.{minr}'). "
              f"Install it, or run this script directly under Python {maj}.{minr}.")

# --- WinAPI / CPython ABI entry points -------------------------------------

k32 = ctypes.windll.kernel32
k32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
k32.GetModuleHandleW.restype = ctypes.c_void_p
k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
k32.GetProcAddress.restype = ctypes.c_void_p
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_uint]
k32.VirtualAlloc.restype = ctypes.c_void_p
k32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.POINTER(ctypes.c_ulong)]

# pythonapi resolves against the running interpreter, not a hardcoded pythonXY.dll
pydll = ctypes.pythonapi
pydll.PyBytes_AsString.argtypes = [ctypes.c_void_p]
pydll.PyBytes_AsString.restype = ctypes.c_void_p
pydll.PyBytes_Size.argtypes = [ctypes.c_void_p]
pydll.PyBytes_Size.restype = ctypes.c_int

HOOK_LEN = 16  # first N bytes of C_ENTER we patch and replay


class PyArmorRecoverer:
    def __init__(self, target, runtime_override=None, out=None):
        self.target = os.path.abspath(target)
        self.outdir = os.path.dirname(self.target) or "."
        self.base = os.path.splitext(os.path.basename(self.target))[0]
        self.runtime_override = os.path.abspath(runtime_override) if runtime_override else None
        self.out = out or sys.stdout
        self.c_enter = 0
        self.mod = None
        self.captured = []
        self.seen_codes = set()
        # GC must not free these while the patch is live
        self.hook = None
        self.orig_fn = None
        self.tramp = None
        self.import_hook = None

    @staticmethod
    def _log(msg):
        print(msg, file=sys.stderr)

    # --- runtime discovery -------------------------------------------------

    def find_runtime(self):
        """Embedded runtime dir the target references, as
        (modname, abs_pyd_path), or None if it isn't a PyArmor 9 script."""
        if self.runtime_override:
            name = os.path.basename(os.path.dirname(self.runtime_override))
            return (name, self.runtime_override)
        src = open(self.target, "rb").read().decode("utf-8", "replace")
        m = re.search(r"(pyarmor_runtime_[A-Za-z0-9_]+)", src)
        if not m:
            return None
        name = m.group(1)
        d = self.outdir
        while True:
            for base in (d, os.path.join(d, "dist")):
                cand = os.path.join(base, name, "pyarmor_runtime.pyd")
                if os.path.isfile(cand):
                    return (name, os.path.abspath(cand))
            parent = os.path.dirname(d)
            if parent == d:
                return (name, None)
            d = parent

    def load_runtime(self):
        """Import the runtime package and return its HMODULE (or an exit code)."""
        found = self.find_runtime()
        if not found:
            self._log("[!] no embedded pyarmor_runtime in target; is this a PyArmor 9 script?")
            return 3
        modname, pyd_path = found
        sys.path.insert(0, self.outdir)
        if pyd_path:
            sys.path.insert(0, os.path.dirname(pyd_path))
        try:
            __import__(modname)
        except Exception as e:
            self._log(f"[!] failed to import runtime {modname}: {e}")
            return 4

        # GetModuleHandleW needs the exact absolute pyd path
        hmod = k32.GetModuleHandleW(pyd_path) if pyd_path else None
        if hmod is None:
            for m in list(sys.modules.values()):
                f = getattr(m, "__file__", "")
                if f and f.endswith(".pyd") and "pyarmor_runtime" in f:
                    hmod = k32.GetModuleHandleW(os.path.abspath(f))
                    break
        if not hmod:
            self._log("[!] runtime loaded but HMODULE not resolved")
            return 4
        self._log(f"[*] runtime HMODULE = 0x{hmod:x}")
        return hmod

    # --- PE helpers --------------------------------------------------------

    @staticmethod
    def _write_mem(addr, data):
        """Write bytes into an executable page (flip to RWX and back)."""
        old = ctypes.c_ulong()
        page = ctypes.c_void_p(addr & ~0xFFF)
        k32.VirtualProtect(page, 0x1000, 0x40, ctypes.byref(old))
        ctypes.memmove(addr, data, len(data))
        k32.VirtualProtect(page, 0x1000, old.value, ctypes.byref(old))

    def _pe_sections(self, base):
        """Map section name -> (virtual address, virtual size) of a loaded PE."""
        e = ctypes.c_uint.from_address(base + 0x3C).value
        nt = base + e
        no = ctypes.c_ushort.from_address(nt + 20).value
        so = nt + 24 + no
        ns = ctypes.c_ushort.from_address(nt + 6).value
        sects = {}
        for i in range(ns):
            s = so + i * 40
            nm = bytes(ctypes.string_at(s, 8)).rstrip(b"\x00")
            vsz = ctypes.c_uint.from_address(s + 8).value
            va = ctypes.c_uint.from_address(s + 12).value
            sects[nm] = (va, vsz)
        return sects

    def _find_iat_slot(self, base, target_fn):
        """.idata slot holding target_fn (the resolved import address)."""
        sects = self._pe_sections(base)
        if b".idata" not in sects:
            return None
        va, vsz = sects[b".idata"]
        for a in range(base + va, base + va + vsz - 8, 8):
            if struct.unpack("<Q", ctypes.string_at(a, 8))[0] == target_fn:
                return a
        return None

    def _read_ml_meth(self, builtin):
        """PyCFunctionObject.m_ml at +16, PyMethodDef.ml_meth at +8."""
        m_ml = ctypes.c_void_p.from_address(id(builtin) + 16).value
        return ctypes.c_void_p.from_address(m_ml + 8).value

    def _snapshot_code(self, co):
        # co_code gets re-encrypted in place once C_LEAVE fires -- copy now.
        args = [
            co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount,
            co.co_nlocals, co.co_stacksize, co.co_flags,
            bytes(memoryview(co.co_code)),
            co.co_consts, co.co_names, co.co_varnames,
            co.co_filename, co.co_name,
        ]
        if sys.version_info >= (3, 11):
            args += [co.co_qualname, co.co_firstlineno, co.co_linetable,
                     co.co_exceptiontable, co.co_freevars, co.co_cellvars]
        else:
            args += [co.co_firstlineno, co.co_lnotab, co.co_freevars, co.co_cellvars]
        return types.CodeType(*args)

    # --- C_ENTER discovery -------------------------------------------------

    def _discover_c_enter(self, code):
        co = ctypes.cast(code, ctypes.py_object).value
        for c in co.co_consts:
            if type(c).__name__ == "builtin_function_or_method" and getattr(c, "__name__", "") == "C_ENTER_CO_OBJECT_INDEX":
                self.c_enter = self._read_ml_meth(c)
                return

    def _on_import(self, mod_name, code, globals_, locals_):
        # Discovers C_ENTER and installs the detour, then aborts the exec by
        # returning NULL -- running the real exec here would re-enter the
        # detour as a nested callback and crash. run() retries after this.
        try:
            self._discover_c_enter(code)
            if self.c_enter:
                self._log(f"[*] C_ENTER discovered at 0x{self.c_enter:x}")
                self.install_detour(self.c_enter)
            else:
                self._log("[!] C_ENTER_CO_OBJECT_INDEX not found in wrapper consts")
        except Exception as e:
            self._log(f"[!] discovery hook error: {type(e).__name__}: {e}")
        return None

    # --- detour ------------------------------------------------------------

    def install_detour(self, c_enter):
        # Overwrite C_ENTER's prologue with a jump to our hook; a trampoline
        # holding the original bytes replays it before continuing.
        orig = bytes(ctypes.string_at(c_enter, HOOK_LEN))

        tramp = k32.VirtualAlloc(None, 0x1000, 0x3000, 0x40)
        buf = bytearray(orig)
        buf += b"\xff\x25\x00\x00\x00\x00"
        buf += struct.pack("<Q", c_enter + HOOK_LEN)
        ctypes.memmove(tramp, bytes(buf), len(buf))

        orig_fn = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(tramp)

        @ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        def hook(self_, arg):
            ret = orig_fn(self_, arg)  # decrypts co_code; result embeds a pointer to it
            try:
                n = pydll.PyBytes_Size(arg)
                data = bytes(ctypes.string_at(pydll.PyBytes_AsString(arg), n))
                ptr = struct.unpack("<Q", data[0:8])[0]
                co = ctypes.cast(ptr, ctypes.py_object).value
                if isinstance(co, types.CodeType):
                    snap = self._snapshot_code(co)
                    key = (co.co_name, snap.co_code)
                    if key not in self.seen_codes:
                        self.seen_codes.add(key)
                        self.captured.append(snap)
                        self._log(f"[hook] captured {snap.co_name!r} co_code={snap.co_code.hex()[:80]}...")
            except Exception as e:
                self._log(f"[hook err] {type(e).__name__}: {e}")
            return ret

        self._write_mem(c_enter, b"\xff\x25\x00\x00\x00\x00" + struct.pack("<Q", ctypes.cast(hook, ctypes.c_void_p).value))
        self._log(f"[*] C_ENTER @0x{c_enter:x} detoured -> 0x{ctypes.cast(hook, ctypes.c_void_p).value:x} (tramp 0x{tramp:x})")

        # pin: the GC must not free the live patch's callback/trampoline
        self.hook = hook
        self.orig_fn = orig_fn
        self.tramp = tramp

    # --- capture passes ----------------------------------------------------

    def exec_target(self):
        # Import as a named module, never run as __main__ -- that path
        # bypasses the C_ENTER detour.
        try:
            spec = importlib.util.spec_from_file_location(self.base, self.target)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[self.base] = mod
            spec.loader.exec_module(mod)
            self.mod = mod
        except SystemExit:
            pass
        except Exception as e:
            self._log(f"[!] target raised (non-fatal): {type(e).__name__}: {e}")

    def force_call(self):
        # Calls each top-level function so its own C_ENTER fires and its body
        # decrypts -- the __main__ guard never runs under a named import.
        if self.mod is None:
            return
        for f in vars(self.mod).values():
            if not isinstance(f, types.FunctionType):
                continue
            try:
                f()
            except Exception as e:
                self._log(f"    [*] call {f.__name__} failed (non-fatal): {type(e).__name__}: {e}")

    def report(self):
        p = lambda *a: print(*a, file=self.out)
        p("=" * 70)
        if not self.captured:
            p("[!] nothing captured")
            return 5
        seen = []
        for co in self.captured:
            if any(co is s for s in seen):
                continue
            seen.append(co)
            p(f"[*] recovered code object: {co.co_name!r}")
            p(f"    co_names  = {co.co_names!r}")
            p(f"    co_consts = {co.co_consts!r}")
            p(f"    co_code.hex() = {co.co_code.hex()}")
            p("")
            try:
                dis_txt = "".join(dis.Bytecode(co).dis())
            except Exception as e:
                p(f"[!] dis failed: {type(e).__name__}: {e}")
                et = getattr(co, "co_exceptiontable", None)
                p(f"    co_exceptiontable = {et.hex() if et else None}")
                p(f"    co_code len = {len(co.co_code)}")
                for i in range(0, min(len(co.co_code), 256), 16):
                    p(f"    {i:04x}: {co.co_code[i:i+16].hex()}")
                dis_txt = ""
            p("[*] disassembly:")
            p(dis_txt)
            p("")
        return 0

    # --- main flow ---------------------------------------------------------

    def run(self):
        hmod = self.load_runtime()
        if not isinstance(hmod, int):
            return hmod

        # pass 1: patch the IAT so the wrapper's exec call lands in our hook
        dllname = "python%d%d.dll" % sys.version_info[:2]
        pyhmod = k32.GetModuleHandleW(dllname)
        real_fn = k32.GetProcAddress(pyhmod, b"PyImport_ExecCodeModuleObject")
        slot = self._find_iat_slot(hmod, real_fn)
        if slot is None:
            self._log("[!] PyImport_ExecCodeModuleObject IAT slot not found")
            return 6
        self._log(f"[*] ExecCodeModuleObject IAT slot @0x{slot - hmod:x}")

        @ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        def import_hook(mod_name, code, globals_, locals_):
            return self._on_import(mod_name, code, globals_, locals_)

        self.import_hook = import_hook  # pin

        self._write_mem(slot, struct.pack("<Q", ctypes.cast(import_hook, ctypes.c_void_p).value))
        try:
            self.exec_target()
        finally:
            # restore the slot; the machine detour stays live for pass 2
            self._write_mem(slot, struct.pack("<Q", real_fn))

        if not self.c_enter:
            self._log("[!] C_ENTER not discovered; nothing to do")
            return 7

        # pass 2: normal exec, now that the detour is installed
        sys.modules.pop(self.base, None)
        self.exec_target()
        if self.mod is None:
            self._log("[!] pass-2 exec failed to load the module")
            return 8

        self.force_call()
        return self.report()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)

    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    ap.add_argument("script", help="obfuscated .py file to recover (this actually runs it)")
    ap.add_argument("--runtime", default=None,
                     help="path to pyarmor_runtime.pyd (auto-discovered next to the "
                          "script, or in an ancestor dist/ dir, if omitted)")
    ap.add_argument("-o", "--output", default=None,
                     help="write the recovered report here instead of stdout")
    args = ap.parse_args(argv)

    target = os.path.abspath(args.script)
    if not os.path.isfile(target):
        sys.exit(f"[!] not found: {target}")
    if args.runtime and not os.path.isfile(args.runtime):
        sys.exit(f"[!] runtime not found: {args.runtime}")

    target_version = _peek_target_version(target)
    if target_version is not None:
        _reexec_if_needed(target_version, argv)

    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    try:
        sys.exit(PyArmorRecoverer(target, runtime_override=args.runtime, out=out).run())
    finally:
        if args.output:
            out.close()


if __name__ == "__main__":
    main()
