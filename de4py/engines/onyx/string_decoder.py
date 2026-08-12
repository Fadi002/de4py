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
import io
import re
import codecs
import bz2
import gzip
import tokenize
import zlib
import lzma
from typing import Optional, Any
from de4py.engines.onyx.constant_eval import fold_constants
from de4py.engines.onyx.safe_eval import safe_eval_scalar, safe_eval_source


class StringDecoder:

    MAX_PASSES = 10

    def decode_all(self, source: str) -> str:
        try:
            for _ in range(self.MAX_PASSES):
                decoded = self._single_pass(source)
                if decoded == source:
                    break
                source = decoded
        except RecursionError:
            pass  # return whatever we have so far
        except Exception:
            pass  # return whatever we have so far
        return source

    def _single_pass(self, source: str) -> str:
        # 0a. AST constant folding: handles b64/b85 chains, chr(ord(i)-N),
        #     int.__xor__ XOR decode, globals()["__builtins__"], builtins-dict subscripts.
        source = fold_constants(source)

        # 0b. Resolve import aliases (must be first for regex compatibility)
        source = self._resolve_import_aliases_for_decoding(source)

        # 0c. __import__('base64').b64decode(...) → base64.b64decode(...) so
        # every decoder below matches the dynamic-import spelling for free,
        # instead of each needing its own dynamic-import variant.
        source = self._normalize_dynamic_imports(source)

        source = self._unwrap_eval_exec(source)
        # Dynamic-import form first: it is a superset of the plain form, and
        # running the plain rule first would eat the inner call and strip the
        # `__import__('base64').` prefix off, leaving a syntax error behind.
        source = self._decode_base64_dynamic_import(source)
        source = self._decode_base64_calls(source)
        source = self._decode_base32_calls(source)
        source = self._decode_base85_calls(source)
        source = self._decode_base16_calls(source)
        source = self._decode_hex_escape_strings(source)
        source = self._decode_bytes_fromhex(source)
        source = self._decode_bytearray_literals(source)
        source = self._decode_chr_chains(source)
        source = self._decode_join_chr_list(source)
        source = self._decode_join_chr_map(source)
        source = self._decode_xor_zip(source)
        source = self._decode_xor_chr_list(source)
        source = self._decode_map_lambda_offset_chr(source)
        source = self._decode_xor_byte_arrays(source)
        source = self._decode_xor_comprehension(source)
        source = self._decode_zlib(source)
        source = self._decode_lzma(source)
        source = self._decode_bz2(source)
        source = self._decode_gzip(source)
        source = self._decode_rot13(source)
        source = self._decode_unicode_escapes(source)
        source = self._decode_codecs_hex(source)
        source = self._decode_reversed_string(source)
        source = self._decode_int_hex_literal(source)
        source = self._decode_encode_decode_roundtrip(source)

        source = self._run_ast_transformations(source)

        return source

    def _resolve_import_aliases_for_decoding(self, source: str) -> str:
        """
        Resolve common import aliases so that base64/zlib/codecs decode patterns
        are recognized regardless of the alias used.
        E.g.: import base64 as _b  →  replace _b with base64 in the source.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        alias_map = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname and alias.name in ('base64', 'zlib', 'bz2', 'lzma', 'gzip', 'codecs', 'binascii'):
                        alias_map[alias.asname] = alias.name
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.asname:
                        alias_map[alias.asname] = alias.name

        if not alias_map:
            return source

        for old, new in alias_map.items():
            source = re.sub(r'\b' + re.escape(old) + r'\b', new, source)
        return source

    _DYNAMIC_IMPORT_MODULES = (
        'base64', 'zlib', 'bz2', 'lzma', 'gzip', 'codecs', 'binascii', 'marshal',
    )

    def _normalize_dynamic_imports(self, source: str) -> str:
        """
        __import__('base64').b64decode(...) → base64.b64decode(...)

        A loader commonly reaches stdlib modules through ``__import__`` (or
        ``vars(__builtins__)['__import__']``, already reduced to a bare
        ``__import__`` call by the constant-eval passes that run before this
        one) specifically so a static ``import base64`` grep won't find it.
        Rewriting the call site to a plain module reference lets every decoder
        below match the module's usual dotted-call shape without each one
        needing a separate dynamic-import variant of its own pattern.
        """
        modules = '|'.join(re.escape(m) for m in self._DYNAMIC_IMPORT_MODULES)
        pattern = re.compile(r'__import__\(\s*[\'"](' + modules + r')[\'"]\s*\)\s*\.')
        return pattern.sub(lambda m: f'{m.group(1)}.', source)

    def _run_ast_transformations(self, source: str) -> str:
        # Fast path check to avoid unnecessary AST parsing
        if not any(k in source for k in (
            'exec', 'eval', 'repr', 'str', 'len', 'bool', 'int', 'float',
            'abs', 'hex', 'oct', 'bin', 'chr', 'ord', 'upper', 'lower',
            'strip', 'title', 'capitalize', 'swapcase', 'replace'
        )) and ' + ' not in source and ' ^ ' not in source:
             return source

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        transformer = ConsolidatedASTTransformer(tree)
        for _ in range(3):
            transformer.changed = False
            tree = transformer.visit(tree)
            if not transformer.changed:
                break

        if not transformer.global_changed:
            return source

        ast.fix_missing_locations(tree)
        try:
            return ast.unparse(tree)
        except Exception:
            return source

    def _unwrap_eval_exec(self, source: str) -> str:
        # Pattern 1: eval/exec("literal string")
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
        source = pattern.sub(replace_match, source)

        # Pattern 2: eval(compile("literal", ...)) or exec(compile("literal", ...))
        pattern2 = re.compile(
            r'(?:eval|exec)\s*\(\s*compile\s*\(\s*'
            r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
            r'\s*,\s*[^)]+\)\s*\)'
        )
        def replace_compile(m):
            try:
                val = ast.literal_eval(m.group(1))
                if isinstance(val, str):
                    return val
            except Exception:
                pass
            return m.group(0)
        source = pattern2.sub(replace_compile, source)
        return source

    @staticmethod
    def _emit_literal(data: bytes, original: str) -> str:
        """
        Re-emit decoded bytes as a Python literal.

        Text payloads become string literals, but a binary one must stay a
        ``bytes`` literal: forcing it through ``decode(errors='replace')``
        both loses bytes and doubles every backslash, which turns a decoded VM
        payload into source that no longer parses.
        """
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            return repr(data)
        if text.isprintable() or all(c in '\r\n\t' or c.isprintable() for c in text):
            return repr(text)
        return repr(data)

    def _decode_base64_calls(self, source: str) -> str:
        pattern = re.compile(
            r'(?:base64\.)?b64decode\s*\(\s*b?(["\'])([A-Za-z0-9+/=\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def decode_b64(m):
            try:
                raw = m.group(2).replace('\n','').replace(' ','')
                return self._emit_literal(base64.b64decode(raw), m.group(0))
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
                return self._emit_literal(base64.b64decode(m.group(1)), m.group(0))
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
            r'(?:base64\.)?b85decode\s*\(\s*b?(["\'])([!-u\s]+)\1\s*\)'
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

    def _decode_hex_escape_strings(self, source: str) -> str:
        """
        Convert ``'\x68\x65'`` string literals to ASCII, leaving bytes alone.

        Literal boundaries come from tokenizing rather than from scanning raw
        text: a ``(?<!b)`` lookbehind only inspects the character before the
        quote, so a long ``b'...'`` payload containing printable bytes lets the
        pattern re-match part way through and splice decoded text into the
        middle of a bytes literal, destroying it.
        """
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
            return source

        escapes = re.compile(r'^(?:\\x[0-9a-fA-F]{2})+$')
        edits = []
        for token in tokens:
            if token.type != tokenize.STRING or token.start[0] != token.end[0]:
                continue
            text = token.string
            prefix = text[:len(text) - len(text.lstrip('bBrRuUfF'))]
            if 'b' in prefix.lower() or 'r' in prefix.lower():
                continue
            body = text[len(prefix):]
            if len(body) < 2 or body[0] not in "\"'" or body[-1] != body[0]:
                continue
            inner = body[1:-1]
            if not inner or not escapes.match(inner):
                continue
            try:
                decoded = bytes.fromhex(inner.replace('\\x', '')).decode('utf-8')
            except (ValueError, UnicodeDecodeError):
                continue
            if not decoded.isascii() or not decoded.isprintable():
                continue
            edits.append((token.start, token.end, repr(decoded)))

        if not edits:
            return source

        lines = source.splitlines(keepends=True)
        for (srow, scol), (_erow, ecol), replacement in reversed(edits):
            line = lines[srow - 1]
            lines[srow - 1] = line[:scol] + replacement + line[ecol:]
        return "".join(lines)

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
        p1 = re.compile(
            r'bytearray\s*\(\s*(b"(?:[^"\\]|\\.)*"|b\'(?:[^\'\\]|\\.)*\')\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
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

    def _decode_chr_chains(self, source: str) -> str:
        # A negative lookbehind on the leading `chr(` keeps this off
        # `__builtins__.chr(78)` / `obj.chr(78)`: matching only the call and
        # substituting a bare literal for it would leave the attribute-access
        # prefix dangling (`__builtins__.'N'`), which is not valid Python.
        # The `+`-chained arms can't carry the same lookbehind (each one
        # legitimately follows a preceding `+`, not a dot), so this only
        # guards the chain's first token.
        pattern = re.compile(
            r'(?<![.\w])(?:chr\s*\(\s*\d{1,3}\s*\)\s*\+\s*)*chr\s*\(\s*\d{1,3}\s*\)'
        )
        def d(m):
            ok, result = safe_eval_source(m.group(0))
            if ok and isinstance(result, str) and result.isprintable():
                return repr(result)
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

    def _decode_xor_zip(self, source: str) -> str:
        """Decode zip/key XOR join patterns."""
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
            ok, result = safe_eval_source(m.group(0))
            if ok and isinstance(result, str) and result.isprintable() and result:
                return repr(result)
            return m.group(0)

        source = p2.sub(d2, source)
        return source

    def _decode_xor_chr_list(self, source: str) -> str:
        pattern = re.compile(
            r'["\']["\']\.join\s*\(\s*chr\s*\(\s*\w+\s*\^\s*(\d+)\s*\)\s+for\s+\w+\s+in\s+'
            r'\[([0-9,\s]+)\]\s*\)'
        )
        def d(m):
            try:
                key  = int(m.group(1))
                nums = [int(x.strip()) for x in m.group(2).split(',') if x.strip()]
                r    = ''.join(chr(n ^ key) for n in nums)
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_map_lambda_offset_chr(self, source: str) -> str:
        pattern = re.compile(
            r'["\']["\']\.join\s*\(\s*map\s*\(\s*lambda\s+(\w+)\s*:\s*chr\s*\(\s*\1\s*([+-])\s*(\d+)\s*\)\s*'
            r',\s*\[([0-9,\s]+)\]\s*\)\s*\)'
        )
        def d(m):
            try:
                op     = m.group(2)
                offset = int(m.group(3))
                nums   = [int(x.strip()) for x in m.group(4).split(',') if x.strip()]
                r = ''.join(chr(n - offset if op == '-' else n + offset) for n in nums)
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

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
            r'bytes\s*\(\s*\[?\s*\w+\s*\^\s*(\d+)\s+for\s+\w+\s+in\s+'
            r'(b"(?:[^"\\]|\\.)*"|b\'(?:[^\'\\]|\\.)*\')\s*\]?\s*\)'
        )
        def d(m):
            try:
                key = int(m.group(1))
                raw = ast.literal_eval(m.group(2))
                return repr(bytes(b^key for b in raw).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_zlib(self, source): return self._decode_compression(source,'zlib',zlib.decompress)
    def _decode_lzma(self, source): return self._decode_compression(source,'lzma',lzma.decompress)
    def _decode_bz2(self,  source): return self._decode_compression(source,'bz2', bz2.decompress)
    def _decode_gzip(self, source): return self._decode_compression(source,'gzip',gzip.decompress)

    def _decode_compression(self, source, name, fn):
        # Escape-aware byte-literal body: a naive [^']* class stops early at
        # the first escaped quote a large binary blob is all but guaranteed
        # to contain, silently leaving the whole call unmatched.
        pattern = re.compile(
            rf'{re.escape(name)}\.decompress\s*\('
            r'\s*(b"(?:[^"\\]|\\.)*"|b\'(?:[^\'\\]|\\.)*\')\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                decompressed = fn(ast.literal_eval(m.group(1)))
                return self._emit_literal(decompressed, m.group(0))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

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


class ConsolidatedASTTransformer(ast.NodeTransformer):
    """Combines all AST-based string transformations into a single pass."""

    SAFE_ZERO_ENV = {
        '__builtins__': {},
        'repr': repr, 'str': str, 'len': len, 'bool': bool,
        'int': int, 'float': float, 'abs': abs, 'hex': hex,
        'oct': oct, 'bin': bin, 'chr': chr, 'ord': ord,
    }
    FOLDABLE_FUNCS = {'repr', 'str', 'len', 'bool', 'int', 'float',
                      'abs', 'hex', 'oct', 'bin', 'chr', 'ord'}
    SAFE_METHODS = {'upper', 'lower', 'strip', 'lstrip', 'rstrip', 'title', 'capitalize', 'swapcase'}
    ARITH_OPS = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod,
                 ast.BitXor, ast.BitAnd, ast.BitOr, ast.LShift, ast.RShift)

    def __init__(self, tree: ast.AST):
        self.changed = False
        self.global_changed = False
        self.bytes_vars = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, bytes)):
                self.bytes_vars[node.targets[0].id] = node.value.value

    def visit_Expr(self, node: ast.Expr) -> Any:
        self.generic_visit(node)
        if (isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id in ('exec', 'eval')
                and len(node.value.args) == 1):
            decoded = self._try_decode_chain(node.value.args[0])
            if decoded and decoded.strip():
                self.changed = True
                self.global_changed = True
                try:
                    return ast.parse(decoded).body
                except SyntaxError:
                    pass
        return node

    def visit_Call(self, node: ast.Call) -> Any:
        self.generic_visit(node)

        if (isinstance(node.func, ast.Name)
                and node.func.id in self.FOLDABLE_FUNCS
                and len(node.args) == 1
                and not node.keywords):
            arg = node.args[0]
            if isinstance(arg, ast.Constant):
                ok, result = safe_eval_scalar(node)
                if ok:
                    self.changed = True
                    self.global_changed = True
                    return ast.Constant(value=result)

        if isinstance(node.func, ast.Attribute):
            if (node.func.attr in self.SAFE_METHODS
                    and isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                    and not node.args and not node.keywords):
                try:
                    self.changed = True
                    self.global_changed = True
                    return ast.Constant(value=getattr(node.func.value.value, node.func.attr)())
                except Exception:
                    pass
            if (node.func.attr == 'replace'
                    and isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                    and len(node.args) == 2
                    and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args)
                    and not node.keywords):
                try:
                    self.changed = True
                    self.global_changed = True
                    return ast.Constant(value=node.func.value.value.replace(node.args[0].value, node.args[1].value))
                except Exception:
                    pass
        return node

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        self.generic_visit(node)

        if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            if (isinstance(node.op, self.ARITH_OPS)
                    and isinstance(node.left.value, (int, float))
                    and isinstance(node.right.value, (int, float))):
                try:
                    ok, result = safe_eval_scalar(node)
                    if not ok:
                        raise ValueError
                    self.changed = True
                    self.global_changed = True
                    return ast.Constant(value=result)
                except Exception:
                    pass
            if isinstance(node.op, ast.Add) and isinstance(node.left.value, str) and isinstance(node.right.value, str):
                self.changed = True
                self.global_changed = True
                return ast.Constant(value=node.left.value + node.right.value)
        return node

    def _try_decode_chain(self, arg_node) -> Optional[str]:
        """Try to decode a possibly chained base64+compress call to a string."""
        if (isinstance(arg_node, ast.Call)
                and isinstance(arg_node.func, ast.Attribute)
                and arg_node.func.attr == 'decompress'
                and len(arg_node.args) == 1):
            inner_bytes = self._try_decode_inner(arg_node.args[0])
            if inner_bytes is not None:
                mod_name = None
                if isinstance(arg_node.func.value, ast.Name):
                    mod_name = arg_node.func.value.id
                try:
                    if mod_name in ('zlib', None):
                        return zlib.decompress(inner_bytes).decode('utf-8', errors='replace')
                    elif mod_name == 'bz2':
                        return bz2.decompress(inner_bytes).decode('utf-8', errors='replace')
                    elif mod_name == 'lzma':
                        return lzma.decompress(inner_bytes).decode('utf-8', errors='replace')
                except Exception:
                    pass
        return None

    def _try_decode_inner(self, arg_node) -> Optional[bytes]:
        """Try to get bytes from a b64decode call or literal."""
        if isinstance(arg_node, ast.Constant) and isinstance(arg_node.value, bytes):
            return arg_node.value
        if isinstance(arg_node, ast.Name) and arg_node.id in self.bytes_vars:
            return self.bytes_vars[arg_node.id]

        if (isinstance(arg_node, ast.Call)
                and isinstance(arg_node.func, ast.Attribute)
                and arg_node.func.attr == 'b64decode'
                and len(arg_node.args) == 1):
            inner = self._try_decode_inner(arg_node.args[0])
            if inner is not None:
                try:
                    return base64.b64decode(inner)
                except Exception:
                    pass
        return None