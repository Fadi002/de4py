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

    MAX_PASSES = 10  # Safety limit on recursion depth

    def decode_all(self, source: str) -> str:
        """
        Run decoding passes until no further changes occur or max passes reached.
        Returns the maximally decoded source.
        """
        for pass_num in range(self.MAX_PASSES):
            decoded = self._single_pass(source)
            if decoded == source:
                break  # Converged — no more patterns found
            source = decoded
        return source

    def _single_pass(self, source: str) -> str:
        """Apply all decoders once in the correct dependency order"""
        # Unwrap eval/exec layers first so inner content becomes visible
        source = self._unwrap_eval_exec(source)

        # Base encodings (most common)
        source = self._decode_base64_calls(source)
        source = self._decode_base64_dynamic_import(source)
        source = self._decode_base32_calls(source)
        source = self._decode_base85_calls(source)
        source = self._decode_base16_calls(source)

        # Hex / byte patterns
        source = self._decode_hex_escape_strings(source)
        source = self._decode_bytes_fromhex(source)
        source = self._decode_bytearray_literals(source)

        # Character-level patterns
        source = self._decode_chr_chains(source)
        source = self._decode_join_chr_list(source)      # ''.join(chr(x) for x in [...])
        source = self._decode_join_chr_map(source)       # ''.join(map(chr, [...]))

        # XOR patterns
        source = self._decode_xor_byte_arrays(source)
        source = self._decode_xor_comprehension(source)  # bytes(b ^ k for b in b"...")

        # Compression
        source = self._decode_zlib(source)
        source = self._decode_lzma(source)
        source = self._decode_bz2(source)

        # Text transforms
        source = self._decode_rot13(source)
        source = self._decode_unicode_escapes(source)
        source = self._decode_codecs_hex(source)         # codecs.decode(s, 'hex_codec')
        source = self._decode_reversed_string(source)    # ''.join(reversed("..."))
        source = self._decode_int_hex_literal(source)    # int("ff", 16) → 255

        # String-level cleanup
        source = self._fold_adjacent_string_literals(source)
        source = self._decode_encode_decode_roundtrip(source)  # "x".encode().decode()

        return source

    # --- eval / exec unwrapping ------------------------------------------------

    def _unwrap_eval_exec(self, source: str) -> str:
        """
        Replace eval("literal_string") and exec("literal_string") with
        the string content itself, only when the argument is a pure literal.
        SAFE: uses ast.literal_eval, never calls eval() on unknown code.
        """
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

        def replace_match(m: re.Match) -> str:
            raw = next(g for g in m.groups() if g is not None)
            try:
                val = ast.literal_eval(raw)
                if isinstance(val, (str, bytes)):
                    return val if isinstance(val, str) else val.decode('utf-8', errors='replace')
            except Exception:
                pass
            return m.group(0)

        return pattern.sub(replace_match, source)

    # --- Base64 ----------------------------------------------------------------

    def _decode_base64_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b64decode\s*\(\s*'
            r'b?(["\'])([A-Za-z0-9+/=\s]+)\1'
            r'\s*\)(?:\.decode\s*\([^)]*\))?'
        )

        def decode_b64(m: re.Match) -> str:
            try:
                raw = m.group(2).replace('\n', '').replace(' ', '')
                decoded = base64.b64decode(raw).decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern.sub(decode_b64, source)

    def _decode_base64_dynamic_import(self, source: str) -> str:
        pattern = re.compile(
            r'__import__\s*\(\s*[\'"]base64[\'"]\s*\)'
            r'\.b64decode\s*\(\s*b?["\']([A-Za-z0-9+/=]+)["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_dynamic(m: re.Match) -> str:
            try:
                decoded = base64.b64decode(m.group(1)).decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern.sub(decode_dynamic, source)

    # --- Base32 ----------------------------------------------------------------

    def _decode_base32_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b32decode\s*\(\s*b?(["\'])([A-Z2-7=\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_b32(m: re.Match) -> str:
            try:
                raw = m.group(2).replace('\n', '').replace(' ', '')
                decoded = base64.b32decode(raw).decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern.sub(decode_b32, source)

    # --- Base85 ----------------------------------------------------------------

    def _decode_base85_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b85decode\s*\(\s*b?(["\'])([!-u\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_b85(m: re.Match) -> str:
            try:
                raw = m.group(2).replace('\n', '').replace(' ', '')
                decoded = base64.b85decode(raw.encode()).decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern.sub(decode_b85, source)

    # --- Base16 (hex encoding) -------------------------------------------------

    def _decode_base16_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b16decode\s*\(\s*b?(["\'])([A-F0-9\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_b16(m: re.Match) -> str:
            try:
                raw = m.group(2).replace('\n', '').replace(' ', '')
                decoded = base64.b16decode(raw).decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern.sub(decode_b16, source)

    # --- Hex escape strings ----------------------------------------------------

    def _decode_hex_escape_strings(self, source: str) -> str:
        """Convert '\\x68\\x65\\x6c\\x6c\\x6f' inside string literals to 'hello'."""
        pattern = re.compile(
            r'(?<!\\)"((?:\\x[0-9a-fA-F]{2})+)"'
            r'|'
            r"(?<!\\)'((?:\\x[0-9a-fA-F]{2})+)'"
        )

        def decode_hex(m: re.Match) -> str:
            content = m.group(1) or m.group(2)
            try:
                hex_bytes = bytes.fromhex(content.replace('\\x', ''))
                decoded = hex_bytes.decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern.sub(decode_hex, source)

    # --- bytes.fromhex() -------------------------------------------------------

    def _decode_bytes_fromhex(self, source: str) -> str:
        """Decode bytes.fromhex('deadbeef') and b'...'.hex() round-trips."""
        # bytes.fromhex("...")
        pattern = re.compile(
            r'bytes\.fromhex\s*\(\s*["\']([0-9a-fA-F\s]+)["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_fromhex(m: re.Match) -> str:
            try:
                raw = m.group(1).replace(' ', '').replace('\n', '')
                decoded = bytes.fromhex(raw).decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        source = pattern.sub(decode_fromhex, source)

        # codecs.decode("...", "hex") / ("hex_codec")
        pattern2 = re.compile(
            r'codecs\.decode\s*\(\s*b?["\']([0-9a-fA-F]+)["\']\s*,\s*["\']hex(?:_codec)?["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_hex_codec(m: re.Match) -> str:
            try:
                decoded = bytes.fromhex(m.group(1)).decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern2.sub(decode_hex_codec, source)

    # --- bytearray literal decode ----------------------------------------------

    def _decode_bytearray_literals(self, source: str) -> str:
        """
        bytearray(b'\\x68\\x65\\x6c\\x6c\\x6f').decode() → 'hello'
        bytearray([104, 101, 108, 108, 111]).decode() → 'hello'
        """
        # bytearray(b"...").decode(...)
        pattern1 = re.compile(
            r'bytearray\s*\(\s*(b"[^"]*"|b\'[^\']*\')\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_bytearray_bytes(m: re.Match) -> str:
            try:
                raw = ast.literal_eval(m.group(1))
                return repr(raw.decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)

        source = pattern1.sub(decode_bytearray_bytes, source)

        # bytearray([N, N, ...]).decode()  — only printable ASCII
        pattern2 = re.compile(
            r'bytearray\s*\(\s*\[([0-9,\s]+)\]\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_bytearray_list(m: re.Match) -> str:
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                if all(32 <= n <= 126 or n in (9, 10, 13) for n in nums):
                    return repr(bytearray(nums).decode('utf-8', errors='replace'))
            except Exception:
                pass
            return m.group(0)

        return pattern2.sub(decode_bytearray_list, source)

    # --- chr() chains ----------------------------------------------------------

    def _decode_chr_chains(self, source: str) -> str:
        """Evaluate chr(104)+chr(101)+... → 'hello'"""
        pattern = re.compile(
            r'(?:chr\s*\(\s*\d{1,3}\s*\)\s*\+\s*)*chr\s*\(\s*\d{1,3}\s*\)',
        )

        def eval_chain(m: re.Match) -> str:
            expr = m.group(0)
            try:
                result = eval(expr, {"__builtins__": {}}, {"chr": chr})
                if isinstance(result, str) and result.isprintable():
                    return repr(result)
            except Exception:
                pass
            return expr

        return pattern.sub(eval_chain, source)

    def _decode_join_chr_list(self, source: str) -> str:
        """
        Decode: ''.join([chr(x) for x in [72, 101, 108, ...]])
                ''.join(chr(x) for x in [72, 101, 108, ...])
                ''.join([chr(N), chr(N), ...])
        """
        # Generator / list-comp form
        pattern1 = re.compile(
            r'["\']["\']\.join\s*\(\s*\[?\s*chr\s*\(\s*\w+\s*\)\s+'
            r'for\s+\w+\s+in\s+\[([0-9,\s]+)\]\s*\]?\s*\)'
        )

        def decode_join_gen(m: re.Match) -> str:
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                result = ''.join(chr(n) for n in nums)
                if result.isprintable():
                    return repr(result)
            except Exception:
                pass
            return m.group(0)

        source = pattern1.sub(decode_join_gen, source)

        # map(chr, [...]) form
        pattern2 = re.compile(
            r'["\']["\']\.join\s*\(\s*map\s*\(\s*chr\s*,\s*\[([0-9,\s]+)\]\s*\)\s*\)'
        )

        def decode_join_map(m: re.Match) -> str:
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                result = ''.join(chr(n) for n in nums)
                if result.isprintable():
                    return repr(result)
            except Exception:
                pass
            return m.group(0)

        source = pattern2.sub(decode_join_map, source)

        # Explicit list form: ''.join([chr(N), chr(N), ...])
        pattern3 = re.compile(
            r'["\']["\']\.join\s*\(\s*\[\s*((?:chr\s*\(\s*\d{1,3}\s*\)\s*,?\s*)+)\]\s*\)'
        )

        def decode_join_explicit(m: re.Match) -> str:
            try:
                nums = [int(x) for x in re.findall(r'chr\s*\(\s*(\d{1,3})\s*\)', m.group(1))]
                result = ''.join(chr(n) for n in nums)
                if result.isprintable():
                    return repr(result)
            except Exception:
                pass
            return m.group(0)

        return pattern3.sub(decode_join_explicit, source)

    def _decode_join_chr_map(self, source: str) -> str:
        """
        ''.join(map(chr, range(65, 91))) → 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        Also handles map(chr, some_bytes_literal)
        """
        pattern = re.compile(
            r'["\']["\']\.join\s*\(\s*map\s*\(\s*chr\s*,\s*range\s*\(\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d+))?\s*\)\s*\)\s*\)'
        )

        def decode_range(m: re.Match) -> str:
            try:
                start = int(m.group(1))
                stop  = int(m.group(2))
                step  = int(m.group(3)) if m.group(3) else 1
                result = ''.join(chr(n) for n in range(start, stop, step))
                if result.isprintable():
                    return repr(result)
            except Exception:
                pass
            return m.group(0)

        return pattern.sub(decode_range, source)

    # --- XOR encoded byte arrays -----------------------------------------------

    def _decode_xor_byte_arrays(self, source: str) -> str:
        """bytes([x ^ 42 for x in [104, 99, 110, ...]]) → 'hello...'"""
        pattern1 = re.compile(
            r'bytes\s*\(\s*\[\s*\w+\s*\^\s*(\d+)\s+for\s+\w+\s+in\s+'
            r'\[([0-9,\s]+)\]\s*\]\s*\)'
        )

        def decode_xor_list(m: re.Match) -> str:
            try:
                key  = int(m.group(1))
                nums = [int(x.strip()) for x in m.group(2).split(',') if x.strip()]
                decoded = bytes([n ^ key for n in nums])
                return repr(decoded.decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)

        source = pattern1.sub(decode_xor_list, source)

        # bytes([N, N, N, ...]) — pre-computed printable byte arrays
        pattern2 = re.compile(r'bytes\s*\(\s*\[([0-9,\s]+)\]\s*\)')

        def decode_byte_array(m: re.Match) -> str:
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                if all(32 <= n <= 126 or n in (9, 10, 13) for n in nums):
                    decoded = bytes(nums).decode('utf-8', errors='replace')
                    return repr(decoded)
            except Exception:
                pass
            return m.group(0)

        return pattern2.sub(decode_byte_array, source)

    def _decode_xor_comprehension(self, source: str) -> str:
        """
        bytes(b ^ KEY for b in b"raw_bytes") → decoded string
        bytes([b ^ KEY for b in b"raw_bytes"])
        """
        pattern = re.compile(
            r'bytes\s*\(\s*\[?\s*\w+\s*\^\s*(\d+)\s+for\s+\w+\s+in\s+'
            r'(b"[^"]*"|b\'[^\']*\')\s*\]?\s*\)'
        )

        def decode_xor_comp(m: re.Match) -> str:
            try:
                key      = int(m.group(1))
                raw      = ast.literal_eval(m.group(2))
                decoded  = bytes(b ^ key for b in raw)
                return repr(decoded.decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)

        return pattern.sub(decode_xor_comp, source)

    # --- Compression -----------------------------------------------------------

    def _decode_zlib(self, source: str) -> str:
        return self._decode_compression(source, 'zlib', zlib.decompress)

    def _decode_lzma(self, source: str) -> str:
        return self._decode_compression(source, 'lzma', lzma.decompress)

    def _decode_bz2(self, source: str) -> str:
        return self._decode_compression(source, 'bz2', bz2.decompress)

    def _decode_compression(self, source: str, module_name: str, decompress_fn) -> str:
        pattern = re.compile(
            rf'{re.escape(module_name)}\.decompress\s*\(\s*(b"[^"]*"|b\'[^\']*\')\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def do_decompress(m: re.Match) -> str:
            try:
                raw_bytes    = ast.literal_eval(m.group(1))
                decompressed = decompress_fn(raw_bytes)
                return repr(decompressed.decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)

        return pattern.sub(do_decompress, source)

    # --- ROT13 -----------------------------------------------------------------

    def _decode_rot13(self, source: str) -> str:
        """Decode codecs.decode('...', 'rot_13') and variants"""
        pattern = re.compile(
            r'codecs\.decode\s*\(\s*'
            r'(["\'][^"\']+["\'])'
            r'\s*,\s*["\']rot.?13[\'"]\s*\)'
        )

        def do_rot13(m: re.Match) -> str:
            try:
                s = ast.literal_eval(m.group(1))
                return repr(codecs.decode(s, 'rot_13'))
            except Exception:
                return m.group(0)

        return pattern.sub(do_rot13, source)

    # --- Unicode escapes -------------------------------------------------------

    def _decode_unicode_escapes(self, source: str) -> str:
        """Decode '\\u0068\\u0065\\u006c\\u006c\\u006f' → 'hello'"""
        pattern = re.compile(r'"((?:\\u[0-9a-fA-F]{4})+)"|\'((?:\\u[0-9a-fA-F]{4})+)\'')

        def decode_unicode(m: re.Match) -> str:
            content = m.group(1) or m.group(2)
            try:
                decoded = content.encode('utf-8').decode('unicode_escape')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern.sub(decode_unicode, source)

    # --- codecs hex codec ------------------------------------------------------

    def _decode_codecs_hex(self, source: str) -> str:
        """
        codecs.decode(b'68656c6c6f', 'hex') → 'hello'
        Also handles 'hex_codec', 'utf-8-sig' BOM stripping.
        """
        # hex_codec
        pattern = re.compile(
            r'codecs\.decode\s*\(\s*(b["\'][0-9a-fA-F]+["\'])\s*,\s*["\']hex_codec["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )

        def decode_hex_c(m: re.Match) -> str:
            try:
                raw = ast.literal_eval(m.group(1))
                decoded = bytes.fromhex(raw.decode('ascii')).decode('utf-8', errors='replace')
                return repr(decoded)
            except Exception:
                return m.group(0)

        return pattern.sub(decode_hex_c, source)

    # --- Reversed string reconstruction ----------------------------------------

    def _decode_reversed_string(self, source: str) -> str:
        """
        ''.join(reversed("olleh")) → 'hello'
        "olleh"[::-1] → 'hello'
        """
        # ''.join(reversed("..."))
        pattern1 = re.compile(
            r'["\']["\']\.join\s*\(\s*reversed\s*\(\s*(["\'][^"\']+["\'])\s*\)\s*\)'
        )

        def decode_reversed_join(m: re.Match) -> str:
            try:
                s = ast.literal_eval(m.group(1))
                return repr(s[::-1])
            except Exception:
                return m.group(0)

        source = pattern1.sub(decode_reversed_join, source)

        # "olleh"[::-1]
        pattern2 = re.compile(
            r'(["\'][^"\']{2,}["\'])\[::-1\]'
        )

        def decode_slice_reverse(m: re.Match) -> str:
            try:
                s = ast.literal_eval(m.group(1))
                return repr(s[::-1])
            except Exception:
                return m.group(0)

        return pattern2.sub(decode_slice_reverse, source)

    # --- int("ff", 16) constant folding ----------------------------------------

    def _decode_int_hex_literal(self, source: str) -> str:
        """
        int("ff", 16) → 255
        int("0b1010", 2) → 10
        int("777", 8) → 511
        """
        pattern = re.compile(
            r'\bint\s*\(\s*(["\'][0-9a-fA-FxXbBoO]+["\'])\s*,\s*(\d+)\s*\)'
        )

        def decode_int_base(m: re.Match) -> str:
            try:
                s    = ast.literal_eval(m.group(1))
                base = int(m.group(2))
                if base in (2, 8, 10, 16):
                    return str(int(s, base))
            except Exception:
                pass
            return m.group(0)

        return pattern.sub(decode_int_base, source)

    # --- Adjacent string literal folding --------------------------------------

    def _fold_adjacent_string_literals(self, source: str) -> str:
        """
        Fold implicit Python string concatenation at the source level:
        "hel" "lo" → "hello"
        ("foo" "bar") → ("foobar")
        Also handles multi-line implicit concatenation via parentheses.
        Uses AST to do this safely.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        class StringFolder(ast.NodeTransformer):
            def visit_JoinedStr(self, node):
                return node  # Never touch f-strings

            def visit_Constant(self, node):
                return node

        # ast.parse already folds implicit adjacent strings during parsing,
        # but unparsed output won't re-fold them.  The main gain here is from
        # explicit BinOp(Add, str, str) folding at the AST level which is
        # already done in ASTCleaner.  Here we handle the regex-level case
        # of "x" "y" (adjacent without +).
        #
        # We use a regex approach because ast.unparse doesn't produce this.
        pattern = re.compile(
            r'(?<![a-zA-Z0-9_\)])'       # not immediately preceded by identifier or )
            r'(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*)\1'
            r'\s+'
            r'(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*)\3'
        )

        def fold_adj(m: re.Match) -> str:
            q1, s1, q2, s2 = m.group(1), m.group(2), m.group(3), m.group(4)
            try:
                v1 = ast.literal_eval(f'{q1}{s1}{q1}')
                v2 = ast.literal_eval(f'{q2}{s2}{q2}')
                if isinstance(v1, str) and isinstance(v2, str):
                    return repr(v1 + v2)
            except Exception:
                pass
            return m.group(0)

        # Run a few times to handle chains: "a" "b" "c"
        for _ in range(5):
            prev = source
            source = pattern.sub(fold_adj, source)
            if source == prev:
                break

        return source

    # --- encode().decode() round-trip removal ---------------------------------

    def _decode_encode_decode_roundtrip(self, source: str) -> str:
        """
        "hello".encode('utf-8').decode('utf-8') → 'hello'
        "hello".encode().decode() → 'hello'
        """
        pattern = re.compile(
            r'(["\'][^"\'\\]*(?:\\.[^"\'\\]*)*["\'])'
            r'\.encode\s*\([^)]*\)'
            r'\.decode\s*\([^)]*\)'
        )

        def strip_roundtrip(m: re.Match) -> str:
            try:
                s = ast.literal_eval(m.group(1))
                if isinstance(s, str):
                    return repr(s)
            except Exception:
                pass
            return m.group(0)

        return pattern.sub(strip_roundtrip, source)
