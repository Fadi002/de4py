# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Multi-pass string encoding reversal for Python deobfuscation.
"""

import ast
import base64
import re
import codecs
import bz2
import zlib
import lzma
from typing import Optional


class StringDecoder:

    MAX_PASSES = 10

    def decode_all(self, source: str) -> str:
        for _ in range(self.MAX_PASSES):
            decoded = self._single_pass(source)
            if decoded == source:
                break
            source = decoded
        return source

    def _single_pass(self, source: str) -> str:
        source = self._unwrap_eval_exec(source)
        source = self._decode_base64_calls(source)
        source = self._decode_base64_dynamic_import(source)
        source = self._decode_base32_calls(source)
        source = self._decode_base85_calls(source)
        source = self._decode_base16_calls(source)
        source = self._decode_hex_escape_strings(source)
        source = self._decode_bytes_fromhex(source)
        source = self._decode_bytearray_literals(source)
        source = self._decode_chr_chains(source)
        source = self._decode_join_chr_list(source)
        source = self._decode_join_chr_map(source)
        source = self._decode_xor_zip(source)           # NEW: ''.join(chr(x^y) for x,y in zip([...],[...]))
        source = self._decode_xor_byte_arrays(source)
        source = self._decode_xor_comprehension(source)
        source = self._decode_zlib(source)
        source = self._decode_lzma(source)
        source = self._decode_bz2(source)
        source = self._decode_rot13(source)
        source = self._decode_unicode_escapes(source)
        source = self._decode_codecs_hex(source)
        source = self._decode_reversed_string(source)
        source = self._decode_int_hex_literal(source)
        source = self._fold_adjacent_string_literals(source)
        source = self._decode_encode_decode_roundtrip(source)
        return source

    # ── eval / exec unwrapping ────────────────────────────────────────────────

    def _unwrap_eval_exec(self, source: str) -> str:
        pattern = re.compile(
            r'(?:eval|exec)\s*\(\s*'
            r'(?:'
            r'  (b?"""[\s\S]*?""")'
            r"| (b?'''[\s\S]*?''')"
            r'| (b?"(?:[^"\\]|\\.)*")'
            r"| (b?'(?:[^'\\]|\\.)*')"
            r')\s*\)',
            re.VERBOSE,
        )
        def replace_match(m):
            raw = next(g for g in m.groups() if g is not None)
            try:
                val = ast.literal_eval(raw)
                if isinstance(val, (str, bytes)):
                    return val if isinstance(val, str) else val.decode('utf-8', errors='replace')
            except Exception:
                pass
            return m.group(0)
        return pattern.sub(replace_match, source)

    # ── Base64 ───────────────────────────────────────────────────────────────

    def _decode_base64_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b64decode\s*\(\s*b?(["\'])([A-Za-z0-9+/=\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def decode_b64(m):
            try:
                raw = m.group(2).replace('\n','').replace(' ','')
                return repr(base64.b64decode(raw).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(decode_b64, source)

    def _decode_base64_dynamic_import(self, source: str) -> str:
        pattern = re.compile(
            r'__import__\s*\(\s*[\'"]base64[\'"]\s*\)'
            r'\.b64decode\s*\(\s*b?["\']([A-Za-z0-9+/=]+)["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def decode_dyn(m):
            try:
                return repr(base64.b64decode(m.group(1)).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(decode_dyn, source)

    def _decode_base32_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b32decode\s*\(\s*b?(["\'])([A-Z2-7=\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                return repr(base64.b32decode(m.group(2).replace('\n','').replace(' ','')).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_base85_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b85decode\s*\(\s*b?(["\'])([!-u\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                return repr(base64.b85decode(m.group(2).replace('\n','').replace(' ','').encode()).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_base16_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b16decode\s*\(\s*b?(["\'])([A-F0-9\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                return repr(base64.b16decode(m.group(2).replace('\n','').replace(' ','')).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    # ── Hex / bytes ───────────────────────────────────────────────────────────

    def _decode_hex_escape_strings(self, source: str) -> str:
        """Convert '\\x68\\x65' inside STRING literals to ASCII. Skips bytes literals."""
        # (?<!b) prevents matching inside b'\\x..' byte literals
        pattern = re.compile(
            r'(?<!\\)(?<!b)"((?:\\x[0-9a-fA-F]{2})+)"'
            r'|'
            r"(?<!\\)(?<!b)'((?:\\x[0-9a-fA-F]{2})+)'"
        )

        def decode_hex(m: re.Match) -> str:
            content = m.group(1) or m.group(2)
            try:
                hex_bytes = bytes.fromhex(content.replace('\\x', ''))
                decoded = hex_bytes.decode('utf-8', errors='replace')
                # Only inline if result is clean ASCII — never put non-ASCII into source
                if '\ufffd' not in decoded and decoded.isascii():
                    return repr(decoded)
            except Exception:
                pass
            return m.group(0)

        return pattern.sub(decode_hex, source)

    def _decode_bytes_fromhex(self, source: str) -> str:
        p1 = re.compile(
            r'bytes\.fromhex\s*\(\s*["\']([0-9a-fA-F\s]+)["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d1(m):
            try:
                return repr(bytes.fromhex(m.group(1).replace(' ','').replace('\n','')).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(
            r'codecs\.decode\s*\(\s*b?["\']([0-9a-fA-F]+)["\']\s*,\s*["\']hex(?:_codec)?["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d2(m):
            try:
                return repr(bytes.fromhex(m.group(1)).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return p2.sub(d2, source)

    def _decode_bytearray_literals(self, source: str) -> str:
        p1 = re.compile(r'bytearray\s*\(\s*(b"[^"]*"|b\'[^\']*\')\s*\)(?:\.decode\s*\([^)]*\))?')
        def d1(m):
            try:
                return repr(ast.literal_eval(m.group(1)).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(r'bytearray\s*\(\s*\[([0-9,\s]+)\]\s*\)(?:\.decode\s*\([^)]*\))?')
        def d2(m):
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                if all(32 <= n <= 126 or n in (9,10,13) for n in nums):
                    return repr(bytearray(nums).decode('utf-8', errors='replace'))
            except Exception:
                pass
            return m.group(0)
        return p2.sub(d2, source)

    # ── chr / join patterns ───────────────────────────────────────────────────

    def _decode_chr_chains(self, source: str) -> str:
        pattern = re.compile(r'(?:chr\s*\(\s*\d{1,3}\s*\)\s*\+\s*)*chr\s*\(\s*\d{1,3}\s*\)')
        def d(m):
            try:
                result = eval(m.group(0), {'__builtins__':{}}, {'chr':chr})
                if isinstance(result, str) and result.isprintable():
                    return repr(result)
            except Exception:
                pass
            return m.group(0)
        return pattern.sub(d, source)

    def _decode_join_chr_list(self, source: str) -> str:
        p1 = re.compile(r'["\']["\']\.join\s*\(\s*\[?\s*chr\s*\(\s*\w+\s*\)\s+for\s+\w+\s+in\s+\[([0-9,\s]+)\]\s*\]?\s*\)')
        def d1(m):
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                r = ''.join(chr(n) for n in nums)
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(r'["\']["\']\.join\s*\(\s*map\s*\(\s*chr\s*,\s*\[([0-9,\s]+)\]\s*\)\s*\)')
        def d2(m):
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                r = ''.join(chr(n) for n in nums)
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        source = p2.sub(d2, source)
        p3 = re.compile(r'["\']["\']\.join\s*\(\s*\[\s*((?:chr\s*\(\s*\d{1,3}\s*\)\s*,?\s*)+)\]\s*\)')
        def d3(m):
            try:
                nums = [int(x) for x in re.findall(r'chr\s*\(\s*(\d{1,3})\s*\)', m.group(1))]
                r = ''.join(chr(n) for n in nums)
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        return p3.sub(d3, source)

    def _decode_join_chr_map(self, source: str) -> str:
        pattern = re.compile(
            r'["\']["\']\.join\s*\(\s*map\s*\(\s*chr\s*,\s*range\s*\(\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d+))?\s*\)\s*\)\s*\)'
        )
        def d(m):
            try:
                start, stop = int(m.group(1)), int(m.group(2))
                step = int(m.group(3)) if m.group(3) else 1
                r = ''.join(chr(n) for n in range(start, stop, step))
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    # ── NEW: XOR zip decode ───────────────────────────────────────────────────

    def _decode_xor_zip(self, source: str) -> str:
        """
        Decode patterns like:
          ''.join(chr(x ^ y) for x, y in zip([0xde, 0xf9, ...], [0x8d] * 11))
          ''.join(chr(x ^ y) for x, y in zip([N, ...], [K] * M))
          ''.join(chr(x ^ K) for x in [N, N, N])
        """
        # Pattern 1: zip([...], [K] * M) or zip([...], [K, K, K, ...])
        p1 = re.compile(
            r"[\"'][\"']\.join\s*\(\s*(?:chr\s*\(\s*\w+\s*\^\s*\w+\s*\)\s*for\s+\w+\s*,\s*\w+\s+in|"
            r"\(chr\s*\(\s*\w+\s*\^\s*\w+\s*\)\s*for\s+\w+\s*,\s*\w+\s+in)\s+zip\s*\("
            r"\s*\[([0-9,\s0xXa-fA-F]+)\]\s*,\s*"
            r"\[([0-9,\s0xXa-fA-F]+)\]\s*(?:\*\s*\d+)?\s*\)\s*\)\s*\)"
        )

        def d1(m):
            try:
                def parse_list(s):
                    # Handle hex literals like 0xde
                    return [int(x.strip(), 0) for x in s.split(',') if x.strip()]
                arr1 = parse_list(m.group(1))
                arr2_raw = m.group(2)
                arr2 = parse_list(arr2_raw)
                # If arr2 has one element, it's a repeated key
                if len(arr2) == 1:
                    key = arr2[0]
                    result = ''.join(chr(x ^ key) for x in arr1)
                else:
                    result = ''.join(chr(x ^ y) for x, y in zip(arr1, arr2))
                return repr(result) if result.isprintable() else m.group(0)
            except Exception:
                return m.group(0)

        source = p1.sub(d1, source)

        # Pattern 2: Use safe eval for remaining zip patterns
        p2 = re.compile(
            r"[\"'][\"']\.join\s*\([^)]{0,500}\bzip\b[^)]{0,300}\)\s*\)"
        )

        def d2(m):
            expr = m.group(0)
            try:
                result = eval(expr, {'__builtins__': {'chr': chr, 'zip': zip, 'range': range}})
                if isinstance(result, str) and result.isprintable() and len(result) > 0:
                    return repr(result)
            except Exception:
                pass
            return m.group(0)

        source = p2.sub(d2, source)
        return source

    # ── XOR byte arrays ───────────────────────────────────────────────────────

    def _decode_xor_byte_arrays(self, source: str) -> str:
        p1 = re.compile(
            r'bytes\s*\(\s*\[\s*\w+\s*\^\s*(\d+)\s+for\s+\w+\s+in\s+\[([0-9,\s]+)\]\s*\]\s*\)'
        )
        def d1(m):
            try:
                key = int(m.group(1))
                nums = [int(x.strip()) for x in m.group(2).split(',') if x.strip()]
                return repr(bytes([n^key for n in nums]).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(r'bytes\s*\(\s*\[([0-9,\s]+)\]\s*\)')
        def d2(m):
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                if all(32<=n<=126 or n in (9,10,13) for n in nums):
                    return repr(bytes(nums).decode('utf-8', errors='replace'))
            except Exception:
                pass
            return m.group(0)
        return p2.sub(d2, source)

    def _decode_xor_comprehension(self, source: str) -> str:
        pattern = re.compile(
            r'bytes\s*\(\s*\[?\s*\w+\s*\^\s*(\d+)\s+for\s+\w+\s+in\s+(b"[^"]*"|b\'[^\']*\')\s*\]?\s*\)'
        )
        def d(m):
            try:
                key = int(m.group(1))
                raw = ast.literal_eval(m.group(2))
                return repr(bytes(b^key for b in raw).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    # ── Compression ──────────────────────────────────────────────────────────

    def _decode_zlib(self, source): return self._decode_compression(source,'zlib',zlib.decompress)
    def _decode_lzma(self, source): return self._decode_compression(source,'lzma',lzma.decompress)
    def _decode_bz2(self,  source): return self._decode_compression(source,'bz2', bz2.decompress)

    def _decode_compression(self, source, name, fn):
        pattern = re.compile(
            rf'{re.escape(name)}\.decompress\s*\(\s*(b"[^"]*"|b\'[^\']*\')\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                return repr(fn(ast.literal_eval(m.group(1))).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    # ── Text transforms ───────────────────────────────────────────────────────

    def _decode_rot13(self, source: str) -> str:
        pattern = re.compile(r'codecs\.decode\s*\(\s*(["\'][^"\']+["\'])\s*,\s*["\']rot.?13["\']\s*\)')
        def d(m):
            try:
                return repr(codecs.decode(ast.literal_eval(m.group(1)), 'rot_13'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_unicode_escapes(self, source: str) -> str:
        pattern = re.compile(r'"((?:\\u[0-9a-fA-F]{4})+)"|\'((?:\\u[0-9a-fA-F]{4})+)\'')
        def d(m):
            try:
                return repr((m.group(1) or m.group(2)).encode('utf-8').decode('unicode_escape'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_codecs_hex(self, source: str) -> str:
        pattern = re.compile(
            r'codecs\.decode\s*\(\s*(b["\'][0-9a-fA-F]+["\'])\s*,\s*["\']hex_codec["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                raw = ast.literal_eval(m.group(1))
                return repr(bytes.fromhex(raw.decode('ascii')).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_reversed_string(self, source: str) -> str:
        p1 = re.compile(r'["\']["\']\.join\s*\(\s*reversed\s*\(\s*(["\'][^"\']+["\'])\s*\)\s*\)')
        def d1(m):
            try:
                return repr(ast.literal_eval(m.group(1))[::-1])
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(r'(["\'][^"\']{2,}["\'])\[::-1\]')
        def d2(m):
            try:
                return repr(ast.literal_eval(m.group(1))[::-1])
            except Exception:
                return m.group(0)
        return p2.sub(d2, source)

    def _decode_int_hex_literal(self, source: str) -> str:
        pattern = re.compile(r'\bint\s*\(\s*(["\'][0-9a-fA-FxXbBoO]+["\'])\s*,\s*(\d+)\s*\)')
        def d(m):
            try:
                s = ast.literal_eval(m.group(1))
                base = int(m.group(2))
                if base in (2,8,10,16):
                    return str(int(s, base))
            except Exception:
                pass
            return m.group(0)
        return pattern.sub(d, source)

    def _fold_adjacent_string_literals(self, source: str) -> str:
        try:
            ast.parse(source)
        except SyntaxError:
            return source
        pattern = re.compile(
            r'(?<![a-zA-Z0-9_\)])'
            r'(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*)\1'
            r'\s+'
            r'(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*)\3'
        )
        def d(m):
            try:
                v1 = ast.literal_eval(f'{m.group(1)}{m.group(2)}{m.group(1)}')
                v2 = ast.literal_eval(f'{m.group(3)}{m.group(4)}{m.group(3)}')
                if isinstance(v1, str) and isinstance(v2, str):
                    return repr(v1+v2)
            except Exception:
                pass
            return m.group(0)
        for _ in range(5):
            prev = source
            source = pattern.sub(d, source)
            if source == prev:
                break
        return source

    def _decode_encode_decode_roundtrip(self, source: str) -> str:
        pattern = re.compile(
            r'(["\'][^"\'\\]*(?:\\.[^"\'\\]*)*["\'])'
            r'\.encode\s*\([^)]*\)'
            r'\.decode\s*\([^)]*\)'
        )
        def d(m):
            try:
                s = ast.literal_eval(m.group(1))
                if isinstance(s, str):
                    return repr(s)
            except Exception:
                pass
            return m.group(0)
        return pattern.sub(d, source)
